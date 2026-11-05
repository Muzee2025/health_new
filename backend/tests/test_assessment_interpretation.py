"""Interpretation must bind to the requested owned assessment and disclose fallback."""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, get_db
from app.main import app
from app.routers.auth import get_current_user


@pytest.fixture()
def interpretation_client(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'interpretation.sqlite3').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add_all([
            models.User(id=8811, username="synthetic-owner", role="student", password_hash="unused"),
            models.User(id=8812, username="synthetic-other", role="student", password_hash="unused"),
        ])
        db.add_all([
            models.TestResult(id=9911, user_id=8811, test_type="SDS", score=43, standard_score=53,
                result_level="待专业复核", answers=json.dumps({"0": 1}),
                result_json=json.dumps({"provenance": {"scoring_version": "health-new-muzee2025-assessment-engine-2026-10-31-v1",
                    "eligibility": "pending_professional_review", "form_version": "question-bank-2026-10-31-v1",
                    "form_hash": "synthetic-form-hash", "question_bank_source_sha256": "synthetic-source-hash"}})),
            models.TestResult(id=9912, user_id=8811, test_type="SAS", score=40, standard_score=50,
                result_level="旧结论", answers="{}", result_json="[]"),
            models.TestResult(id=9914, user_id=8811, test_type="SDS", score=40, standard_score=50,
                result_level="旧结论", answers="{}", result_json='{"provenance":[]}'),
            models.TestResult(id=9913, user_id=8812, test_type="SDS", score=40, standard_score=50,
                result_level="待专业复核", answers="{}", result_json="{}"),
        ])
        db.commit()
    identity = {"id": 8811}
    def current_user():
        return models.User(id=identity["id"], username="synthetic", role="student")
    def database():
        with sessions() as db:
            yield db
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = current_user
    try:
        with TestClient(app) as client:
            yield client, identity
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        engine.dispose()


def test_analysis_requires_id_and_returns_structured_local_fallback(interpretation_client, monkeypatch):
    client, _ = interpretation_client
    monkeypatch.delenv("AI_EXTERNAL_ENABLED", raising=False)
    missing_id = client.post("/api/student/tests/ai-analyze", json={})
    response = client.post("/api/student/tests/ai-analyze", json={"test_id": 9911})
    assert missing_id.status_code == 422
    assert response.status_code == 200
    data = response.json()
    assert data["test_id"] == 9911
    assert data["status"] == "fallback"
    assert data["source"] == "local_rule"
    assert data["model_id"] is None
    assert set(data["content"]) == {"summary", "observations", "limitations", "next_steps"}
    assert "非大模型" in data["notice"]


def test_old_history_is_explicitly_unknown_and_never_latest_fallback(interpretation_client):
    client, identity = interpretation_client
    unknown = client.post("/api/student/tests/ai-analyze", json={"test_id": 9912}).json()
    malformed_provenance = client.post("/api/student/tests/ai-analyze", json={"test_id": 9914}).json()
    missing = client.post("/api/student/tests/ai-analyze", json={"test_id": 123456})
    report = client.get("/api/student/report/analysis")
    identity["id"] = 8812
    foreign = client.post("/api/student/tests/ai-analyze", json={"test_id": 9911})
    assert "版本未知" in unknown["content"]["summary"]
    assert "版本未知" in malformed_provenance["content"]["summary"]
    assert missing.status_code == 404
    assert report.status_code == 200
    assert foreign.status_code == 404


def test_report_basis_does_not_claim_normative_judgment(interpretation_client, monkeypatch):
    client, _ = interpretation_client
    monkeypatch.delenv("AI_EXTERNAL_ENABLED", raising=False)
    response = client.get("/api/student/report/analysis")
    assert response.status_code == 200
    logic = " ".join(response.json()["analysis_basis"]["logic_path"])
    assert "常模与解释待专业复核" in logic
    assert "对照常模标准判定" not in logic


def test_extra_request_fields_are_rejected(interpretation_client):
    client, _ = interpretation_client
    response = client.post("/api/student/tests/ai-analyze", json={"test_id": 9911, "answers": {"0": 4}})
    assert response.status_code == 422


