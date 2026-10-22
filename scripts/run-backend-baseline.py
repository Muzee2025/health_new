"""Run existing backend tests with disposable data and outbound networking blocked.

Usage: .venv/Scripts/python.exe scripts/run-backend-baseline.py [pytest arguments]
Does not install dependencies, read local .env values, or replace missing modules.
"""

import os
import re
import socket
import sys
import tempfile
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    backend = ROOT / "backend"
    scratch = ROOT / "tmp" / "backend-baseline"
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    # Only inspect variable NAMES referenced in source, never a local env file.
    names = {"DEEPSEEK_API_KEY", "QWEN_API_KEY", "DASHSCOPE_API_KEY", "ZHIPU_API_KEY",
             "ZAI_API_KEY", "WECHAT_SECRET", "WECHAT_APPID"}
    for source in (backend / "app").rglob("*.py"):
        text = source.read_text(encoding="utf-8-sig")
        names.update(re.findall(r'(?:getenv|environ\.get)\(\s*[\'"]([A-Z_0-9]+)', text))
    for name in names:
        if any(word in name for word in ("API_KEY", "SECRET", "TOKEN", "PASSWORD")):
            os.environ[name] = ""
    os.environ["JWT_SECRET_KEY"] = "w2-disposable-test-secret-never-use-in-production"
    os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

    # Windows asyncio uses socketpair() for its internal wake-up channel. Permit
    # only that standard-library call's loopback connect, never arbitrary local
    # services (including the developer's existing backend on port 8000).
    socketpair_state = threading.local()
    original_socketpair = socket.socketpair

    def internal_socketpair(*args, **kwargs):
        socketpair_state.active = True
        try:
            return original_socketpair(*args, **kwargs)
        finally:
            socketpair_state.active = False

    socket.socketpair = internal_socketpair

    def deny_network(event, args):
        if event == "socket.connect" and getattr(socketpair_state, "active", False):
            address = args[1]
            if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
                return
        if event in {"socket.connect", "socket.getaddrinfo"}:
            raise RuntimeError("Backend test runner blocks outbound networking")

    # Imports may instantiate HTTP clients. Install the guard before importing tests.
    sys.addaudithook(deny_network)
    try:
        import pytest
    except ImportError:
        print("BLOCKED: pytest is not installed in the selected Python environment")
        return 2
    previous_cwd = Path.cwd()
    previous_tempdir = tempfile.tempdir
    try:
        test_args = []
        has_target = False
        for arg in sys.argv[1:]:
            path, *node_id = arg.split("::")
            candidate = previous_cwd / path
            if not arg.startswith("-") and candidate.exists():
                has_target = True
                test_args.append("::".join([str(candidate.resolve()), *node_id]))
            else:
                test_args.append(arg)
        if not has_target:
            test_args.insert(0, str(backend / "tests"))
        # Some existing tests retain SQLite handles on Windows. Leftovers remain ignored.
        with tempfile.TemporaryDirectory(prefix="run-", dir=scratch, ignore_cleanup_errors=True) as run:
            run_dir = Path(run)
            os.environ["DATABASE_URL"] = "sqlite:///" + (run_dir / "baseline.db").as_posix()
            os.environ["RAG_ENABLED"] = "false"
            os.environ["RAG_ALLOW_MODEL_DOWNLOAD"] = "false"
            os.environ["CHROMA_DIR"] = str(run_dir / "chroma")
            os.environ["CORS_ALLOWED_ORIGINS"] = "http://127.0.0.1:5173"
            os.environ["HEALTH_TEST_ISOLATED"] = "1"
            os.environ["TEMP"] = os.environ["TMP"] = str(run_dir)
            tempfile.tempdir = str(run_dir)
            os.chdir(run_dir)
            sys.path.insert(0, str(backend))
            print("Backend tests: disposable SQLite/files, dotenv and RAG disabled, Python socket/DNS blocked")
            return int(pytest.main([*test_args, "-q", "--tb=short", "--disable-warnings"]))
    finally:
        os.chdir(previous_cwd)
        tempfile.tempdir = previous_tempdir


if __name__ == "__main__":
    raise SystemExit(main())
