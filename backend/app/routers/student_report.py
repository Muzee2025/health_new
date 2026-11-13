import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.security import require_roles
from app.services.qwen_service import client as qwen_client

from .. import models, schemas
from ..database import get_db
from .auth import get_current_user
from .student_shared import (
    ASSESSMENT_ENGINE_VERSION,
    _assessment_is_current,
    _assessment_provenance,
    _invalidate_user_report_cache,
    _json_object,
    check_student_role,
)

router = APIRouter(prefix="/api/student")

ASSESSMENT_QUESTION_BANK_SHA256 = "ab811c96af47cb88e76a842beac42984aa6ab23d0047fb59386cd11dbc2822f8"

ASSESSMENT_SUBMISSION_LOCK = Lock()

_ASSESSMENT_FORMS = {
    "SDS": {"count": 20, "version": "question-bank-2026-10-31-v1", "reverse": {2, 5, 6, 11, 12, 14, 16, 17, 18, 20}},
    "SAS": {"count": 20, "version": "question-bank-2026-10-31-v1", "reverse": {5, 9, 13, 17, 19}},
    "MBTI": {"count": 28, "version": "question-bank-2026-10-31-v1", "groups": ["EI"] * 7 + ["SN"] * 7 + ["TF"] * 7 + ["JP"] * 7},
    "MentalAge": {"count": 15, "version": "question-bank-2026-10-31-v1"},
}

def _score_assessment(test_type: str, answers: dict):
    form = _ASSESSMENT_FORMS.get(test_type)
    if not form:
        raise HTTPException(status_code=422, detail="未知测评工具")
    expected = {str(i) for i in range(form["count"])}
    if set(answers) != expected:
        raise HTTPException(status_code=422, detail="答题题数或题目编号不匹配")
    normalized = {}
    for key in sorted(expected, key=int):
        value = answers[key]
        if isinstance(value, bool):
            raise HTTPException(status_code=422, detail="答题选项无效")
        normalized[key] = value
    result_level = None
    standard_score = None
    risk_level = None
    if test_type in ("SDS", "SAS"):
        if any(type(normalized[str(i)]) is not int or normalized[str(i)] not in (1, 2, 3, 4) for i in range(form["count"])):
            raise HTTPException(status_code=422, detail="答题选项超出题本范围")
        score = sum((5 - normalized[str(i)]) if (i + 1) in form["reverse"] else normalized[str(i)] for i in range(form["count"]))
        standard_score = int(score * 1.25)
        eligibility = "pending_professional_review"
        result_level = "待专业复核"
        explanation = "已按当前登记题本完成工程计分；正式解释和界值尚待专业复核。"
    elif test_type == "MBTI":
        if any(type(normalized[str(i)]) is not str or normalized[str(i)] not in form["groups"][i] for i in range(form["count"])):
            raise HTTPException(status_code=422, detail="答题选项超出题本范围")
        dimensions = []
        for offset, (left, right) in zip((0, 7, 14, 21), (("E", "I"), ("S", "N"), ("T", "F"), ("J", "P")), strict=True):
            vals = [normalized[str(i)] for i in range(offset, offset + 7)]
            dimensions.append(left if vals.count(left) > vals.count(right) else right)
        score, result_level, eligibility = 100, "".join(dimensions), "entertainment_only"
        explanation = "此为娱乐性自我探索结果，不是心理测量或诊断。"
    else:
        allowed = {1, 3, 5}
        if any(type(normalized[str(i)]) is not int or normalized[str(i)] not in allowed for i in range(form["count"])):
            raise HTTPException(status_code=422, detail="答题选项超出题本范围")
        score = sum(normalized.values())
        result_level = "纯真孩童" if score <= 25 else "青春少年" if score <= 50 else "成熟青年" if score <= 65 else "稳重长者"
        eligibility = "entertainment_only"
        explanation = "此为娱乐性自我探索结果，不是心理测量或诊断。"
    form_snapshot = {key: value for key, value in form.items()}
    form_hash = hashlib.sha256(json.dumps(form_snapshot, sort_keys=True, ensure_ascii=False,
        default=lambda value: sorted(value) if isinstance(value, set) else str(value)).encode("utf-8")).hexdigest()
    provenance = {"instrument_id": test_type, "form_version": form["version"], "form_hash": form_hash,
        "question_bank_source_sha256": ASSESSMENT_QUESTION_BANK_SHA256,
        "scoring_version": ASSESSMENT_ENGINE_VERSION, "eligibility": eligibility}
    detail = {"desc": explanation, "provenance": provenance, "scoring": {"score": score, "standard_score": standard_score}}
    return score, standard_score, result_level, risk_level, eligibility, detail, normalized

