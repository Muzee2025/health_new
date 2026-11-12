import os
import sys
import tempfile
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
from app.routers import advanced_chat, advanced_teacher
from app.routers.auth import get_current_user
from app.utils.websocket_manager import manager as ws_manager


def _build_test_app():
    db_url = f"sqlite:///{tempfile.NamedTemporaryFile(prefix='crisis_', suffix='.db', delete=False).name}"
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(advanced_chat.router, prefix="/api/advanced-ai")
    app.include_router(advanced_teacher.router, prefix="/api/advanced-teacher")

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return app, TestingSessionLocal


@pytest.fixture()
def test_context():
    app, TestingSessionLocal = _build_test_app()
    db = TestingSessionLocal()
    student = models.User(id=101, username="stu", password_hash="x", role="student", name="李明", class_name="计科1班")
    teacher = models.User(id=201, username="tea", password_hash="x", role="teacher", name="王老师")
    db.add_all([student, teacher])
    db.commit()
    db.add(models.TeacherStudentAssignment(teacher_id=teacher.id, student_id=student.id))
    db.commit()
    session = models.AIChatSession(id="s-001", user_id=student.id, mode="daily", title="测试会话")
    db.add(session)
    db.commit()
    db.close()
    yield app, TestingSessionLocal, student, teacher, session.id


def test_crisis_keyword_trigger_rate_and_teacher_delivery(test_context, monkeypatch):
    app, TestingSessionLocal, student, _, session_id = test_context
    delivered_payloads: List[dict] = []

    async def fake_broadcast(message: dict, *, db, student_id):
        assert student_id == student.id
        delivered_payloads.append(message)

    monkeypatch.setattr(advanced_chat.manager, "broadcast_to_teachers", fake_broadcast)

    def override_get_current_user_student():
        return student

    app.dependency_overrides[get_current_user] = override_get_current_user_student
    client = TestClient(app)

    phrases = [
        "我想要跳楼",
        "我不想活了",
        "我想自杀",
        "我准备轻生",
        "我想结束生命",
        "我想一了百了",
        "我想死",
        "我今天去死算了",
        "我准备割腕",
        "我准备服毒",
        "我想上吊",
        "想跳楼解脱",
        "真的不想活了",
        "我有轻生念头",
        "我想结束这一切",
        "我要自杀了",
        "我不想再活下去",
        "今天就去跳楼",
        "想去死",
        "我想一死了之",
    ]

    hit = 0
    for text in phrases:
        res = client.post(
            "/api/advanced-ai/chat",
            json={
                    "session_id": session_id,
                "message": text,
                "anonymous": False,
                "deep_think": False,
                "mode": "daily",
            },
        )
        assert res.status_code == 200
        if res.json().get("is_crisis") is True:
            hit += 1

    trigger_rate = hit / len(phrases)
    assert trigger_rate >= 0.95

    db = TestingSessionLocal()
    pending = db.query(models.CrisisWarning).filter(models.CrisisWarning.student_id == student.id).all()
    db.close()
    assert len(pending) == hit

    # 广播到达率: 每次触发都广播一条
    delivery_rate = len(delivered_payloads) / max(hit, 1)
    assert delivery_rate == 1.0
    assert all(p.get("type") == "new_warning" for p in delivered_payloads)


def test_teacher_process_warning_sync_flow(test_context, monkeypatch):
    app, TestingSessionLocal, student, teacher, session_id = test_context
    to_student_payloads: List[dict] = []

    async def fake_broadcast(_: dict, *, db, student_id):
        assert student_id == student.id
        return None

    async def fake_personal(message: dict, user_id: int, role: str):
        to_student_payloads.append({"message": message, "user_id": user_id, "role": role})

    monkeypatch.setattr(advanced_chat.manager, "broadcast_to_teachers", fake_broadcast)
    monkeypatch.setattr(ws_manager, "send_personal_message", fake_personal)

    def as_student():
        return student

    def as_teacher():
        return teacher

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

    app.dependency_overrides[get_current_user] = as_teacher
    list_res = client.get("/api/advanced-teacher/warnings")
    assert list_res.status_code == 200
    rows = list_res.json()["data"]
    assert len(rows) >= 1
    wid = rows[0]["id"]

    proc_res = client.post(f"/api/advanced-teacher/warnings/{wid}/process",
                           json={"action": "pass", "reason": "Synthetic human review"})
    assert proc_res.status_code == 200

    new_rows = client.get("/api/advanced-teacher/warnings").json()["data"]
    target = [x for x in new_rows if x["id"] == wid][0]
    assert target["status"] == "processed"
    assert target["processed_by"] == teacher.name

    assert len(to_student_payloads) == 1
    assert to_student_payloads[0]["user_id"] == student.id
    assert to_student_payloads[0]["role"] == "student"
    assert "reason" not in to_student_payloads[0]["message"].get("data", {})
    with TestingSessionLocal() as db:
        event = db.query(models.SupportWorkflowEvent).filter_by(
            subject_type="crisis_warning", subject_id=wid).one()
        assert event.action == "pass"
        assert event.reason == "Synthetic human review"

