// Isolated gzip SPA preview: no backend, no real credentials or API forwarding.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { gzipSync } from 'node:zlib';
import assert from 'node:assert/strict';
const root=path.resolve(process.env.PERF_PREVIEW_DIR || 'tmp/frontend-audit');
const port=Number(process.env.PERF_PREVIEW_PORT || 4185);
assert(root.startsWith(path.resolve('tmp')+path.sep),'Serve only an isolated audit build inside tmp');
assert(fs.existsSync(path.join(root,'index.html')),'Prepare a compiled audit build first');
const realRoot=fs.realpathSync(root);
assert(Number.isInteger(port) && port>=1024 && port<=65535,'Use a valid local preview port');
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.webp':'image/webp','.woff2':'font/woff2'};
http.createServer((request,response)=>{
  let pathname;
  try {pathname=decodeURIComponent(new URL(request.url,'http://localhost').pathname);} catch {response.writeHead(400).end();return;}
  if(pathname.startsWith('/api/')) {response.writeHead(503,{'Content-Type':'application/json'}).end('{"detail":"Isolated audit preview has no backend"}');return;}
  if(!['GET','HEAD'].includes(request.method)) {response.writeHead(405).end();return;}
  let target=path.resolve(root,'.'+pathname);
  if(!target.startsWith(root+path.sep) && target!==root) {response.writeHead(403).end();return;}
  if(!fs.existsSync(target) || fs.statSync(target).isDirectory()) {
    if(path.extname(pathname)) {response.writeHead(404).end();return;}
    target=path.join(root,'index.html');
  }
  if(!fs.realpathSync(target).startsWith(realRoot+path.sep)) {response.writeHead(403).end();return;}
  const extension=path.extname(target);
  let bytes=fs.readFileSync(target);
  const headers={'Content-Type':types[extension] || 'application/octet-stream','Cache-Control':'no-store'};
  if(['.html','.js','.css','.json','.svg'].includes(extension) && String(request.headers['accept-encoding']).includes('gzip')) {
    bytes=gzipSync(bytes);headers['Content-Encoding']='gzip';
  }
  headers['Content-Length']=bytes.length;
  response.writeHead(200,headers);response.end(request.method==='HEAD'?undefined:bytes);
}).listen(port,'127.0.0.1',()=>console.log(`Isolated compiled audit preview: http://127.0.0.1:${port}`));
