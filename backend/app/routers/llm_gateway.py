import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.models import User
from app.security import get_current_user
from app.services.llm_fallback import _build_structured_fallback, _build_interpretation_fallback

router = APIRouter(tags=["llm-gateway"])


class GenerateRequest(BaseModel):
    prompt: str = Field(max_length=50000)


def _generate(req: GenerateRequest):
    prompt = req.prompt or ""
    wants_structured_json = "严格JSON" in prompt or "risk_level" in prompt or "chart_insights" in prompt
    if wants_structured_json:
        text = json.dumps(_build_structured_fallback(prompt), ensure_ascii=False)
        return {"text": text, "result": text, "source": "local_rules", "status": "fallback", "model_id": None}
    text = _build_interpretation_fallback(prompt)
    return {"text": text, "result": text, "source": "local_rules", "status": "fallback", "model_id": None}


@router.post("/generate")
def generate_text(req: GenerateRequest, current_user: User = Depends(get_current_user)):
    return _generate(req)


@router.post("/api/llm/generate")
def generate_text_alias(req: GenerateRequest, current_user: User = Depends(get_current_user)):
    return _generate(req)
