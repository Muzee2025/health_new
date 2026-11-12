"""The preview guard blocks outbound sockets without breaking asyncio wakeups."""
import os
import subprocess
import sys
from pathlib import Path


def test_preview_guard_blocks_dns_and_connect_but_allows_internal_socketpair(tmp_path):
    launcher = Path(__file__).resolve().parents[1] / 'scripts' / 'run-local-backend.py'
    check = tmp_path / 'check_guard.py'
    check.write_text('''import asyncio, importlib.util, socket, sys
spec = importlib.util.spec_from_file_location('preview', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.block_outbound_network()
for action in (lambda: socket.getaddrinfo('example.invalid', 443),
               lambda: socket.socket().connect(('127.0.0.1', 9)),
               lambda: socket.socket().connect(('192.0.2.1', 443))):
    try:
        action()
    except RuntimeError as exc:
        assert 'blocks outbound' in str(exc)
    else:
        raise AssertionError('Network guard did not reject operation')
async def wakeup():
    await asyncio.sleep(0)
asyncio.run(wakeup())
print('Outbound DNS/connect blocked; asyncio wakeup passed')
''', encoding='utf-8')
    keep = {'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LOCALAPPDATA', 'APPDATA', 'USERPROFILE'}
    env = {key: value for key, value in os.environ.items() if key.upper() in keep}
    result = subprocess.run([sys.executable, str(check), str(launcher)], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert 'asyncio wakeup passed' in result.stdout


def test_isolated_storage_uses_only_the_selected_deployment_directory(tmp_path):
    launcher = Path(__file__).resolve().parents[1] / 'scripts' / 'run-local-backend.py'
    deployment = tmp_path / 'private'
    deployment.mkdir()
    (deployment / 'health.db').touch()
    envfile = deployment / '.env'
    envfile.write_text(
        f'DATABASE_URL=sqlite:///{(deployment / "health.db").as_posix()}\n'
        'JWT_SECRET_KEY=synthetic-test-only-never-use-in-production\n'
        'RAG_ENABLED=false\nRAG_ALLOW_MODEL_DOWNLOAD=false\n', encoding='utf-8')
    check = tmp_path / 'check_storage.py'
    check.write_text('''import importlib.util, os, pathlib, sys, types
launcher, deployment = sys.argv[1:]
spec = importlib.util.spec_from_file_location('preview', launcher)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
def run(*args, **kwargs):
    assert pathlib.Path.cwd() == pathlib.Path(deployment)
    assert kwargs['host'] == '127.0.0.1'
    assert kwargs['port'] == 18081
    assert os.environ['PYTHON_DOTENV_DISABLED'] == '1'
    assert 'SYNTHETIC_INHERITED_SECRET' not in os.environ
    pathlib.Path('uploads').mkdir()
sys.modules['uvicorn'] = types.SimpleNamespace(run=run)
sys.argv = [launcher, '--env-file', str(pathlib.Path(deployment) / '.env'),
            '--port', '18081', '--isolated-storage', '--block-outbound']
module.main()
print('Explicit deployment storage and environment isolation passed')
''', encoding='utf-8')
    keep = {'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LOCALAPPDATA', 'APPDATA', 'USERPROFILE'}
    env = {key: value for key, value in os.environ.items() if key.upper() in keep}
    env['SYNTHETIC_INHERITED_SECRET'] = 'synthetic-test-only'
    result = subprocess.run([sys.executable, str(check), str(launcher), str(deployment)],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert (deployment / 'uploads').is_dir()
