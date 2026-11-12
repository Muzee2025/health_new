import asyncio
import os
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import models
from app.routers import report_v1
from app.routers.auth import get_current_user
from app.services import multi_model_orchestrator as mm


class _FakeUsage:
    prompt_tokens = 10
    completion_tokens = 6
    total_tokens = 16


class _FakeChoiceMsg:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeChoiceMsg(content)


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage()


class _AlwaysPrimaryFailClient:
    class _Completions:
        async def create(self, model=None, **kwargs):
            if model == mm.PRIMARY_TEXT_MODEL:
                raise RuntimeError("upstream timeout")
            return _FakeResponse('{"summary":"fallback ok","confidence":0.61,"detail":{"src":"fallback"}}')

    class _Chat:
        def __init__(self):
            self.completions = _AlwaysPrimaryFailClient._Completions()

    def __init__(self):
        self.chat = _AlwaysPrimaryFailClient._Chat()


class _AlwaysSuccessClient:
    class _Completions:
        async def create(self, model=None, **kwargs):
            return _FakeResponse('{"summary":"ok","confidence":0.82,"detail":{"model":"ok"}}')

    class _Chat:
        def __init__(self):
            self.completions = _AlwaysSuccessClient._Completions()

    def __init__(self):
        self.chat = _AlwaysSuccessClient._Chat()


def test_primary_fallback_marked_done_and_does_not_open_circuit(monkeypatch):
    monkeypatch.setattr(mm, "qwen_client", _AlwaysPrimaryFailClient())
    monkeypatch.setattr(mm, "MODEL_FAILURE_WINDOW_SEC", 300)
    monkeypatch.setattr(mm, "PRIMARY_CIRCUIT_MIN_SAMPLES", 3)
    monkeypatch.setattr(mm, "PRIMARY_CIRCUIT_ERROR_RATE", 0.34)
    monkeypatch.setattr(mm, "PRIMARY_CIRCUIT_CONSECUTIVE", 2)
    monkeypatch.setattr(mm, "PRIMARY_CIRCUIT_COOLDOWN_SEC", 60)

    orchestrator = mm.MultiModelOrchestrator()
    model = {"id": mm.PRIMARY_TEXT_MODEL, "stage": "x", "etaSec": 1, "qps": 10.0, "timeout": 5}
    payload = {"messages": [{"role": "user", "content": "test"}]}
    context = {}
    task_id = "t-circuit"
    orchestrator._tasks[task_id] = {"events": [], "updated_at": "", "status": "running"}

    for _ in range(4):
        result, cached = asyncio.run(orchestrator._call_with_retry(model, payload, context, task_id))
        assert cached is False
        assert result["status"] == "done"
        assert result["fallback_used"] is True

    metrics = orchestrator.get_metrics()
    assert not any(a.get("type") == "model_circuit_open" for a in metrics.get("alerts", []))
    assert metrics["models"][mm.PRIMARY_TEXT_MODEL]["circuit_open"] is False


class _AlwaysTimeoutClient:
    class _Completions:
        async def create(self, model=None, **kwargs):
            # 故意慢于 wait_for timeout，模拟上游卡住。
            await asyncio.sleep(0.05)
            return _FakeResponse('{"summary":"late","confidence":0.51,"detail":{"src":"late"}}')

    class _Chat:
        def __init__(self):
            self.completions = _AlwaysTimeoutClient._Completions()

    def __init__(self):
        self.chat = _AlwaysTimeoutClient._Chat()


