import json
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models

ASSESSMENT_ENGINE_VERSION = "health-new-muzee2025-assessment-engine-2026-10-31-v1"


def _json_object(raw):
    """Parse legacy JSON defensively; only object payloads are trusted metadata."""
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _assessment_provenance(row):
    detail = _json_object(getattr(row, "result_json", None))
    provenance = detail.get("provenance")
    return provenance if isinstance(provenance, dict) else {}

def check_student_role(user: models.User):
    if user.role != "student":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return user


def _assessment_is_current(row):
    return _assessment_provenance(row).get("scoring_version") == ASSESSMENT_ENGINE_VERSION

def _invalidate_user_report_cache(db: Session, user_id: int):
    caches = db.query(models.ReportAnalysisCache).filter(models.ReportAnalysisCache.user_id == user_id).all()
    if not caches:
        return
    now = datetime.now(timezone.utc) - timedelta(seconds=1)
    for cache in caches:
        cache.expires_at = now
    db.commit()
