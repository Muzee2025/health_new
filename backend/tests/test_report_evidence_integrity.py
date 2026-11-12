"""Reports must not invent observations or hide local-rule fallbacks."""
import asyncio
import importlib
import json
from datetime import datetime, timedelta, timezone
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.routers import advanced_chat, assistant_v1, llm_gateway, report_v1, student, teacher
from app.services import dialogue_analysis_service as analysis


@pytest.fixture
def db(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "report-evidence.db").as_posix())
    models.Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        session.add_all([models.User(id=1, username="synthetic-1", password_hash="unused", role="student"),
                         models.User(id=2, username="synthetic-2", password_hash="unused", role="student")])
        session.commit()
        yield session
    engine.dispose()


def add_message(db, session_id, user_id, text, timestamp, tags=None):
    if db.get(models.AIChatSession, session_id) is None:
        db.add(models.AIChatSession(id=session_id, user_id=user_id, created_at=timestamp))
        db.flush()
    db.add(models.AIChatMessage(session_id=session_id, role="ai", content=text,
                               created_at=timestamp, emotion_tags=json.dumps(tags) if tags is not None else None))
    db.commit()


def test_no_messages_produce_no_scores_or_inferred_risk(db):
    result = analysis.build_structured_report(db, 1)
    assert result["data_status"] == "insufficient"
    assert result["generation"] == {"source": "local_rules", "status": "insufficient", "model_id": None}
    assert result["source"]["message_count"] == 0
    assert all(value is None for value in result["scores"].values())
    assert result["risk"]["risk_level"] == "UNKNOWN"
    assert result["risk"]["suicide_confidence"] is None
    assert result["trends"]["heatmap"] == []
    assert all(row["score"] is None and row["sample_count"] == 0 for row in result["trends"]["seven_days"])


def test_recent_window_is_global_ordered_and_user_scoped(db):
    now = datetime.now(timezone.utc)
    add_message(db, "newer-session", 1, "new", now)
    add_message(db, "older-session", 1, "old", now - timedelta(days=1))
    add_message(db, "other-user", 2, "must-not-appear", now)
    assert [row["content"] for row in analysis._collect_messages(db, 1)] == ["old", "new"]
    assert [row["content"] for row in analysis._collect_messages(db, 1, max_messages=1)] == ["new"]


@pytest.mark.parametrize("tags", [[1], {"joy": "invalid"}, {"fear": float("nan")}, {"sadness": 2}])
def test_invalid_stored_tags_are_not_converted_to_zero_health_scores(tags):
    assert analysis._score_from_message({"emotion_tags": tags}) is None


def test_rule_fallback_cannot_infer_disease_from_prompt_instructions():
    result = llm_gateway._generate(llm_gateway.GenerateRequest(prompt="risk_level 抑郁 自杀 焦虑"))
    assert result["source"] == "local_rules" and result["status"] == "fallback"
    decoded = json.loads(result["text"])
    assert decoded["risk_level"] == "UNKNOWN" and decoded["depression_confidence"] is None


def test_optional_report_provider_receives_only_aggregate_facts(monkeypatch):
    messages = [{"content": "PRIVATE-CONTENT-SENTINEL", "session_id": "PRIVATE-ID", "emotion_tags": {"joy": 0.4}}]
    monkeypatch.setenv("REPORT_AI_ENABLED", "true")
    monkeypatch.setattr(analysis, "LLM_URL", "https://synthetic.invalid/explain")
    captured = []
    def post(url, **kwargs):
        captured.append(kwargs["json"])
        return SimpleNamespace(status_code=200, json=lambda: {
            "text": json.dumps({"summary": "仅依据记录数量说明范围", "interventions": ["按需寻求支持"]}),
            "model_id": "synthetic-model-version"})
    monkeypatch.setattr(analysis.requests, "post", post)
    result = analysis._llm_analyze(messages)
    assert result["_generation"]["source"] == "provider"
    assert result["_generation"]["model_id"] == "synthetic-model-version"
    assert "PRIVATE-CONTENT-SENTINEL" not in json.dumps(captured)
    assert "PRIVATE-ID" not in json.dumps(captured)


def test_disabled_provider_never_connects(monkeypatch):
    monkeypatch.delenv("REPORT_AI_ENABLED", raising=False)
    monkeypatch.setattr(analysis.requests, "post", lambda *a, **k: pytest.fail("unexpected external call"))
    result = analysis._llm_analyze([{"content": "synthetic"}])
    assert result["_generation"]["source"] == "local_rules"


def test_force_does_not_duplicate_inflight_report_job(monkeypatch):
    monkeypatch.setattr(analysis, "ANALYSIS_JOBS", {1: {"status": "running"}})
    monkeypatch.setattr(analysis, "Thread", lambda *a, **k: pytest.fail("duplicate worker"))
    assert analysis.enqueue_dialogue_analysis(1, force=True)["status"] == "running"