def test_primary_timeout_soft_fallback_returns_done_fast(monkeypatch):
    monkeypatch.setattr(mm, "qwen_client", _AlwaysTimeoutClient())
    monkeypatch.setattr(mm, "MODEL_RETRY_ATTEMPTS", 3)
    monkeypatch.setattr(mm, "PRIMARY_TIMEOUT_SOFT_FALLBACK", True)

    orchestrator = mm.MultiModelOrchestrator()
    model = {"id": mm.PRIMARY_TEXT_MODEL, "stage": "x", "etaSec": 1, "qps": 10.0, "timeout": 0.01}
    payload = {"messages": [{"role": "user", "content": "test timeout fallback"}]}
    context = {}
    task_id = "t-timeout-soft-fallback"
    orchestrator._tasks[task_id] = {"events": [], "updated_at": "", "status": "running"}

    result, cached = asyncio.run(orchestrator._call_with_retry(model, payload, context, task_id))
    assert cached is False
    assert result["status"] == "done"
    assert result["fallback_used"] is True
    assert result["api_model"] == mm.PRIMARY_MODEL_FALLBACK
    assert any("primary_timeout_soft_fallback" in evt for evt in orchestrator._tasks[task_id]["events"])


def test_primary_success_does_not_false_degrade(monkeypatch):
    monkeypatch.setattr(mm, "qwen_client", _AlwaysSuccessClient())

    orchestrator = mm.MultiModelOrchestrator()
    model = {"id": mm.PRIMARY_TEXT_MODEL, "stage": "x", "etaSec": 1, "qps": 10.0, "timeout": 5}
    payload = {"messages": [{"role": "user", "content": "normal"}]}
    context = {}
    task_id = "t-ok"
    orchestrator._tasks[task_id] = {"events": [], "updated_at": "", "status": "running"}

    result, _ = asyncio.run(orchestrator._call_with_retry(model, payload, context, task_id))
    assert result["status"] == "done"
    assert result["api_model"] == mm.PRIMARY_TEXT_MODEL
    assert orchestrator.get_metrics()["models"][mm.PRIMARY_TEXT_MODEL]["error_rate"] == 0.0


def test_run_task_integration_with_guard_and_metrics(monkeypatch):
    monkeypatch.setattr(mm, "qwen_client", _AlwaysSuccessClient())
    monkeypatch.setattr(
        mm,
        "MODEL_CHAIN",
        [
            {"id": mm.PRIMARY_TEXT_MODEL, "stage": "文本理解与逻辑推理", "etaSec": 1, "qps": 10.0, "timeout": 5},
            {"id": "emohaa", "stage": "情感倾向分析", "etaSec": 1, "qps": 10.0, "timeout": 5},
        ],
    )

    orchestrator = mm.MultiModelOrchestrator()

    async def _fake_emohaa(payload, context, text):
        return {
            "summary": "情绪稳定",
            "confidence": 0.7,
            "detail": {"emotion_tags": {"calm": 0.7}},
            "api_model": "emohaa",
            "requested_model": "emohaa",
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            "status": "done",
        }

    monkeypatch.setattr(orchestrator, "_invoke_emohaa_real", _fake_emohaa)

    task_id = "t-int"
    orchestrator._tasks[task_id] = {
        "task_id": task_id,
        "user_id": 1,
        "status": "queued",
        "created_at": mm._utc_now(),
        "updated_at": mm._utc_now(),
        "progress": 0,
        "payload": {"messages": [{"role": "user", "content": "最近焦虑但可控"}]},
        "events": [],
        "context": {},
        "result": None,
        "error": "",
    }

    asyncio.run(orchestrator._run_task(task_id))
    task = orchestrator.get_task(task_id)
    assert task is not None
    assert task["status"] == "done"
    assert task["result"]["confidence"] > 0
    assert task["result"]["modelResults"][0]["model"] == mm.PRIMARY_TEXT_MODEL


def test_collab_health_endpoint_exposes_metrics(monkeypatch):
    app = FastAPI()
    app.include_router(report_v1.router)

    def _fake_user():
        return models.User(id=1, username="u", password_hash="x", role="student")

    app.dependency_overrides[get_current_user] = _fake_user
    monkeypatch.setattr(report_v1, "orchestrator", mm.MultiModelOrchestrator())

    client = TestClient(app)
    resp = client.get("/api/v1/report/analysis/collab/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "metrics" in body
    assert "models" in body["metrics"]
