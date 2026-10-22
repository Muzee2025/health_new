import sys

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.services.zhipu_emohaa_service import ZhipuEmohaaService


def test_app_import_and_routes_available():
    # New FastAPI versions keep included routers lazy. Assert the public
    # contracts, rather than requiring each app.routes entry to expose .path.
    assert "/api/advanced-teacher/warnings" in app.openapi()["paths"]
    with TestClient(app) as client:
        assert client.get("/api/advanced-teacher/warnings").status_code == 401
        with pytest.raises(WebSocketDisconnect) as closed:
            with client.websocket_connect("/api/ws"):
                pass
        assert closed.value.code == 1008


def test_emohaa_provider_selection_matches_python_version():
    service = ZhipuEmohaaService()
    if sys.version_info >= (3, 14):
        assert service.provider == "http"
    else:
        assert service.provider in {"zai_sdk", "http"}
