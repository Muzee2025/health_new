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
    # Existing tests and dialogue tags do not measure these five constructs.
    # A single score (or missing data) must never be expanded into five scores.
    return {
        "code": 200,
        "data": None,
        "data_status": "insufficient",
        "source": "not_available",
        "message": "暂无可核验的五维评估数据。现有测评与对话记录不能推导学业、人际、家庭、情绪和身体的独立分数。",
    }