@pytest.mark.parametrize("test_id", ["9911", True, 0, -1])
def test_test_id_must_be_positive_strict_integer(interpretation_client, test_id):
    client, _ = interpretation_client
    assert client.post("/api/student/tests/ai-analyze", json={"test_id": test_id}).status_code == 422


class _FakeCompletions:
    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.error:
            raise self.error
        from types import SimpleNamespace
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], model="fake-qwen-version")


class _FakeClient:
    def __init__(self, completions):
        from types import SimpleNamespace
        self.chat = SimpleNamespace(completions=completions)


@pytest.mark.parametrize("provider_content,expected_status", [
    ('{"summary":"说明","observations":["观察"],"limitations":["非诊断"],"next_steps":["可选建议"]}', "completed"),
    ("not-json", "fallback"),
    ('{"summary":"","observations":[],"limitations":[],"next_steps":[]}', "fallback"),
    ('{"summary":"说明","observations":[7],"limitations":[],"next_steps":[]}', "fallback"),
])
def test_fake_provider_is_validated_minimized_and_has_real_metadata(interpretation_client, monkeypatch, provider_content, expected_status):
    from app.routers import student
    client, _ = interpretation_client
    monkeypatch.setenv("AI_EXTERNAL_ENABLED", "1")
    fake_calls = _FakeCompletions(content=provider_content)
    monkeypatch.setattr(student, "qwen_client", _FakeClient(fake_calls))
    response = client.post("/api/student/tests/ai-analyze", json={"test_id": 9911})
    data = response.json()
    assert response.status_code == 200
    assert data["status"] == expected_status
    assert data["model_id"] == ("fake-qwen-version" if expected_status == "completed" else None)
    assert data["sources"][0]["type"] == "scoring_provenance"
    assert data["sources"][0]["external"] is False
    assert isinstance(data["sources"][0]["question_bank_source_sha256"], str)
    sent = fake_calls.requests[0]["messages"][1]["content"]
    assert '"answers"' not in sent
    assert "synthetic-owner" not in sent
    assert "student_id" not in sent
    assert "8811" not in sent


def test_fake_provider_exception_degrades_to_local_rule(interpretation_client, monkeypatch):
    from app.routers import student
    client, _ = interpretation_client
    monkeypatch.setenv("AI_EXTERNAL_ENABLED", "1")
    monkeypatch.setattr(student, "qwen_client", _FakeClient(_FakeCompletions(error=TimeoutError("synthetic timeout"))))
    data = client.post("/api/student/tests/ai-analyze", json={"test_id": 9911}).json()
    assert data["status"] == "fallback"
    assert data["source"] == "local_rule"
    assert data["model_id"] is None


def test_chat_report_sends_only_count_and_validates_provider_shape(monkeypatch):
    import asyncio
    from app.services import qwen_service
    expected = {"overall_status": "仅有条数信息，无法据此判断心理状态。", "chart_interpretations": {
        "emotion_trend": "资料不足。", "stress_index": "资料不足。", "risk_level": "资料不足。"}}
    calls = _FakeCompletions(content=json.dumps(expected, ensure_ascii=False))
    monkeypatch.setattr(qwen_service, "client", _FakeClient(calls))
    result = asyncio.run(qwen_service.QwenAiService().generate_report_from_chats(["PRIVATE_NAME_SENTINEL 真实树洞原文", "PRIVATE_ID_SENTINEL 对话文本"]))
    sent = calls.requests[0]["messages"][1]["content"]
    assert "PRIVATE_NAME_SENTINEL" not in sent
    assert "PRIVATE_ID_SENTINEL" not in sent
    assert "真实树洞原文" not in sent
    assert json.loads(sent)["record_count"] == 2
    assert result["source"] == "provider"
    assert result["model_id"] == "fake-qwen-version"

    malformed_calls = _FakeCompletions(content='{"overall_status":"资料不足。","chart_interpretations":{"emotion_trend":"资料不足。","stress_index":"资料不足。"}}')
    monkeypatch.setattr(qwen_service, "client", _FakeClient(malformed_calls))
    malformed = asyncio.run(qwen_service.QwenAiService().generate_report_from_chats(["SENTINEL content"]))
    assert malformed["status"] == "fallback"
    assert malformed["source"] == "local_rule"
    assert malformed["model_id"] is None
