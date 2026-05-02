import os
import sys
import tempfile
import time

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


def test_deep_think_realtime_chain_happy_sad_normal():
    invoked = {"count": 0}

    async def _fake_emotion_pipeline(message: str):
        return {
            "emotion_tags": {"joy": 0.5, "sadness": 0.2, "neutral": 0.2, "fear": 0.05, "anxiety": 0.03, "anger": 0.02},
            "keywords": [],
            "attention_heatmap": [],
            "risk_radar": {},
            "is_crisis": False,
        }

    async def _fake_vector_recall(db, user_id, user_message, session_id, trace_id, top_k=3):
        return {
            "snippets": [f"历史片段-{user_message[:6]}"],
            "timings_ms": {"query": 1.0, "embedding": 1.0, "recall": 1.0, "total": 3.0},
            "topk": [{"score": 0.9, "session_id": "s1", "snippet": f"历史片段-{user_message[:6]}"}],
        }

    async def _fake_deep_think_with_student(user_id: str, prompt: str, chat_context: str, mode: str = "daily", trace_id: str | None = None):
        invoked["count"] += 1
        return f"emohaa实时推理输出 trace={trace_id} prompt={prompt[:10]}"

    advanced_chat._emotion_pipeline = _fake_emotion_pipeline
    advanced_chat._vector_retrieve_memories = _fake_vector_recall
    advanced_chat.zhipu_chat_service.deep_think_with_student = _fake_deep_think_with_student

    app = _build_test_app()
    client = TestClient(app)
    created = client.post("/api/advanced-ai/sessions", json={"mode": "daily"})
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    inputs = [
        "我今天很开心，拿了奖",
        "我现在有点难过和焦虑",
        "今天一般般，想聊聊天",
    ]
    forbidden_templates = [
        "先给你一个今天就能做的小方案",
        "不需要逼自己立刻振作",
        "先给情绪 20 分钟出口",
    ]

    for msg in inputs:
        started = time.perf_counter()
        resp = client.post(
            "/api/advanced-ai/chat",
            json={
                "session_id": session_id,
                "message": msg,
                "modality": "text",
                "anonymous": False,
                "mode": "daily",
                "deep_think": True,
                "history": [],
            },
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        assert resp.status_code == 200
        body = resp.json()
        assert body["model_invoked"] is True
        assert body["model_latency_ms"] < 2000
        assert elapsed_ms < 2000
        assert body.get("trace_id")
        assert "emohaa实时推理输出" in body["reply"]
        for t in forbidden_templates:
            assert t not in body["reply"]

    assert invoked["count"] == len(inputs)
