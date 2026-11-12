"""W2 security regression checks using only synthetic users and disposable SQLite."""
from __future__ import annotations

import asyncio
import io
import os
import time
import uuid
import zipfile

import bcrypt
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# The test runner supplies a disposable DATABASE_URL and disables dotenv before
# collection. Keep a deterministic synthetic signing key for these test tokens.
os.environ["JWT_SECRET_KEY"] = "W2-security-test-only-key-7f41a2d9c03e8b65"
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

from app import models  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.security import login_guard  # noqa: E402
from app.upload_body_limit import UPLOAD_PATHS, UPLOAD_REQUEST_LIMIT, UploadBodyLimitMiddleware  # noqa: E402

TEST_KEY = os.environ["JWT_SECRET_KEY"]
TOKEN_ISSUER = "health-new"
TOKEN_AUDIENCE = "health-new-api"


def _claims(sub: object = "42", **overrides) -> dict:
    now = int(time.time())
    claims = {
        "sub": sub,
        "ver": 2,
        "type": "access",
        "iat": now,
        "exp": now + 900,
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
    }
    claims.update(overrides)
    return claims


def _token(sub: object = "42", *, key: str = TEST_KEY, algorithm: str = "HS256", **claims) -> str:
    return jwt.encode(_claims(sub, **claims), key, algorithm=algorithm)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


@pytest.fixture()
def security_client(tmp_path):
    """Build fixture-only schema and identities in an isolated temporary SQLite file."""
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'security.sqlite3').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    sessions = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with sessions() as db:
        db.add_all(
            [
                models.User(
                    id=42,
                    username="3141592653",
                    password_hash=_password_hash("LegacyPass123"),
                    role="student",
                    student_id="S-42",
                    name="Synthetic Student",
                ),
                models.User(
                    id=52,
                    username="teacher-a",
                    password_hash=_password_hash("SyntheticPass123"),
                    role="teacher",
                    name="Synthetic Teacher A",
                ),
                models.User(
                    id=53,
                    username="teacher-b",
                    password_hash=_password_hash("SyntheticPass123"),
                    role="teacher",
                    name="Synthetic Teacher B",
                ),
                models.User(
                    id=54,
                    username="other-student",
                    password_hash=_password_hash("SyntheticPass123"),
                    role="student",
                    student_id="S-54",
                    name="Other Synthetic Student",
                ),
            ]
        )
        db.commit()

    previous_overrides = dict(app.dependency_overrides)

    def override_get_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with login_guard._lock:
        login_guard._entries.clear()
    try:
        with TestClient(app) as client:
            yield client, sessions
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        engine.dispose()


def test_strict_v2_tokens_reject_forgery_expiry_legacy_claims_and_subject_confusion(security_client):
    client, _ = security_client
    now = int(time.time())
    legacy = _claims()
    legacy.pop("ver")
    legacy.pop("type")
    invalid_tokens = [
        _token(key="wrong-synthetic-signing-key-88a741f92cbe636d"),
        _token(**{"exp": now - 1}),
        jwt.encode(legacy, TEST_KEY, algorithm="HS256"),
        _token(**{"sub": "01"}),
        _token(**{"sub": 42}),
        _token(algorithm="HS384"),
        _token(**{"aud": "another-api"}),
    ]

    for token in invalid_tokens:
        response = client.get("/api/me", headers=_auth(token))
        assert response.status_code == 401


