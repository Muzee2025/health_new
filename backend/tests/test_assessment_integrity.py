"""Server-side questionnaire scoring and tamper rejection on synthetic inputs."""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, get_db
from app.main import app
from app.routers.auth import get_current_user
from app.routers.student import (
    _assessment_is_current,
    _assessment_provenance,
    _score_assessment,
    _submission_id,
)
from app.schemas import TestSubmit


def test_sds_raw_options_are_reversed_once_and_marked_pending():
    answers = {str(i): 1 for i in range(20)}
    score, standard, level, risk, status, detail, normalized = _score_assessment("SDS", answers)
    assert score == 50  # ten reverse-keyed items are inverted by the server
    assert standard == 62
    assert level == "待专业复核"
    assert risk is None
    assert status == "pending_professional_review"
    assert normalized == answers
    assert detail["provenance"]["scoring_version"].endswith("v1")


@pytest.mark.parametrize("answers", [
    {str(i): 1 for i in range(19)},
    {**{str(i): 1 for i in range(20)}, "20": 1},
    {**{str(i): 1 for i in range(20)}, "0": True},
    {**{str(i): 1 for i in range(20)}, "0": 5},
])
def test_sds_rejects_missing_extra_boolean_and_out_of_range_answers(answers):
    # A bare `Exception` also passes when the scorer crashes for an unrelated
    # reason (a TypeError in a lookup, say), so the rejection has to be the one
    # the endpoint documents: a 422 about the answers themselves.
    with pytest.raises(HTTPException) as refused:
        _score_assessment("SDS", answers)
    assert refused.value.status_code == 422


def test_fun_tool_scoring_is_not_eligible_for_risk():
    answers = {str(i): "E" if i < 7 else "S" if i < 14 else "T" if i < 21 else "J" for i in range(28)}
    score, _, level, risk, status, _, _ = _score_assessment("MBTI", answers)
    assert (score, level, risk, status) == (100, "ESTJ", None, "entertainment_only")


def test_submit_rejects_client_supplied_score_fields():
    # Validation has to refuse the extra field specifically, not fail for any
    # reason at all (see the note above).
    with pytest.raises(ValidationError):
        TestSubmit(test_type="SDS", answers={str(i): 1 for i in range(20)}, submission_id="submit-123456", score=1)


@pytest.mark.parametrize("raw", ["[]", "null", "5", "\"text\"", "{\"provenance\": []}", "{broken"])
def test_malformed_historical_provenance_is_safely_unknown(raw):
    from types import SimpleNamespace
    row = SimpleNamespace(result_json=raw)
    assert _assessment_provenance(row) == {}
    assert _assessment_is_current(row) is False
    assert _submission_id(raw) is None


@pytest.fixture()
def assessment_client(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'assessment.sqlite3').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add(models.User(id=8801, username="synthetic-assessment", role="student", password_hash="unused"))
        db.commit()
    def current_user():
        return models.User(id=8801, username="synthetic-assessment", role="student")
    def database():
        with sessions() as db:
            yield db
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = current_user
    try:
        with TestClient(app) as client:
            yield client, sessions
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        engine.dispose()


def test_submit_persists_server_result_and_retry_is_idempotent(assessment_client):
    client, sessions = assessment_client
    payload = {"test_type": "SAS", "answers": {str(i): 1 for i in range(20)}, "submission_id": "submit-123456"}
    first = client.post("/api/student/tests/submit", json=payload)
    second = client.post("/api/student/tests/submit", json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json()["test_id"] == second.json()["test_id"]
    assert first.json()["assessment_status"] == "pending_professional_review"
    assert first.json()["risk_level"] is None
    with sessions() as db:
        rows = db.query(models.TestResult).filter_by(user_id=8801, test_type="SAS").all()
        assert len(rows) == 1
