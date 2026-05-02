import csv
import json
import secrets
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import requests
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from scipy.stats import binomtest
from snownlp import SnowNLP


BASE_URL = "http://127.0.0.1:8000"
INPUT_TEXT = "我最近获得比赛第二名 我很开心"
RUNS = 10
SENTIMENT_DIFF_THRESHOLD = 0.6
RESULT_ROOT = Path("diagnostics_output")
TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT_DIR = RESULT_ROOT / f"deep_think_audit_{TIMESTAMP}"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sentiment_score(text: str) -> Dict[str, float]:
    score_pos = float(SnowNLP(text).sentiments)
    score_neg = 1.0 - score_pos
    polarity = score_pos - score_neg
    return {
        "positive_confidence": round(score_pos, 4),
        "negative_confidence": round(score_neg, 4),
        "polarity": round(polarity, 4),
    }


def _register_or_login(username: str, password: str) -> str:
    register_payload = {
        "username": username,
        "password": password,
        "role": "student",
        "name": "DiagUser",
    }
    requests.post(f"{BASE_URL}/api/register", json=register_payload, timeout=20)

    login_payload = {"username": username, "password": password}
    resp = requests.post(f"{BASE_URL}/api/login", json=login_payload, timeout=20)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _create_session(token: str) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"mode": "daily", "title": "深度思考诊断会话"}
    resp = requests.post(f"{BASE_URL}/api/advanced-ai/sessions", headers=headers, json=payload, timeout=20)
    resp.raise_for_status()
    return resp.json()["session_id"]


def _stream_once(token: str, session_id: str, nonce: str, client_trace_id: str) -> Dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream",
        "X-Diag-Nonce": nonce,
        "X-Trace-Id": client_trace_id,
    }
    body = {
        "session_id": session_id,
        "message": INPUT_TEXT,
        "modality": "text",
        "anonymous": False,
        "mode": "daily",
        "deep_think": True,
        "history": [],
    }

    started = time.perf_counter()
    started_wall = _iso_now()
    first_token_latency_ms = None
    final_payload = None
    chunks: List[str] = []
    events: List[Dict] = []

    with requests.post(
        f"{BASE_URL}/api/advanced-ai/chat/stream",
        headers=headers,
        json=body,
        stream=True,
        timeout=120,
    ) as resp:
        status_code = resp.status_code
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")

        for raw_line in resp.iter_lines(decode_unicode=True):
            if raw_line is None:
                continue
            line = str(raw_line).strip()
            if not line:
                continue
            if line.startswith("event:"):
                events.append({"event": line[6:].strip(), "at": _iso_now()})
                continue
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            try:
                payload = json.loads(data)
            except Exception:
                payload = data

            if isinstance(payload, dict) and "text" in payload:
                if first_token_latency_ms is None:
                    first_token_latency_ms = round((time.perf_counter() - started) * 1000, 2)
                chunks.append(str(payload.get("text", "")))
            if isinstance(payload, dict) and "reply" in payload:
                final_payload = payload

    ended = time.perf_counter()
    ended_wall = _iso_now()
    total_latency_ms = round((ended - started) * 1000, 2)
    reply_text = ""
    if isinstance(final_payload, dict):
        reply_text = str(final_payload.get("reply", "")).strip()
    if not reply_text:
        reply_text = "".join(chunks).strip()

    nonce_echo_ok = nonce in reply_text
    has_deep_think_tag = "深度思考" in reply_text

    return {
        "started_at": started_wall,
        "ended_at": ended_wall,
        "status_code": status_code,
        "content_type": content_type,
        "client_trace_id": client_trace_id,
        "nonce": nonce,
        "nonce_echo_ok": nonce_echo_ok,
        "first_token_latency_ms": first_token_latency_ms,
        "total_latency_ms": total_latency_ms,
        "has_deep_think_tag": has_deep_think_tag,
        "reply_text": reply_text,
        "event_count": len(events),
        "events": events,
    }


def _suspicious_latency(record: Dict) -> bool:
    if not record.get("has_deep_think_tag"):
        return False
    total = float(record.get("total_latency_ms") or 0.0)
    return total < 1000.0


def _calc_stats(records: List[Dict]) -> Dict:
    nonce_success = sum(1 for r in records if r["nonce_echo_ok"])
    contradiction = sum(1 for r in records if r["sentiment_contradiction"])
    suspicious = sum(1 for r in records if r["suspicious_latency"])
    latencies = [float(r["total_latency_ms"]) for r in records]

    nonce_test = binomtest(k=nonce_success, n=len(records), p=0.95, alternative="less")
    contradiction_test = binomtest(k=contradiction, n=len(records), p=0.1, alternative="greater")

    return {
        "runs": len(records),
        "nonce_echo_success_rate": round(nonce_success / len(records), 4),
        "sentiment_contradiction_rate": round(contradiction / len(records), 4),
        "suspicious_latency_rate": round(suspicious / len(records), 4),
        "latency_ms_avg": round(statistics.mean(latencies), 2),
        "latency_ms_min": round(min(latencies), 2),
        "latency_ms_max": round(max(latencies), 2),
        "latency_ms_p50": round(statistics.median(latencies), 2),
        "latency_ms_p90": round(sorted(latencies)[int(len(latencies) * 0.9) - 1], 2),
        "p_value_nonce_success_below_95pct": nonce_test.pvalue,
        "p_value_contradiction_above_10pct": contradiction_test.pvalue,
        "hypothesis_note": "nonce: H0(success>=95%); contradiction: H0(rate<=10%)",
    }