def test_numeric_username_uses_same_token_identity_over_http_and_websocket(security_client):
    client, _ = security_client
    token = _token("42")

    response = client.get("/api/me", headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["id"] == 42
    assert response.json()["username"] == "3141592653"

    with client.websocket_connect("/api/ws", subprotocols=["access_token", token]) as websocket:
        assert websocket.accepted_subprotocol == "access_token"
        websocket.send_text("ping")
        assert websocket.receive_text() == "pong"


def test_registration_limits_role_and_password_and_old_bcrypt_hash_remains_usable(security_client):
    client, _ = security_client
    teacher_signup = client.post(
        "/api/register",
        json={"username": "public-teacher", "password": "StrongPass123", "role": "teacher"},
    )
    assert teacher_signup.status_code == 422

    weak_password = client.post(
        "/api/register",
        json={"username": "weak-password-user", "password": "short1"},
    )
    assert weak_password.status_code == 400

    login = client.post(
        "/api/login",
        json={"username": "3141592653", "password": "LegacyPass123"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["id"] == 42
    assert client.get("/api/me", headers=_auth(login.json()["access_token"])).status_code == 200


def test_login_guard_returns_retry_after_after_repeated_failures(security_client):
    client, _ = security_client
    with login_guard._lock:
        login_guard._entries.clear()

    for _ in range(5):
        response = client.post(
            "/api/login",
            json={"username": "rate-limit-synthetic-account", "password": "WrongPass123"},
        )
        assert response.status_code == 401

    limited = client.post(
        "/api/login",
        json={"username": "rate-limit-synthetic-account", "password": "WrongPass123"},
    )
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) > 0


def test_login_guard_counts_a_concurrent_burst_once_per_attempt(security_client):
    """The limit must hold when the attempts arrive together.

    A check that only read the counter let every concurrent request pass before
    any of them was counted, so a burst of 40 all got through. The reservation
    has to happen inside the same locked step as the check.
    """
    import threading

    client, _ = security_client
    with login_guard._lock:
        login_guard._entries.clear()

    burst = 40
    statuses: list[int] = []
    start = threading.Barrier(burst)
    guard = threading.Lock()

    def attempt() -> None:
        start.wait()
        response = client.post(
            "/api/login",
            json={"username": "burst-synthetic-account", "password": "WrongPass123"},
        )
        with guard:
            statuses.append(response.status_code)

    threads = [threading.Thread(target=attempt) for _ in range(burst)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # Five attempts per account are allowed; everything past that is refused,
    # however many arrived at once.
    assert statuses.count(401) == 5
    assert statuses.count(429) == burst - 5


def test_anonymous_access_and_x_user_id_header_do_not_authenticate(security_client):
    client, _ = security_client
    headers = {"X-User-Id": "42"}
    for path in (
        "/api/me",
        "/api/advanced-ai/sessions",
        "/api/advanced-teacher/dashboard/metrics",
        "/api/v1/report/analysis/diagnostics",
    ):
        assert client.get(path, headers=headers).status_code == 401

    # WebSocket credentials belong in the supported subprotocol pair, not URL query logs.
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as closed:
        with client.websocket_connect("/api/ws?token=synthetic", headers=headers):
            pass
    assert closed.value.code == 1008


def test_teacher_scope_protects_appointments_interventions_and_profiles(security_client):
    client, sessions = security_client
    with sessions() as db:
        db.add_all(
            [
                models.TeacherStudentAssignment(teacher_id=52, student_id=42),
                models.TeacherStudentAssignment(teacher_id=53, student_id=54),
                models.Appointment(student_id=42, teacher_id=52, time_slot="slot-a", status="pending"),
                models.Appointment(student_id=54, teacher_id=53, time_slot="slot-b", status="pending"),
                models.InterventionRecord(
                    student_id=42, teacher_id=52, record_date="2026-10-22", notes="synthetic-a-only"
                ),
                models.InterventionRecord(
                    student_id=54, teacher_id=53, record_date="2026-10-22", notes="synthetic-b-only"
                ),
            ]
        )
        db.commit()
        foreign_appointment_id = db.query(models.Appointment.id).filter_by(teacher_id=52).scalar()

    student_headers = _auth(_token("42"))
    teacher_a_headers = _auth(_token("52"))
    teacher_b_headers = _auth(_token("53"))

    for path, method, _payload in (
        ("/api/teacher/appointments", "get", None),
        ("/api/teacher/interventions", "get", None),
        ("/api/teacher/teachers_profiles", "get", None),
    ):
        response = getattr(client, method)(path, headers=student_headers)
        assert response.status_code == 403

    own_appointments = client.get("/api/teacher/appointments", headers=teacher_b_headers)
    assert own_appointments.status_code == 200
    assert all(item["teacher_id"] == 53 for item in own_appointments.json())
    cross_appointment = client.post(
        f"/api/teacher/appointments/{foreign_appointment_id}/status?status=completed",
        headers=teacher_b_headers,
    )
    assert cross_appointment.status_code == 404

    own_interventions = client.get("/api/teacher/interventions", headers=teacher_b_headers)
    assert own_interventions.status_code == 200
    notes = [item["notes"] for item in own_interventions.json()]
    assert "synthetic-b-only" in notes
    assert "synthetic-a-only" not in notes
    forbidden_intervention = client.post(
        "/api/teacher/interventions",
        headers=student_headers,
        json={"student_id": 54, "record_date": "2026-10-22", "notes": "synthetic"},
    )
    assert forbidden_intervention.status_code == 403

    cross_profile = client.post(
        "/api/teacher/teachers_profiles",
        headers=teacher_a_headers,
        json={"user_id": 53, "title": "Synthetic"},
    )
    assert cross_profile.status_code == 403


def test_report_diagnostics_only_returns_current_users_safe_job_snapshot(security_client, monkeypatch):
    client, _ = security_client
    from app.routers import report_v1

    monkeypatch.setattr(
        report_v1,
        "get_analysis_job_snapshot",
        lambda user_id: {
            "status": "idle",
            "started_at": None,
            "finished_at": None,
            "deadline_seconds": 0,
            "duration_ms": 0,
            "api_key": "must-not-escape",
            "other_user": "must-not-escape",
        },
    )
    response = client.get("/api/v1/report/analysis/diagnostics", headers=_auth(_token("42")))
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == 42
    assert list(body["queue"]) == ["42"]
    assert body["queue"]["42"] == {
        "status": "idle",
        "started_at": None,
        "finished_at": None,
        "deadline_seconds": 0,
        "duration_ms": 0,
    }
    assert "must-not-escape" not in response.text
    assert body["db"]["ok"] is True


def _synthetic_png(width: int = 1, height: int = 1) -> bytes:
    # Enough structure for the validator's signature/IHDR/dimension checks.
    return b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x06\x00\x00\x00" + b"\x00\x00\x00\x00"


def _synthetic_docx() -> bytes:
    members = {
        "[Content_Types].xml": b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        "_rels/.rels": b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        "word/document.xml": b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body/></w:document>',
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, contents in members.items():
            archive.writestr(name, contents)
    return buffer.getvalue()


def test_upload_magic_mime_bounds_and_protected_document_download(security_client):
    client, _ = security_client
    teacher_headers = _auth(_token("52"))
    student_headers = _auth(_token("42"))

    bad_image = client.post(
        "/api/teacher/upload",
        headers=teacher_headers,
        files={"file": ("fake.png", b"not-an-image", "image/png")},
    )
    assert bad_image.status_code == 415
    good_image = client.post(
        "/api/teacher/upload",
        headers=teacher_headers,
        files={"file": ("tiny.png", _synthetic_png(), "image/png")},
    )
    assert good_image.status_code == 200
    assert "/static/public_images/" in good_image.json()["url"]

    invalid_pdf = client.post(
        "/api/teacher/upload",
        headers=teacher_headers,
        files={"file": ("fake.pdf", b"not a PDF", "application/pdf")},
    )
    assert invalid_pdf.status_code == 415
    good_pdf = client.post(
        "/api/teacher/upload",
        headers=teacher_headers,
        files={
            "file": (
                "synthetic.pdf",
                b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n",
                "application/pdf",
            )
        },
    )
    assert good_pdf.status_code == 200
    pdf_url = good_pdf.json()["url"]
    pdf_download = client.get(pdf_url, headers=student_headers)
    assert pdf_download.status_code == 200
    assert pdf_download.headers["content-type"].startswith("application/pdf")

    good_docx = client.post(
        "/api/teacher/upload",
        headers=teacher_headers,
        files={
            "file": (
                "synthetic.docx",
                _synthetic_docx(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert good_docx.status_code == 200
    document_url = good_docx.json()["url"]
    assert "/api/teacher/documents/" in document_url

    anonymous_download = client.get(document_url)
    assert anonymous_download.status_code == 401
    protected_download = client.get(document_url, headers=student_headers)
    assert protected_download.status_code == 200
    assert protected_download.headers["x-content-type-options"] == "nosniff"
    assert "private" in protected_download.headers["cache-control"]
    assert client.get("/api/teacher/documents/%2e%2e%2fsecret.docx", headers=student_headers).status_code == 404
    opaque_name = document_url.rsplit("/", 1)[-1]
    assert client.get(f"/static/article_documents/{opaque_name}").status_code == 404


def test_upload_limits_reject_oversized_images_and_invalid_upload_entrypoints(security_client):
    client, _ = security_client
    student_headers = _auth(_token("42"))
    too_large = b"x" * (5 * 1024 * 1024 + 1)
    response = client.post(
        "/api/advanced-ai/chat/upload",
        headers=student_headers,
        data={"type": "image"},
        files={"file": ("large.png", too_large, "image/png")},
    )
    assert response.status_code == 413

    # The teacher upload endpoint uses the same bounded reader before format dispatch.
    teacher_response = client.post(
        "/api/teacher/upload",
        headers=_auth(_token("52")),
        files={"file": ("large.pdf", too_large, "application/pdf")},
    )
    assert teacher_response.status_code == 413


@pytest.mark.parametrize("path", sorted(UPLOAD_PATHS))
def test_asgi_upload_middleware_counts_chunked_body_without_content_length(path):
    """The ingress cap must still apply when clients omit Content-Length."""
    downstream_called = False
    sent = []

    async def downstream(scope, receive, send):
        nonlocal downstream_called
        downstream_called = True

    async def receive():
        return {"type": "http.request", "body": b"x" * (UPLOAD_REQUEST_LIMIT + 1), "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }
    asyncio.run(UploadBodyLimitMiddleware(downstream)(scope, receive, send))

    assert downstream_called is False
    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 413


def test_cors_allows_only_configured_origins(security_client):
    client, _ = security_client
    allowed = client.options(
        "/api/login",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert "authorization" in allowed.headers["access-control-allow-headers"].lower()

    denied = client.options(
        "/api/login",
        headers={
            "Origin": "https://untrusted.invalid",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_article_view_counter_increments_and_deduplicates_synthetic_viewer(security_client):
    client, sessions = security_client
    with sessions() as db:
        article = models.Article(title="Synthetic article", content="Synthetic only", views=100)
        db.add(article)
        db.commit()
        db.refresh(article)
        article_id = article.id

    viewer_one = f"synthetic-{uuid.uuid4().hex}"
    viewer_two = f"synthetic-{uuid.uuid4().hex}"
    first = client.post(f"/api/student/articles/{article_id}/view", json={"viewer_id": viewer_one})
    second = client.post(f"/api/student/articles/{article_id}/view", json={"viewer_id": viewer_one})
    third = client.post(f"/api/student/articles/{article_id}/view", json={"viewer_id": viewer_two})
    assert first.status_code == second.status_code == third.status_code == 200
    assert first.json()["counted"] is True
    assert second.json()["counted"] is False
    assert third.json()["counted"] is True
    with sessions() as db:
        assert db.query(models.Article.views).filter_by(id=article_id).scalar() == 102
