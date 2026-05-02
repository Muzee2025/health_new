import sys

from app.main import app
from app.services.zhipu_emohaa_service import ZhipuEmohaaService


def test_app_import_and_routes_available():
    paths = {route.path for route in app.routes}
    assert "/api/advanced-teacher/warnings" in paths
    assert "/api/ws" in paths


def test_emohaa_provider_selection_matches_python_version():
    service = ZhipuEmohaaService()
    if sys.version_info >= (3, 14):
        assert service.provider == "http"
    else:
        assert service.provider in {"zai_sdk", "http"}
