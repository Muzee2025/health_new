"""Probe repository Nginx configs with cached images and a synthetic backend.

This never builds the application image or uses an application database/key.
Run without --run to print a plan. Test certificates are generated locally.
"""
import argparse  # noqa: I001
import importlib.util
import os
import shutil
import sys  # noqa: F401
import base64
import gzip
import hashlib
import http.client
import json
from pathlib import Path
import secrets
import socket
import ssl
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run', action='store_true')
parser.add_argument('--nginx-image', default='nginx:1.30.6-alpine', help='locally cached image; never pulled')
parser.add_argument('--probe-image', default='python:3.12-slim', help='cached Python image for synthetic HTTP only')
parser.add_argument('--openssl', default=shutil.which('openssl'), help='local OpenSSL executable for QA-only certificate')
parser.add_argument('--http-port', type=int, default=4189)
parser.add_argument('--tls-port', type=int, default=4190)
args = parser.parse_args()
if args.http_port == args.tls_port or any(p in {8000,5173,18080,18081} or not 1024 <= p <= 65535 for p in (args.http_port,args.tls_port)):
    parser.error('choose two distinct non-reserved loopback ports above 1023')
if not args.run:
    print(json.dumps({'mode':'plan','nginx_image':args.nginx_image,'synthetic_image':args.probe_image,
        'http_port':args.http_port,'tls_port':args.tls_port,'pull_images':False,
        'checks':['nginx -t','SPA','gzip','HTTP/TLS proxy','SSE incremental delivery','WebSocket handshake and frame'],
        'scope':'synthetic transport; not application or production acceptance'},indent=2))
    raise SystemExit(0)
if not args.openssl or not Path(args.openssl).is_file():
    parser.error('a local OpenSSL executable is required for QA certificates')
SPEC = importlib.util.spec_from_file_location('fullstack_runner', ROOT/'scripts/verify-fullstack.py')
SHARED = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SHARED)
PREFIX = 'healthnew-qa-transport-' + secrets.token_hex(5)
OUT = ROOT/'tmp'/PREFIX
# Reuse path, project and private ACL checks; never create a QA application env.
SAFETY = SHARED.Runner(ROOT,args.http_port,40,True)
SAFETY.project = PREFIX
SAFETY.output = OUT
SAFETY.preflight()
port_free_check = socket.socket()
try:
    port_free_check.bind(('127.0.0.1',args.tls_port))
finally:
    port_free_check.close()
OUT.mkdir(mode=0o700)
if os.name == 'nt':
    user = os.environ.get('USERNAME')
    if not user or subprocess.run(['icacls',str(OUT),'/inheritance:r','/grant:r',f'{user}:(OI)(CI)F'],capture_output=True,timeout=20).returncode:
        raise SystemExit('private output ACL could not be established')
NETWORK_CREATED = False
NETWORK = PREFIX + '-net'
NAMES = []
RESULT = {'scope': 'cached images and synthetic transport only', 'project': PREFIX,
          'target_images_built': False, 'checks': {}, 'cleanup': {}}
N = args.nginx_image
P = args.probe_image

def command(args, name, check=True):
    proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=40, env=SHARED.docker_environment(os.environ))
    (OUT / (name + '.log')).write_text(proc.stdout + proc.stderr, encoding='utf-8')
    if check and proc.returncode:
        raise RuntimeError(name + ' failed: exit ' + str(proc.returncode))
    return proc

def docker(args, name, check=True):
    return command(['docker', *args], name, check)

def mount(source, target):
    return ['--mount', f'type=bind,source={source},target={target},readonly']

def port_free(port):
    with socket.socket() as s:
        s.bind(('127.0.0.1', port))

def connection(tls=False):
    if tls:
        return http.client.HTTPSConnection('127.0.0.1', args.tls_port, timeout=5,
            context=ssl.create_default_context(cafile=str(OUT/'certs/fullchain.pem')))
    return http.client.HTTPConnection('127.0.0.1', args.http_port, timeout=5)