def test_five_dimensions_not_invented_from_single_measurement(db):
    db.add(models.TestResult(user_id=1, test_type="SDS", score=50, result_json="{}"))
    db.commit()
    result = assistant_v1.get_risk_factor_five_dimension(db, db.get(models.User, 1))
    assert result["data"] is None and result["data_status"] == "insufficient"


def test_teacher_does_not_turn_dialogue_tags_into_test_or_risk_scores(db):
    teacher_user = models.User(id=3, username="synthetic-teacher", password_hash="unused", role="teacher")
    db.add(teacher_user)
    db.flush()
    db.add(models.TeacherStudentAssignment(teacher_id=3, student_id=1))
    db.commit()
    add_message(db, "tagged", 1, "synthetic", datetime.now(timezone.utc), {"sadness": 1, "fear": 1, "anger": 1})
    rows = teacher.get_students(db, teacher_user)
    assert len(rows) == 1 and rows[0].id == 1
    assert rows[0].risk_level is None and rows[0].latest_test_score is None


def test_empty_student_dashboard_has_no_perfect_health_score(db):
    result = student.get_dashboard_stats(db, db.get(models.User, 1))
    assert result["emotion_index"] is None


@pytest.mark.parametrize("message_count", [0, 1, 6])
def test_chat_analysis_has_only_real_ordered_points(db, monkeypatch, message_count):
    now = datetime.now(timezone.utc)
    for i in range(message_count):
        add_message(db, f"session-{i % 2}", 1, f"synthetic-{i}", now - timedelta(minutes=message_count - i), {"joy": 0.3})
    async def fake_report(logs):
        return {"source": "local_rule", "status": "fallback", "overall_status": "本地说明"}
    monkeypatch.setattr(advanced_chat.qwen_service, "generate_report_from_chats", fake_report)
    result = asyncio.run(advanced_chat.get_chat_based_report(db, db.get(models.User, 1)))
    trend = result["data"]["trend_data"]
    assert len(trend["joy"]) == message_count
    assert trend["dates"] == sorted(trend["dates"])
    assert result["data"]["risk_level"] == "待人工评估"


def test_empty_interpretation_is_terminal_not_permanent_loading(db):
    result = report_v1.generate_ai_interpret(report_v1.AiInterpretRequest(recordId=0), db, db.get(models.User, 1))
    assert result["status"] == "insufficient" and result["source"] == "local_rules"
    assert "生成中" not in result["text"]


def test_legacy_summary_discloses_local_source_when_rag_fails(db, monkeypatch):
    from app.services import rag_service
    def fail(**kwargs):
        raise RuntimeError("synthetic-private-detail")
    monkeypatch.setattr(rag_service, "query_rag", fail)
    result, _, _ = student._generate_report_analysis_payload(db, db.get(models.User, 1))
    assert result["generation"]["source"] == "local_rules"
    assert result["generation"]["status"] == "insufficient"
    assert "未调用外部模型" in result["ai_analysis"]


def test_old_report_without_provenance_is_marked_unverified():
    result = analysis.ensure_chart_explanations({"generated_mode": "full", "risk": {"risk_level": "HIGH"}})
    assert result["generation"]["status"] == "unverified" and result["data_status"] == "insufficient"


def test_collaboration_rejects_before_queue_or_external_calls(db, monkeypatch):
    monkeypatch.delenv("AI_EXTERNAL_ENABLED", raising=False)
    monkeypatch.delenv("REPORT_AI_ENABLED", raising=False)
    async def fail(*args):
        pytest.fail("disabled feature must not queue a model task")
    monkeypatch.setattr(report_v1.orchestrator, "submit_task", fail)
    with pytest.raises(HTTPException) as error:
        asyncio.run(report_v1.submit_collab_analysis(report_v1.MultiModelSubmitRequest(), db, db.get(models.User, 1)))
    assert error.value.status_code == 503


def test_unvalidated_multimodal_fusion_stays_disabled_even_with_provider_flags(monkeypatch):
    monkeypatch.setenv("AI_EXTERNAL_ENABLED", "true")
    monkeypatch.setenv("REPORT_AI_ENABLED", "true")
    assert report_v1._collaboration_enabled() is False


