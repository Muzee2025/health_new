import os
import sys
import tempfile
import time
from typing import List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import models
from app.database import get_db
from app.routers import advanced_chat, teacher
from app.routers.auth import get_current_user
from app.services.crisis_pending_service import load_mock_records, merge_pending_records


def _build_test_app():
    db_url = f"sqlite:///{tempfile.NamedTemporaryFile(prefix='teacher_crisis_', suffix='.db', delete=False).name}"
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(teacher.router)
    app.include_router(advanced_chat.router, prefix="/api/advanced-ai")

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return app, TestingSessionLocal


@pytest.fixture()
def context():
    app, TestingSessionLocal = _build_test_app()
    db = TestingSessionLocal()
    student = models.User(
        id=101,
        username="stu",
        password_hash="x",
        role="student",
        name="李明",
        student_id="2024002001",
        class_name="计科1班",
    )
    teacher_user = models.User(id=201, username="tea", password_hash="x", role="teacher", name="王老师")
    db.add_all([student, teacher_user])
    db.commit()
    db.add(models.TeacherStudentAssignment(teacher_id=teacher_user.id, student_id=student.id))
    db.commit()
    session = models.AIChatSession(id="s-001", user_id=student.id, mode="daily", title="测试会话")
    db.add(session)
    db.commit()
    db.close()
    yield app, TestingSessionLocal, student, teacher_user, session.id


def test_merge_records_no_duplicate_and_sorting():
    mock_rows = load_mock_records(include_reviewed=False)
    real_rows = [
        {
            "id": "real-1",
            "createdAt": "2026-04-20 10:00:00",
            "studentId": "2024009999",
            "riskLevel": "high",
            "description": "real-a",
            "status": "pending",
        },
        {
            "id": "real-2",
            "createdAt": "2026-04-19 10:00:00",
            "studentId": "2024008888",
            "riskLevel": "high",
            "description": "real-b",
            "status": "pending",
        },
        # 重复键，后者应覆盖前者
        {
            "id": "real-2",
            "createdAt": "2026-04-19 10:00:00",
            "studentId": "2024008888",
            "riskLevel": "high",
            "description": "real-b-overwrite",
            "status": "pending",
        },
    ]
    merged = merge_pending_records(mock_rows, real_rows)
    real_count = len([x for x in merged if x["id"].startswith("real-")])
    assert real_count == 2
    assert merged[0]["id"].startswith("real-")
    assert merged[1]["id"].startswith("real-")
    assert merged[0]["createdAt"] >= merged[1]["createdAt"]
    assert any(x["description"] == "real-b-overwrite" for x in merged)


def test_merge_records_perf_under_300ms():
    mock_rows = [
        {
            "id": f"mock-m-{i}",
            "createdAt": f"2026-04-{(i % 28) + 1:02d} 10:00:00",
            "studentId": f"mock-{i}",
            "riskLevel": "medium",
            "description": "m",
            "status": "pending",
        }
        for i in range(500)
    ]
    real_rows = [
        {
            "id": f"real-r-{i}",
            "createdAt": f"2026-04-{(i % 28) + 1:02d} 11:00:00",
            "studentId": f"real-{i}",
            "riskLevel": "high",
            "description": "r",
            "status": "pending",
        }
        for i in range(500)
    ]
    start = time.perf_counter()
    merged = merge_pending_records(mock_rows, real_rows)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert len(merged) == 1000
    assert elapsed_ms < 300


def test_pending_api_and_review_closed_loop(context, monkeypatch):
    app, _, student, teacher_user, session_id = context
    delivered_payloads: List[dict] = []

    async def fake_broadcast(message: dict, *, db, student_id):
        assert student_id == student.id
        delivered_payloads.append(message)

    monkeypatch.setattr(advanced_chat.manager, "broadcast_to_teachers", fake_broadcast)

    def as_student():
        return student

    def as_teacher():
        return teacher_user

    client = TestClient(app)

    app.dependency_overrides[get_current_user] = as_student
    res = client.post(
        "/api/advanced-ai/chat",
        json={
            "session_id": session_id,
            "message": "我想要跳楼",
            "anonymous": False,
            "deep_think": False,
            "mode": "daily",
        },
    )
    assert res.status_code == 200
    assert res.json()["is_crisis"] is True
    assert len(delivered_payloads) >= 1
    assert "source" not in delivered_payloads[-1]["data"]

    app.dependency_overrides[get_current_user] = as_teacher
    pending_res = client.get("/api/teacher/crisis/pending")
    assert pending_res.status_code == 200
    items = pending_res.json()["data"]["items"]
    assert len(items) >= 1
    assert all("createdAt" in x and "studentId" in x and "riskLevel" in x and "description" in x and "status" in x for x in items)
    assert all("source" not in x for x in items)
    assert len(items) == 1
    assert all(str(x["id"]).startswith("real-") for x in items)
    real_item = next(x for x in items if str(x["id"]).startswith("real-"))

    review_res = client.post(
        "/api/teacher/crisis/review",
        json={"recordId": real_item["id"], "action": "pass", "reason": "Synthetic human review"},
    )
    assert review_res.status_code == 200
    assert review_res.json()["data"]["status"] == "processed"
    assert review_res.json()["data"]["action"] == "pass"

    pending_after = client.get("/api/teacher/crisis/pending").json()["data"]["items"]
    assert all(x["id"] != real_item["id"] for x in pending_after)
