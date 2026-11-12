import os
import sys
import json
import tempfile
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import models
from app.database import get_db
from app.routers import advanced_chat
from app.routers.auth import get_current_user


def _build_test_app():
    db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    db_file.close()
    engine = create_engine(
        f"sqlite:///{db_file.name}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    app = FastAPI()
    app.include_router(advanced_chat.router, prefix="/api/advanced-ai")

    def override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_user():
        db = session_local()
        try:
            user = db.query(models.User).filter(models.User.id == 1).first()
            if not user:
                user = models.User(
                    id=1,
                    username="student",
                    password_hash="x",
                    role="student",
                    name="李明",
                    class_name="软件1班",
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            return user
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return app


def test_deep_think_stream_emits_three_phases_and_done(monkeypatch):
    async def _fake_deep_think_with_student(
        user_id: str,
        prompt: str,
        chat_context: str,
        mode: str = "daily",
        trace_id: str | None = None,
    ) -> str:
        return "这是一段用于测试的深度思考回复内容。"

    # monkeypatch restores the real method after the test. Assigning it directly
    # left the fake installed for every later test in the same process.
    monkeypatch.setattr(advanced_chat.zhipu_chat_service, "deep_think_with_student", _fake_deep_think_with_student)

    app = _build_test_app()
    client = TestClient(app)
    created = client.post("/api/advanced-ai/sessions", json={"mode": "daily"})
    assert created.status_code == 200
    session_id = created.json()["session_id"]
    payload = {
        "session_id": session_id,
        "message": "我最近总是有点焦虑，想做一次深度思考",
        "modality": "text",
        "anonymous": False,
        "mode": "daily",
        "deep_think": True,
        "history": [],
    }
    resp = client.post("/api/advanced-ai/chat/stream", json=payload)
    assert resp.status_code == 200
    body = resp.text
    assert "event: phase\ndata: memory" in body
    assert "event: phase\ndata: trend" in body
    assert "event: phase\ndata: response" in body
    assert "event: memory_chunk" in body
    assert "event: trend_chunk" in body
    assert "event: message_chunk" in body
    assert "event: done" in body
    done_payload = body.split("event: done\ndata: ", 1)[1].split("\n\n", 1)[0]
    done_data = json.loads(done_payload)
    assert isinstance(done_data.get("reply"), str)
    assert done_data.get("reply")
    assert done_data.get("model_invoked") is True
    assert float(done_data.get("model_latency_ms", 0)) >= 0
    assert done_data.get("trace_id")
    assert "扩展反思" not in done_data["reply"]


def test_session_messages_filter_covers_full_day_range():
    app = _build_test_app()
    client = TestClient(app)
    created = client.post("/api/advanced-ai/sessions", json={"mode": "daily"})
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        db.add(
            models.AIChatMessage(
                session_id=session_id,
                role="user",
                content="4月12日凌晨消息",
                created_at=datetime(2024, 4, 12, 0, 0, 0),
            )
        )
        db.add(
            models.AIChatMessage(
                session_id=session_id,
                role="ai",
                content="4月12日晚间消息",
                created_at=datetime(2024, 4, 12, 23, 59, 59),
            )
        )
        db.add(
            models.AIChatMessage(
                session_id=session_id,
                role="user",
                content="4月13日消息",
                created_at=datetime(2024, 4, 13, 0, 0, 0),
            )
        )
        db.commit()
    finally:
        db.close()

    resp = client.get(f"/api/advanced-ai/sessions/{session_id}/messages", params={"target_date": "2024-04-12"})
    assert resp.status_code == 200
    rows = resp.json()["data"]
    texts = [x["content"] for x in rows]
    assert "4月12日凌晨消息" in texts
    assert "4月12日晚间消息" in texts
    assert "4月13日消息" not in texts


def test_history_query_supports_time_and_topic_filters():
    app = _build_test_app()
    client = TestClient(app)
    created = client.post("/api/advanced-ai/sessions", json={"mode": "daily"})
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        db.add(
            models.ChatHistoryArchive(
                user_id=1,
                session_id=session_id,
                user_input="我最近睡眠很差",
                ai_reply="你最近睡眠可能受压力影响",
                topic_tags="睡眠,压力",
                sentiment_score=46,
                semantic_summary="睡眠问题",
                created_at=datetime(2024, 4, 12, 9, 30, 0),
            )
        )
        db.add(
            models.ChatHistoryArchive(
                user_id=1,
                session_id=session_id,
                user_input="我今天心情不错",
                ai_reply="看到你状态回暖真好",
                topic_tags="情绪,积极",
                sentiment_score=72,
                semantic_summary="情绪好转",
                created_at=datetime(2024, 4, 13, 9, 30, 0),
            )
        )
        db.commit()
    finally:
        db.close()

    resp = client.get(
        "/api/advanced-ai/history/query",
        params={"start_date": "2024-04-12", "end_date": "2024-04-12", "topic_tag": "睡眠"},
    )
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert len(rows) == 1
    assert rows[0]["semantic_summary"] == "睡眠问题"


def test_delete_session_keeps_remote_local_integrity():
    app = _build_test_app()
    client = TestClient(app)
    created = client.post("/api/advanced-ai/sessions", json={"mode": "daily"})
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        msg = models.AIChatMessage(
            session_id=session_id,
            role="user",
            content="待删除消息",
        )
        db.add(msg)
        db.flush()
        db.add(
            models.ChatHistoryArchive(
                user_id=1,
                session_id=session_id,
                user_message_id=msg.id,
                ai_message_id=None,
                user_input="待删除输入",
                ai_reply="待删除回复",
                context_json="{}",
                topic_tags="删除",
                sentiment_score=60,
                semantic_summary="删除一致性",
            )
        )
        db.commit()
    finally:
        db.close()

    resp = client.delete(f"/api/advanced-ai/sessions/{session_id}")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "success"
    assert payload["data"]["session_id"] == session_id

    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        assert db.query(models.AIChatSession).filter(models.AIChatSession.id == session_id).count() == 0
        assert db.query(models.AIChatMessage).filter(models.AIChatMessage.session_id == session_id).count() == 0
        assert db.query(models.ChatHistoryArchive).filter(models.ChatHistoryArchive.session_id == session_id).count() == 0
    finally:
        db.close()