@pytest.mark.parametrize("fail_save", [False, True])
def test_crisis_reply_has_no_invented_contact_and_tracks_persistence(db, monkeypatch, fail_save):
    user = db.get(models.User, 1)
    db.add(models.AIChatSession(id="crisis-case", user_id=1, title="合成会话"))
    db.commit()
    async def analysis_result(message):
        return {"emotion_tags": {}, "keywords": [], "is_crisis": True, "attention_heatmap": [], "risk_radar": {}}
    async def broadcast(*args, **kwargs):
        return None
    monkeypatch.setattr(advanced_chat, "_emotion_pipeline", analysis_result)
    monkeypatch.setattr(advanced_chat.manager, "broadcast_to_teachers", broadcast)
    if fail_save:
        def fail():
            raise RuntimeError("synthetic-storage-error")
        monkeypatch.setattr(db, "commit", fail)
    response = asyncio.run(advanced_chat.ai_chat_interaction(
        advanced_chat.ChatRequest(session_id="crisis-case", message="合成的危机分支测试"), BackgroundTasks(), db, user))
    assert response.is_crisis
    assert response.warning_state == ("not_created" if fail_save else "created")
    assert "400-" not in response.reply and "24小时" not in response.reply and "就在等" not in response.reply
    assert db.query(models.CrisisWarning).count() == (0 if fail_save else 1)


def test_crisis_stream_storage_failure_keeps_support_message_and_not_created_state(db, monkeypatch):
    user = db.get(models.User, 1)
    db.add(models.AIChatSession(id="crisis-stream", user_id=1, title="合成会话"))
    db.commit()
    async def analysis_result(message):
        return {"emotion_tags": {}, "keywords": [], "is_crisis": True, "attention_heatmap": [], "risk_radar": {}}
    def fail():
        raise RuntimeError("synthetic-storage-error")
    monkeypatch.setattr(advanced_chat, "_emotion_pipeline", analysis_result)
    monkeypatch.setattr(db, "commit", fail)
    async def consume():
        response = await advanced_chat.ai_chat_stream(advanced_chat.ChatRequest(session_id="crisis-stream", message="合成安全分支测试"), BackgroundTasks(), db, user)
        return ''.join([chunk async for chunk in response.body_iterator])
    stream = asyncio.run(consume())
    final = json.loads(stream.split('event: done\ndata: ')[-1].strip())
    assert final['warning_state'] == 'not_created' and final['is_crisis']
    assert final['reply'] == advanced_chat.CRISIS_SUPPORT_MESSAGE
    assert 'event: error' not in stream
    assert db.query(models.CrisisWarning).count() == 0


def test_unimplemented_image_parser_never_reports_fabricated_features(monkeypatch):
    async def read_validated_file(file):
        return b"synthetic-validated-file"
    monkeypatch.setattr(advanced_chat, "read_image_upload", read_validated_file)
    monkeypatch.setattr(advanced_chat.nlp_engine, "extract_image_emotion_clip", lambda: pytest.fail("placeholder extraction must not execute"))
    with pytest.raises(HTTPException) as error:
        asyncio.run(advanced_chat.upload_image_or_audio(UploadFile(filename="synthetic.png", file=BytesIO(b"synthetic")), "image", models.User(id=1, role="student")))
    assert error.value.status_code == 503


class MemoryIndex:
    def __init__(self):
        self.rows = {}
        self.fail_delete = False
    def delete(self, where):
        if self.fail_delete:
            raise RuntimeError("synthetic-private-error")
        self.rows = {key: row for key, row in self.rows.items() if row[1]["doc_id"] != where["doc_id"]}
    def upsert(self, documents, metadatas, ids):
        self.rows.update(
            {
                key: (document, metadata)
                for key, document, metadata in zip(ids, documents, metadatas, strict=True)
            }
        )
    def count(self):
        return len(self.rows)
    def query(self, **kwargs):
        rows = list(self.rows.values())[:kwargs["n_results"]]
        return {"documents": [[row[0] for row in rows]], "metadatas": [[row[1] for row in rows]]}


def test_shortening_and_emptying_rag_document_removes_stale_tail(monkeypatch):
    from app.services import rag_service
    rag = importlib.reload(rag_service)
    index = MemoryIndex()
    monkeypatch.setattr(rag, "_get_collection", lambda: index)
    assert rag.add_document_to_rag(77, "Synthetic", "x" * 1200)
    assert len(index.rows) > 1
    assert rag.add_document_to_rag(77, "Synthetic", "short")
    assert len(index.rows) == 1
    assert "short" in rag.query_rag("synthetic")
    assert rag.add_document_to_rag(77, "Synthetic", "") and not index.rows


def test_failed_rag_removal_is_not_served_from_this_process(monkeypatch):
    from app.services import rag_service
    rag = importlib.reload(rag_service)
    index = MemoryIndex()
    monkeypatch.setattr(rag, "_get_collection", lambda: index)
    assert rag.add_document_to_rag(77, "Synthetic", "stale")
    index.fail_delete = True
    assert rag.delete_document_from_rag(77) is False
    assert rag.query_rag("synthetic") == ""
