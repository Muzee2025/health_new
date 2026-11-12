from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

MOCK_CRISIS_SEED: List[Dict[str, Any]] = [
    {
        "id": "c_1001",
        "studentId": "2024001001",
        "studentName": "李某某",
        "className": "大二",
        "riskLevel": "high",
        "description": "我真的受不了我的室友了，每天晚上吵到凌晨，我考试又要挂科了，我好想跳下去一了百了。",
        "createdAt": "2026-04-11 14:30:00",
        "status": "pending",
    },
    {
        "id": "c_1002",
        "studentId": "2024001002",
        "studentName": "王某某",
        "className": "大一",
        "riskLevel": "medium",
        "description": "最近不想去上课，感觉怎么努力都没意义。",
        "createdAt": "2026-04-12 10:20:00",
        "status": "pending",
    },
    {
        "id": "c_1003",
        "studentId": "2024001003",
        "studentName": "赵某某",
        "className": "大三",
        "riskLevel": "low",
        "description": "最近总和同学冲突，晚上也睡不好。",
        "createdAt": "2026-04-12 19:10:00",
        "status": "pending",
    },
]


_mock_status_overrides: Dict[str, str] = {}


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.min
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return datetime.min


def load_mock_records(include_reviewed: bool = False) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for row in MOCK_CRISIS_SEED:
        current_status = _mock_status_overrides.get(row["id"], row["status"])
        if not include_reviewed and current_status != "pending":
            continue
        records.append(
            {
                "id": f"mock-{row['id']}",
                "createdAt": row["createdAt"],
                "studentId": row["studentId"],
                "studentName": row["studentName"],
                "className": row["className"],
                "riskLevel": row["riskLevel"],
                "description": row["description"],
                "status": current_status,
                "highlight": False,
            }
        )
    return records


def mark_mock_reviewed(source_id: str) -> bool:
    exists = any(x["id"] == source_id for x in MOCK_CRISIS_SEED)
    if not exists:
        return False
    _mock_status_overrides[source_id] = "reviewed"
    return True


def merge_pending_records(mock_rows: List[Dict[str, Any]], real_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged_map: Dict[str, Dict[str, Any]] = {}
    for row in [*mock_rows, *real_rows]:
        key = str(row.get("id", ""))
        merged_map[key] = row
    merged = list(merged_map.values())
    merged.sort(
        key=lambda item: (
            0 if str(item.get("id", "")).startswith("real-") else 1,
            -_parse_dt(item.get("createdAt")).timestamp(),
        )
    )
    return merged


def paginate_rows(rows: List[Dict[str, Any]], page: int, page_size: int) -> Dict[str, Any]:
    safe_page = max(page, 1)
    safe_page_size = min(max(page_size, 1), 200)
    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size
    return {
        "items": rows[start:end],
        "total": len(rows),
        "page": safe_page,
        "pageSize": safe_page_size,
    }
