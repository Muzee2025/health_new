import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant-v1"])


@router.get("/risk-factor")
def get_risk_factor_five_dimension(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    latest_report = (
        db.query(models.PsychologicalReport)
        .filter(models.PsychologicalReport.user_id == current_user.id)
        .order_by(models.PsychologicalReport.updated_at.desc())
        .first()
    )
    if latest_report and latest_report.analysis_json:
        try:
            parsed = json.loads(latest_report.analysis_json)
            radar = parsed.get("trends", {}).get("radar", {})
            data = {
                "academic": int(radar.get("cognition", 0)),
                "interpersonal": int(radar.get("behavior", 0)),
                "family": int(max(0, min(100, (radar.get("behavior", 0) + radar.get("emotion", 0)) / 2))),
                "emotion": int(radar.get("emotion", 0)),
                "physical": int(max(0, min(100, 100 - radar.get("anxiety", 0) * 0.5))),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Risk factor parse failed: {exc}") from exc
    else:
        latest_test = (
            db.query(models.TestResult)
            .filter(models.TestResult.user_id == current_user.id)
            .order_by(models.TestResult.created_at.desc())
            .first()
        )
        base = float(latest_test.standard_score or latest_test.score) if latest_test else 55.0
        data = {
            "academic": max(0, min(100, int(base + 6))),
            "interpersonal": max(0, min(100, int(base - 3))),
            "family": max(0, min(100, int(base - 1))),
            "emotion": max(0, min(100, int(base + 4))),
            "physical": max(0, min(100, int(base - 2))),
        }

    for key, val in data.items():
        if not isinstance(val, int):
            raise HTTPException(status_code=500, detail=f"Invalid risk factor value for {key}")
        data[key] = max(0, min(100, val))

    return {
        "code": 200,
        "data": data,
    }
