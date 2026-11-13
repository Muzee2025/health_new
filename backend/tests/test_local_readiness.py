"""Health endpoint checks against isolated synthetic SQLite schemas only."""

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

if os.environ.get("HEALTH_TEST_ISOLATED") != "1":
    raise RuntimeError("Run through scripts/run-backend-baseline.py")

from app.database import Base, get_db
from app.routers.health import router


def _test_app(db_dependency):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = db_dependency
    return app


@pytest.fixture
def isolated_engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'readiness.sqlite3').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    yield engine
    engine.dispose()


def _dependency_for_factory(factory):
    def dependency():
        with factory() as session:
            yield session

    return dependency


def test_liveness_is_public_and_does_not_require_database():
    client = TestClient(_test_app(lambda: None))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "health-new"}


def test_readiness_accepts_empty_database_with_complete_schema(isolated_engine):
    Base.metadata.create_all(bind=isolated_engine)
    factory = sessionmaker(bind=isolated_engine)
    client = TestClient(_test_app(_dependency_for_factory(factory)))

    response = client.get("/api/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "health-new",
        "schema_ready": True,
    }


@pytest.mark.parametrize("schema_case", ["missing_table", "missing_column"])
def test_readiness_sanitizes_incomplete_schema(isolated_engine, schema_case):
    if schema_case == "missing_table":
        Base.metadata.create_all(bind=isolated_engine, tables=[Base.metadata.tables["users"]])
    else:
        with isolated_engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")

    factory = sessionmaker(bind=isolated_engine)
    client = TestClient(_test_app(_dependency_for_factory(factory)))

    response = client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "service": "health-new",
        "schema_ready": False,
    }
    assert "sqlite" not in response.text.lower()
    assert "users" not in response.text.lower()


def test_readiness_sanitizes_connection_errors():
    class UnavailableSession:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("sqlite:///private/path with SQL SELECT sensitive_data")

    def unavailable_dependency():
        yield UnavailableSession()

    client = TestClient(_test_app(unavailable_dependency))

    response = client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "service": "health-new",
        "schema_ready": False,
    }
    assert "private" not in response.text
    assert "sensitive_data" not in response.text