@router.post("/tests/submit")
def submit_test(test_data: schemas.TestSubmit, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_student_role(current_user)
    score, standard_score, result_level, risk_level, eligibility, detail, normalized = _score_assessment(test_data.test_type, test_data.answers)
    detail["provenance"]["submission_id"] = test_data.submission_id
    with ASSESSMENT_SUBMISSION_LOCK:
        prior = db.query(models.TestResult).filter(models.TestResult.user_id == current_user.id, models.TestResult.test_type == test_data.test_type).order_by(models.TestResult.id.desc()).limit(200).all()
        test_result = next((row for row in prior if _submission_id(row.result_json) == test_data.submission_id), None)
        if test_result is not None and (test_result.answers or "") != json.dumps(normalized, ensure_ascii=False):
            raise HTTPException(status_code=409, detail="submission_id 已用于不同答卷")
        if test_result is None:
            test_result = models.TestResult(user_id=current_user.id, test_type=test_data.test_type, score=score,
                standard_score=standard_score, result_level=result_level, answers=json.dumps(normalized, ensure_ascii=False),
                result_json=json.dumps(detail, ensure_ascii=False), risk_level=risk_level)
            db.add(test_result)
            db.commit()
            db.refresh(test_result)
    _invalidate_user_report_cache(db, current_user.id)
    return {"id": test_result.id, "test_id": test_result.id, "user_id": test_result.user_id,
        "test_type": test_result.test_type, "score": score, "standard_score": standard_score,
        "result_level": result_level, "risk_level": risk_level, "answers": test_result.answers,
        "result_json": test_result.result_json, "assessment_status": eligibility,
        "scoring": detail["provenance"], "created_at": test_result.created_at}

def _submission_id(result_json):
    provenance = _json_object(result_json).get("provenance")
    return provenance.get("submission_id") if isinstance(provenance, dict) else None

@router.get("/tests/history", response_model=List[schemas.TestResponse])
def get_test_history(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_student_role(current_user)
    return db.query(models.TestResult).filter(models.TestResult.user_id == current_user.id).order_by(models.TestResult.created_at.asc()).all()

class TestAiAnalyzeRequest(BaseModel):
    model_config = {"extra": "forbid"}
    test_id: int = Field(strict=True, gt=0)

def _active_qwen_client():
    # Preserve the legacy student.qwen_client injection point while callers migrate.
    from . import student

    return getattr(student, "qwen_client", qwen_client)


@router.post("/tests/ai-analyze")
async def ai_analyze_test_result(
    req: TestAiAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_student_role(current_user)

    test_row = db.query(models.TestResult).filter(models.TestResult.user_id == current_user.id, models.TestResult.id == req.test_id).first()

    if not test_row:
        raise HTTPException(status_code=404, detail="未找到可分析的测评结果")

    provenance = _assessment_provenance(test_row)
    sources = [{"type": "scoring_provenance", "label": "本地计分规则记录（非外部文献）",
        "tool_id": test_row.test_type, "form_version": provenance.get("form_version"),
        "scoring_version": provenance.get("scoring_version"), "form_hash": provenance.get("form_hash"),
        "question_bank_source_sha256": provenance.get("question_bank_source_sha256"), "external": False}]
    if test_row.test_type not in _ASSESSMENT_FORMS or provenance.get("scoring_version") != ASSESSMENT_ENGINE_VERSION:
        content = {"summary": "这条历史记录的题本或计分版本未知，资料不足，暂不能生成可靠解读。", "observations": [], "limitations": ["历史版本未登记；不推断正式心理结论。"], "next_steps": ["如需了解当前状态，请使用已登记题本重新作答或联系校内专业人员。"]}
    elif test_row.test_type in ("SDS", "SAS"):
        content = {"summary": "本次结果仅为当前题本的工程计分，正式解释尚待专业复核。", "observations": [f"服务器记录的原始分为 {test_row.score}。"], "limitations": ["当前未配置经批准的界值和解释规则；此结果不是诊断。"], "next_steps": ["如有困扰，可主动向校内心理服务人员咨询。"]}
    else:
        content = {"summary": "这是娱乐性自我探索结果，可作为轻松的自我观察话题。", "observations": [f"工具给出的类型为 {test_row.result_level}。"], "limitations": ["该工具不具备心理风险筛查或诊断用途。"], "next_steps": ["结合自身体验自行参考，不据此作重要决定。"]}
    enabled = os.getenv("AI_EXTERNAL_ENABLED", "").strip().lower() in {"1", "true", "yes"}
    provider_client = _active_qwen_client() if enabled else None
    if provider_client is not None:
        try:
            response = await provider_client.chat.completions.create(
                model="qwen-plus", temperature=0.2, max_tokens=500,
                messages=[
                    {"role": "system", "content": "你提供非诊断性的自我观察说明。仅输出JSON，字段 summary:string, observations:string[], limitations:string[], next_steps:string[]。没有依据时明确写资料不足，不推断风险，不建议诊断。"},
                    {"role": "user", "content": json.dumps({"tool": test_row.test_type, "score": test_row.score if test_row.test_type in ("SDS", "SAS") else None,
                        "standard_score": test_row.standard_score if test_row.test_type in ("SDS", "SAS") else None,
                        "eligibility": provenance.get("eligibility", "unknown"),
                        "rule_summary": content}, ensure_ascii=False)},
                ],
            )
            parsed = _json_object(response.choices[0].message.content)
            if _valid_interpretation_content(parsed):
                content = parsed
                model_id = getattr(response, "model", None)
                if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 120:
                    model_id = None
                return {"status": "completed", "source": "provider", "model_id": model_id, "test_id": test_row.id,
                    "content": content, "sources": sources, "notice": "模型生成的非诊断性说明；未发送逐题答卷、姓名、学号或树洞原文。"}
        except Exception:
            # Provider errors and malformed output degrade to the explicit local result.
            pass
    return {"status": "fallback", "source": "local_rule", "model_id": None, "test_id": test_row.id,
        "content": content, "sources": sources, "notice": "本地规则说明，非大模型生成；当前无可用且获准的模型响应。"}

def _valid_interpretation_content(value):
    if not isinstance(value, dict) or set(value) != {"summary", "observations", "limitations", "next_steps"} or not isinstance(value.get("summary"), str):
        return False
    if not value["summary"].strip() or len(value["summary"]) > 500:
        return False
    for key in ("observations", "limitations", "next_steps"):
        items = value.get(key)
        if not isinstance(items, list) or len(items) > 8:
            return False
        if any(not isinstance(item, str) or not item.strip() or len(item) > 240 for item in items):
            return False
    return True

DEFAULT_REPORT_TYPE = "student_mental_report"

REPORT_CACHE_TTL_SECONDS = 15 * 60

REPORT_TYPE_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,64}$")

REPORT_LOAD_METRICS = {"report:load:hit_rate": 0, "report:load:miss": 0}

METRIC_LOCK = Lock()

def _normalize_report_type(report_type: str) -> str:
    report_type = (report_type or DEFAULT_REPORT_TYPE).strip()
    if not REPORT_TYPE_PATTERN.match(report_type):
        raise HTTPException(status_code=400, detail="Invalid report_type")
    return report_type

def _record_report_metric(metric_key: str):
    with METRIC_LOCK:
        REPORT_LOAD_METRICS[metric_key] = REPORT_LOAD_METRICS.get(metric_key, 0) + 1

def _generate_report_analysis_payload(db: Session, current_user: models.User):
    candidate_tests = db.query(models.TestResult).filter(models.TestResult.user_id == current_user.id,
        models.TestResult.test_type.in_(["SDS", "SAS"])).order_by(models.TestResult.created_at.desc()).all()
    latest_test = next((row for row in candidate_tests if _assessment_is_current(row)), None)
    recent_treehole = db.query(models.TreeholePost).filter(models.TreeholePost.user_id == current_user.id).order_by(models.TreeholePost.created_at.desc()).first()

    all_tests = db.query(models.TestResult).filter(
        models.TestResult.user_id == current_user.id,
        models.TestResult.test_type.in_(["SDS", "SAS"])
    ).order_by(models.TestResult.created_at.desc()).all()

    score_distribution = {"SDS": [], "SAS": []}
    for t in all_tests:
        try:
            provenance = _assessment_provenance(t)
        except (TypeError, ValueError):
            provenance = {}
        if t.test_type in score_distribution and provenance.get("scoring_version") == ASSESSMENT_ENGINE_VERSION:
            score_distribution[t.test_type].append({
                "date": t.created_at.strftime("%Y-%m-%d"),
                "score": t.standard_score or t.score,
                "level": t.result_level,
                "risk": t.risk_level
            })

    risk_stats = {"red": 0, "yellow": 0, "green": 0}
    for t in all_tests:
        try:
            if _assessment_provenance(t).get("scoring_version") != ASSESSMENT_ENGINE_VERSION:
                continue
        except (TypeError, ValueError):
            continue
        if t.risk_level in risk_stats:
            risk_stats[t.risk_level] += 1

    category_scores = {}
    for t in all_tests:
        try:
            if _assessment_provenance(t).get("scoring_version") != ASSESSMENT_ENGINE_VERSION:
                continue
        except (TypeError, ValueError):
            continue
        if t.test_type not in category_scores:
            category_scores[t.test_type] = []
        category_scores[t.test_type].append(t.standard_score or t.score)

    avg_scores = {}
    for cat, scores in category_scores.items():
        if scores:
            avg_scores[cat] = round(sum(scores) / len(scores), 1)

    analysis_basis = {
        "data_sources": [],
        "key_parameters": [],
        "logic_path": []
    }

    if latest_test:
        analysis_basis["data_sources"].append(f"最新{latest_test.test_type}测评（标准分：{latest_test.standard_score or latest_test.score}）")
        analysis_basis["key_parameters"].append(f"评估等级：{latest_test.result_level}，风险级别：{latest_test.risk_level}")
        analysis_basis["logic_path"].append(f"按当前登记规则完成{latest_test.test_type}工程计分；常模与解释待专业复核")

    if recent_treehole:
        analysis_basis["data_sources"].append("树洞倾诉记录")
        if recent_treehole.emotion_keywords:
            analysis_basis["key_parameters"].append(f"情绪关键词：{recent_treehole.emotion_keywords}")
            analysis_basis["logic_path"].append(f"从树洞内容中提取到「{recent_treehole.emotion_keywords}」等情绪关键词")

    rag_context = ""

    user_context = "用户基本情况：\n"
    if latest_test:
        user_context += f"最新测评({latest_test.test_type})结果：标准分 {latest_test.standard_score or latest_test.score}，评估等级：{latest_test.result_level}，风险级别：{latest_test.risk_level}\n"
    if recent_treehole:
        if recent_treehole.emotion_keywords:
            user_context += f"提取的情绪关键词：{recent_treehole.emotion_keywords}\n"

    rag_context = ""
    try:
        from ..services.rag_service import query_rag
        rag_context = query_rag(query=user_context, n_results=3)
    except Exception:
        pass
    if rag_context:
        analysis_basis["data_sources"].append("心理知识库检索结果（存在返回内容）")
        analysis_basis["logic_path"].append("检索返回相关片段，尚未逐条专业核验；不代表临床依据")

    # This legacy aggregate endpoint is a local summary. Per-assessment model
    # explanation has its own explicit, ID-bound and minimized-input endpoint.
    generation = {"source": "local_rules", "status": "fallback" if latest_test or recent_treehole else "insufficient", "model_id": None}
    ai_analysis_text = (f"当前有{sum(len(rows) for rows in score_distribution.values())}条带计分版本的自我观察记录。"
                        "这里显示本地汇总说明，未调用外部模型。分数和关键词不能判断疾病或排除困扰；"
                        "可在本次测评结果页查看辅助说明，或根据需要选择人工求助。")

    treehole_analysis = db.query(models.TreeholeAnalysis).filter(models.TreeholeAnalysis.user_id == current_user.id).order_by(models.TreeholeAnalysis.created_at.desc()).all()

    recent_themes = []
    if treehole_analysis:
        theme_counts = {}
        for ta in treehole_analysis:
            if ta.core_values:
                words = ta.core_values.split(",")
                for w in words:
                    w = w.strip()
                    if w:
                        theme_counts[w] = theme_counts.get(w, 0) + 1
        sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        recent_themes = [{"word": k, "count": v} for k, v in sorted_themes]

    deep_moments = db.query(models.TreeholePost).filter(
        models.TreeholePost.user_id == current_user.id,
        models.TreeholePost.is_deep.is_(True)
    ).order_by(func.random()).first()

    deep_moment_data = None
    if deep_moments:
        deep_moment_data = {
            "content": deep_moments.content,
            "created_at": deep_moments.created_at.strftime("%Y-%m-%d")
        }

    payload = {
        "ai_analysis": ai_analysis_text,
        "generation": generation,
        "data_status": "available" if latest_test or recent_treehole else "insufficient",
        "analysis_basis": analysis_basis,
        "recent_themes": recent_themes,
        "deep_moment": deep_moment_data,
        "score_distribution": score_distribution,
        "risk_stats": risk_stats,
        "avg_scores": avg_scores
    }

    fingerprint_parts = [
        str(latest_test.id if latest_test else 0),
        str(recent_treehole.id if recent_treehole else 0),
        str(len(all_tests)),
        str(len(treehole_analysis)),
    ]
    source_times = [
        t for t in [
            latest_test.created_at if latest_test else None,
            recent_treehole.created_at if recent_treehole else None,
        ] if t is not None
    ]
    source_updated_at = max(source_times) if source_times else None
    data_fingerprint = "|".join(fingerprint_parts)
    return payload, data_fingerprint, source_updated_at

def _save_report_cache(
    db: Session,
    *,
    user_id: int,
    report_type: str,
    payload: dict,
    data_fingerprint: str,
    source_updated_at,
):
    cache = db.query(models.ReportAnalysisCache).filter(
        models.ReportAnalysisCache.user_id == user_id,
        models.ReportAnalysisCache.report_type == report_type,
    ).first()
    if not cache:
        cache = models.ReportAnalysisCache(
            user_id=user_id,
            report_type=report_type,
            payload_json="{}",
        )
        db.add(cache)
    cache.payload_json = json.dumps(payload, ensure_ascii=False)
    cache.data_fingerprint = data_fingerprint
    cache.source_updated_at = source_updated_at
    cache.expires_at = datetime.now(timezone.utc) + timedelta(seconds=REPORT_CACHE_TTL_SECONDS)
    db.commit()
    db.refresh(cache)
    return cache

def _attach_report_meta(payload: dict, *, report_type: str, from_cache: bool, cache_status: str, refreshed_at: str):
    payload_with_meta = dict(payload)
    payload_with_meta["_meta"] = {
        "report_type": report_type,
        "from_cache": from_cache,
        "cache_status": cache_status,
        "refreshed_at": refreshed_at,
        "ttl_seconds": REPORT_CACHE_TTL_SECONDS,
    }
    return payload_with_meta

@router.get("/report/analysis")
def get_report_analysis(
    request: Request,
    response: Response,
    report_type: str = Query(DEFAULT_REPORT_TYPE),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_student_role(current_user)
    report_type = _normalize_report_type(report_type)

    cache = db.query(models.ReportAnalysisCache).filter(
        models.ReportAnalysisCache.user_id == current_user.id,
        models.ReportAnalysisCache.report_type == report_type,
    ).first()

    # A personal report must never enter a shared cache: a proxy that stored it
    # would hand it to the next student asking for the same URL.
    response.headers["Cache-Control"] = "private, max-age=300, stale-while-revalidate=30"
    response.headers["Vary"] = "Authorization"
    if cache and cache.payload_json:
        etag = f'W/"{hashlib.md5(cache.payload_json.encode()).hexdigest()}"'
        if request.headers.get("If-None-Match") == etag:
            response.status_code = 304
            return Response(status_code=304)

        response.headers["ETag"] = etag
        response.headers["Last-Modified"] = cache.updated_at.strftime("%a, %d %b %Y %H:%M:%S GMT")

        try:
            payload = json.loads(cache.payload_json)
            cache_status = "fresh"
            if cache.expires_at and cache.expires_at <= datetime.now(timezone.utc):
                cache_status = "stale"
            _record_report_metric("report:load:hit_rate")
            return _attach_report_meta(
                payload,
                report_type=report_type,
                from_cache=True,
                cache_status=cache_status,
                refreshed_at=(cache.updated_at.isoformat() if cache.updated_at else ""),
            )
        except json.JSONDecodeError:
            pass

    _record_report_metric("report:load:miss")
    payload, data_fingerprint, source_updated_at = _generate_report_analysis_payload(db, current_user)
    cache = _save_report_cache(
        db,
        user_id=current_user.id,
        report_type=report_type,
        payload=payload,
        data_fingerprint=data_fingerprint,
        source_updated_at=source_updated_at,
    )
    return _attach_report_meta(
        payload,
        report_type=report_type,
        from_cache=False,
        cache_status="miss",
        refreshed_at=(cache.updated_at.isoformat() if cache.updated_at else ""),
    )

@router.get("/report/cache/metrics")
def get_report_cache_metrics(current_user: models.User = Depends(require_roles("teacher"))):
    total = REPORT_LOAD_METRICS["report:load:hit_rate"] + REPORT_LOAD_METRICS["report:load:miss"]
    hit_ratio = (REPORT_LOAD_METRICS["report:load:hit_rate"] / total) if total else 1.0
    return {
        "metrics": REPORT_LOAD_METRICS,
        "hit_ratio": round(hit_ratio, 4),
        "alert": "hit_ratio < 0.95",
        "recommended_scrape_interval_seconds": 15,
    }

@router.get("/report/analysis/refresh")
def refresh_report_analysis(
    response: Response,
    report_type: str = Query(DEFAULT_REPORT_TYPE),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_student_role(current_user)
    report_type = _normalize_report_type(report_type)
    payload, data_fingerprint, source_updated_at = _generate_report_analysis_payload(db, current_user)
    cache = _save_report_cache(
        db,
        user_id=current_user.id,
        report_type=report_type,
        payload=payload,
        data_fingerprint=data_fingerprint,
        source_updated_at=source_updated_at,
    )

    if cache and cache.payload_json:
        etag = f'W/"{hashlib.md5(cache.payload_json.encode()).hexdigest()}"'
        response.headers["ETag"] = etag
        if cache.updated_at:
            response.headers["Last-Modified"] = cache.updated_at.strftime("%a, %d %b %Y %H:%M:%S GMT")

    return _attach_report_meta(
        payload,
        report_type=report_type,
        from_cache=False,
        cache_status="refreshed",
        refreshed_at=(cache.updated_at.isoformat() if cache.updated_at else ""),
    )