def probe(tls=False):
    label = 'tls' if tls else 'http'
    for attempt in range(8):
        try:
            c = connection(tls)
            c.request('GET', '/api/health/ready')
            r = c.getresponse()
            assert r.status == 200 and json.loads(r.read()) == {'qa': 'ready'}
            c.close()
            break
        except (OSError, AssertionError, http.client.HTTPException):
            if attempt == 7:
                raise
            time.sleep(.1)
    c = connection(tls)
    c.request('GET', '/student/dashboard')
    r = c.getresponse()
    assert r.status == 200 and b'QA-SPA' in r.read()
    c.close()
    c = connection(tls)
    c.request('GET', '/qa.js', headers={'Accept-Encoding':'gzip'})
    r = c.getresponse()
    assert r.status == 200 and r.getheader('Content-Encoding') == 'gzip'
    assert gzip.decompress(r.read()).startswith(b'const qa =')
    c.close()
    c = connection(tls)
    started = time.monotonic()
    c.request('GET', '/api/qa/events')
    r = c.getresponse()
    assert r.status == 200 and r.getheader('Content-Type') == 'text/event-stream'
    first = r.readline()
    first_at = time.monotonic()-started
    assert first == b'data: first\n'
    remaining = r.read()
    completed_at = time.monotonic()-started
    assert b'data: second' in remaining and completed_at-first_at > .9
    c.close()
    raw = socket.create_connection(('127.0.0.1', args.tls_port if tls else 4189), timeout=5)
    s = ssl.create_default_context(cafile=str(OUT/'certs/fullchain.pem')).wrap_socket(raw, server_hostname='127.0.0.1') if tls else raw
    key = base64.b64encode(secrets.token_bytes(16)).decode()
    request = ('GET /api/qa/ws HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
               f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n')
    s.sendall(request.encode())
    received = b''
    while b'\r\n\r\n' not in received:
        piece = s.recv(4096)
        if not piece:
            raise RuntimeError('WebSocket closed before the upgrade response')
        received += piece
    head, frame = received.split(b'\r\n\r\n', 1)
    assert b'101 Switching Protocols' in head
    expected = base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
    assert expected.lower() in head.lower()
    while len(frame) < 8:
        piece = s.recv(4096)
        if not piece:
            break
        frame += piece
    assert frame[:8] == b'\x81\x06qa-ack'
    s.close()
    RESULT['checks'][label] = {'health_proxy':True, 'spa_fallback':True, 'gzip':True,
        'sse_first_seconds':round(first_at,3), 'sse_complete_seconds':round(completed_at,3),
        'sse_first_arrived_before_second':True, 'websocket_upgrade_and_frame':True,
        'certificate_verified_against_qa_ca': tls}

backend = '''import base64,hashlib,json,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
class Handler(BaseHTTPRequestHandler):
 protocol_version='HTTP/1.1'
 def log_message(self,*args): pass
 def do_GET(self):
  if self.path=='/api/qa/ws':
   key=self.headers['Sec-WebSocket-Key']
   accept=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
   self.send_response(101);self.send_header('Upgrade','websocket');self.send_header('Connection','Upgrade');self.send_header('Sec-WebSocket-Accept',accept);self.end_headers()
   self.wfile.write(b'\\x81\\x06qa-ack');self.wfile.flush();self.close_connection=True
  elif self.path=='/api/qa/events':
   self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Connection','close');self.end_headers()
   self.wfile.write(b'data: first\\n\\n');self.wfile.flush();time.sleep(1.25);self.wfile.write(b'data: second\\n\\n');self.wfile.flush();self.close_connection=True
  else:
   body=json.dumps({'qa':'ready'}).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
ThreadingHTTPServer(('0.0.0.0',8000),Handler).serve_forever()
'''
(OUT/'probe-backend.py').write_text(backend, encoding='utf-8')
(OUT/'html').mkdir(exist_ok=False)
(OUT/'html/index.html').write_text('<html><body>QA-SPA</body></html>', encoding='utf-8')
(OUT/'html/qa.js').write_text('const qa = "'+('synthetic '*600)+'";', encoding='utf-8')
(OUT/'certs').mkdir(exist_ok=False)
try:
    port_free(args.http_port);port_free(args.tls_port)  # noqa: E702
    for tag, label in ((N,'nginx'), (P,'synthetic_python')):
        item = json.loads(docker(['image','inspect',tag,'--format','{{json .Id}}'], label+'-id').stdout)
        RESULT[label+'_image_id'] = item
    RESULT['nginx_version'] = docker(['run','--rm','--pull','never','--network','none','--entrypoint','nginx',N,'-v'],'nginx-version').stderr.strip()
    (OUT/'certs/qa.cnf').write_text('[req]\ndistinguished_name=dn\nx509_extensions=v3\nprompt=no\n[dn]\nCN=localhost\n[v3]\nsubjectAltName=DNS:localhost,IP:127.0.0.1\n', encoding='utf-8')
    command([args.openssl,'req','-x509','-newkey','rsa:2048','-nodes',
        '-keyout',str(OUT/'certs/privkey.pem'),'-out',str(OUT/'certs/fullchain.pem'),'-days','1',
        '-config',str(OUT/'certs/qa.cnf')], 'qa-certificate')
    # Only this disposable QA key: the private parent protects host traversal;
    # the selectively mounted certificate directory must be readable by Nginx.
    (OUT/'certs/privkey.pem').chmod(0o444)
    docker(['network','create','--label',f'healthnew.qa={PREFIX}',NETWORK], 'network-create')
    NETWORK_CREATED = True
    name = PREFIX+'-backend';NAMES.append(name)  # noqa: E702
    docker(['run','-d','--name',name,'--pull','never','--network',NETWORK,'--network-alias','backend',
        '--label',f'healthnew.qa={PREFIX}','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true',
        '--user','65534:65534',*mount(OUT/'probe-backend.py','/probe.py'),P,'python','-B','/probe.py'], 'backend-start')
    for tls in (False,True):
        name=PREFIX+('-tls' if tls else '-http');NAMES.append(name)  # noqa: E702
        site=ROOT/'deploy/fullstack'/('nginx-tls.conf' if tls else 'nginx.conf')
        frontend_args=['run','-d','--name',name,'--pull','never','--network',NETWORK,'--label',f'healthnew.qa={PREFIX}',
            '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true','--user','nginx',
            '--tmpfs','/tmp:size=32m,noexec,nosuid','-p',f'127.0.0.1:{args.http_port}:8080',
            *mount(ROOT/'deploy/fullstack/nginx-main.conf','/etc/nginx/nginx.conf'),*mount(site,'/etc/nginx/conf.d/default.conf'),
            *mount(OUT/'html','/usr/share/nginx/html')]
        if tls:
            frontend_args+=['-p',f'127.0.0.1:{args.tls_port}:8443',*mount(OUT/'certs','/etc/nginx/tls')]
        frontend_args+=['--entrypoint','nginx',N,'-g','daemon off;']
        docker(frontend_args,'frontend-start-'+str(tls))
        docker(['exec',name,'nginx','-t'],'nginx-config-'+str(tls))
        probe(tls)
        fields=docker(['inspect','--format','{{.Config.User}}|{{.HostConfig.ReadonlyRootfs}}|{{json .HostConfig.CapDrop}}',name],'safe-inspect-'+str(tls)).stdout.strip()
        assert fields=='nginx|true|["ALL"]', fields
        RESULT['checks']['tls' if tls else 'http']['nonroot_readonly_capdrop'] = True
        docker(['stop','-t','2',name],'frontend-stop-'+str(tls))
        docker(['rm',name],'frontend-remove-'+str(tls));NAMES.remove(name)  # noqa: E702
        RESULT['cleanup'][name] = {'stop_exit':0, 'remove_exit':0}
    RESULT['status']='passed'
except Exception as exc:
    RESULT['status']='failed';RESULT['error']=str(exc)  # noqa: E702
finally:
    for name in reversed(NAMES):
        ownership = docker(['inspect','--format','{{index .Config.Labels "healthnew.qa"}}',name], name+'-ownership',False)
        if ownership.returncode or ownership.stdout.strip() != PREFIX:
            RESULT['cleanup'][name] = {'error':'owned container not found; no stop or removal attempted'}
            continue
        docker(['logs','--tail','15',name],name+'-diagnostics',False)
        stop=docker(['stop','-t','2',name],name+'-stop',False)
        remove=docker(['rm',name],name+'-remove',False)
        RESULT['cleanup'][name]={'stop_exit':stop.returncode,'remove_exit':remove.returncode}
    RESULT['cleanup']['network_remove_exit']=docker(['network','rm',NETWORK],'network-remove',False).returncode if NETWORK_CREATED else 0
    (OUT/'nginx-transport-summary.json').write_text(json.dumps(RESULT,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(RESULT,indent=2))
    cleanup_ok = RESULT['cleanup']['network_remove_exit']==0 and all(
        value.get('stop_exit')==0 and value.get('remove_exit')==0
        for key,value in RESULT['cleanup'].items() if key!='network_remove_exit')
    raise SystemExit(0 if RESULT.get('status')=='passed' and cleanup_ok else 1)