def _write_pdf(pdf_path: Path, summary: Dict, records: List[Dict], input_sent: Dict) -> None:
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4
    y = height - 50

    def line(text: str) -> None:
        nonlocal y
        if y < 50:
            c.showPage()
            y = height - 50
        c.drawString(40, y, text[:120])
        y -= 16

    line("Deep Think Diagnostic Report")
    line(f"Generated UTC: {_iso_now()}")
    line(f"Input Text: {INPUT_TEXT}")
    line("Independent Sentiment Model: SnowNLP v0.12.3")
    line(f"Input Sentiment: pos={input_sent['positive_confidence']} neg={input_sent['negative_confidence']}")
    line("")
    line("Summary")
    for k, v in summary.items():
        line(f"- {k}: {v}")
    line("")
    line("Top Findings")
    line("1) Header nonce is not wired into deep-think prompt path.")
    line("2) No server traceId in deep-think endpoint response/log contract.")
    line("3) No explicit cache flag in deep-think endpoint payload.")
    line("")
    line("Per-Run Snapshot")
    for idx, r in enumerate(records, 1):
        line(
            f"{idx}. trace={r['client_trace_id']} nonce_ok={r['nonce_echo_ok']} "
            f"lat_ms={r['total_latency_ms']} first_token_ms={r['first_token_latency_ms']} "
            f"contradiction={r['sentiment_contradiction']}"
        )
    c.save()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    username = f"diag_{TIMESTAMP.lower()}"
    password = "Diag#123456"
    token = _register_or_login(username, password)
    session_id = _create_session(token)

    input_sent = _sentiment_score(INPUT_TEXT)
    records: List[Dict] = []
    replays: List[Dict] = []

    for i in range(RUNS):
        nonce = secrets.token_hex(8)
        trace_id = f"diag-{TIMESTAMP.lower()}-{i+1:02d}"
        rec = _stream_once(token, session_id, nonce, trace_id)

        reply_sent = _sentiment_score(rec["reply_text"] or "")
        polarity_gap = abs(input_sent["polarity"] - reply_sent["polarity"])
        contradiction = polarity_gap > SENTIMENT_DIFF_THRESHOLD

        rec["input_sentiment"] = input_sent
        rec["reply_sentiment"] = reply_sent
        rec["polarity_gap"] = round(polarity_gap, 4)
        rec["sentiment_contradiction"] = contradiction
        rec["severity"] = "P0" if contradiction else "OK"
        rec["suspicious_latency"] = _suspicious_latency(rec)

        if rec["suspicious_latency"]:
            nonce2 = secrets.token_hex(8)
            trace2 = f"{trace_id}-replay"
            replay_rec = _stream_once(token, session_id, nonce2, trace2)
            replay_rec["replay_of"] = trace_id
            replays.append(replay_rec)

        records.append(rec)

    summary = _calc_stats(records)
    summary["session_id"] = session_id
    summary["username"] = username
    summary["model_version_assumed"] = "emohaa (from backend service hardcoded model field)"
    summary["trace_id_type"] = "client_trace_id injected by diagnostic script"

    json_path = OUT_DIR / "deep_think_runs.json"
    csv_path = OUT_DIR / "deep_think_runs.csv"
    summary_path = OUT_DIR / "summary.json"
    replay_path = OUT_DIR / "suspicious_replays.json"
    pdf_path = OUT_DIR / "diagnostic_report.pdf"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    with replay_path.open("w", encoding="utf-8") as f:
        json.dump(replays, f, ensure_ascii=False, indent=2)
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "client_trace_id",
                "started_at",
                "ended_at",
                "status_code",
                "nonce",
                "nonce_echo_ok",
                "total_latency_ms",
                "first_token_latency_ms",
                "has_deep_think_tag",
                "polarity_gap",
                "sentiment_contradiction",
                "suspicious_latency",
            ],
        )
        writer.writeheader()
        for r in records:
            writer.writerow({k: r.get(k) for k in writer.fieldnames})

    _write_pdf(pdf_path=pdf_path, summary=summary, records=records, input_sent=input_sent)

    print(str(OUT_DIR.resolve()))
    print(str(summary_path.resolve()))
    print(str(pdf_path.resolve()))


if __name__ == "__main__":
    main()
