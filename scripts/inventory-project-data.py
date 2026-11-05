"""Read-only SQLite schema/profile inventory. Never export record values or credentials."""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp/data-inventory-20261028"
SOURCES = [
    ("PREVIEW", "tmp/article-scaling-20261025/preview-private/health.db", "文档登记的指南预览库；是否仍由服务加载未验证"),
    ("ROOT_HEALTH", "health.db", "根目录历史库；未确认当前服务绑定"),
    ("ROOT_DATABASE", "database.db", "根目录其他历史库；未确认用途"),
    ("BACKEND_HEALTH", "backend/health.db", "backend历史库；未确认当前服务绑定"),
    ("CONTENT", "tmp/content-quality-20261024/content.db", "内容导入新库；工程指南数据"),
    ("SHOWCASE", "tmp/showcase-20261024-7f5512da/health.db", "历史合成展示副本；不代表真实业务"),
]


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def qi(value):
    return '"' + value.replace('"', '""') + '"'


def models():
    path = ROOT / "backend/app/models.py"
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    result = {}
    for cls in ast.parse(text).body:
        if not isinstance(cls, ast.ClassDef):
            continue
        table = None
        cols = {}
        for node in cls.body:
            if not isinstance(node, ast.Assign) or not isinstance(node.targets[0], ast.Name):
                continue
            name = node.targets[0].id
            if name == "__tablename__":
                table = ast.literal_eval(node.value)
            if not isinstance(node.value, ast.Call) or not isinstance(node.value.func, ast.Name) or node.value.func.id != "Column":
                continue
            call = node.value
            kw = {k.arg: ast.unparse(k.value) for k in call.keywords}
            fk = [ast.unparse(a) for a in call.args if isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id == "ForeignKey"]
            line = lines[node.end_lineno - 1]
            cols[name] = {"model_type": ast.unparse(call.args[0]), "app_default": kw.get("default", ""),
                          "server_default_model": kw.get("server_default", ""), "model_nullable": kw.get("nullable", "未显式指定"),
                          "model_fk": "; ".join(fk), "model_comment": line.split("#", 1)[1].strip() if "#" in line else "",
                          "source": "backend/app/models.py", "line": node.lineno}
        if table:
            result[table] = cols
    return result


def inspect(source_id, relative, provenance):
    path = ROOT / relative
    result = {"source_id": source_id, "path": relative, "provenance": provenance, "exists": path.is_file(), "tables": []}
    if not path.is_file():
        return result
    before = digest(path)
    source = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    source.execute("PRAGMA query_only=ON")
    memory = sqlite3.connect(":memory:")
    try:
        source.backup(memory)
    finally:
        source.close()
    memory.execute("PRAGMA query_only=ON")
    result["quick_check"] = "ok" if memory.execute("PRAGMA quick_check").fetchone()[0] == "ok" else "failed"
    fk_issues = {}
    for row in memory.execute("PRAGMA foreign_key_check"):
        key = (row[0], row[2])
        fk_issues[key] = fk_issues.get(key, 0) + 1
    result["foreign_key_issues"] = [{"table": t, "parent": p, "count": n} for (t, p), n in sorted(fk_issues.items())]
    result["fk_issue_count"] = sum(fk_issues.values())
    result["triggers"] = [x[0] for x in memory.execute("SELECT name FROM sqlite_master WHERE type='trigger' ORDER BY name")]
    tables = memory.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
    for (table,) in tables:
        count = memory.execute(f"SELECT COUNT(*) FROM {qi(table)}").fetchone()[0]
        fks = list(memory.execute(f"PRAGMA foreign_key_list({qi(table)})"))
        indexes = []
        for idx in memory.execute(f"PRAGMA index_list({qi(table)})").fetchall():
            indexes.append({"name": idx[1], "unique": bool(idx[2]), "columns": [x[2] for x in memory.execute(f"PRAGMA index_info({qi(idx[1])})")]})
        cols = []
        for row in memory.execute(f"PRAGMA table_xinfo({qi(table)})"):
            cid, name, dtype, notnull, default, pk, hidden = row
            # Defaults are metadata, but unknown literals are redacted rather than exposing historical personal values.
            safe_default = default if default is None or str(default) in {"0", "1", "CURRENT_TIMESTAMP", "'{}'", "'[]'", "NULL"} else "常量默认值（未导出）"
            missing, blank = memory.execute(f"SELECT SUM({qi(name)} IS NULL), SUM(typeof({qi(name)})='text' AND trim({qi(name)})='') FROM {qi(table)}").fetchone()
            cols.append({"ordinal": cid + 1, "name": name, "sql_type": dtype, "notnull": bool(notnull), "pk_order": pk,
                         "sql_default": safe_default, "hidden": hidden, "null_count": missing or 0, "blank_count": blank or 0,
                         "null_rate": (missing or 0) / count if count else None,
                         "foreign_keys": [f"{x[2]}.{x[4]} (ON DELETE {x[6]})" for x in fks if x[3] == name],
                         "indexes": [i["name"] for i in indexes if name in i["columns"]],
                         "unique_alone": any(i["unique"] and i["columns"] == [name] for i in indexes) or (bool(pk) and sum(c[5] > 0 for c in memory.execute(f"PRAGMA table_info({qi(table)})")) == 1)})
        result["tables"].append({"name": table, "row_count": count, "column_count": len(cols), "columns": cols, "indexes": indexes})
    memory.close()
    result["sha256_before"] = before
    result["sha256_after"] = digest(path)
    result["file_unchanged_during_read"] = result["sha256_before"] == result["sha256_after"]
    result["column_count"] = sum(t["column_count"] for t in result["tables"])
    result["table_count"] = len(result["tables"])
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    inventory = {"as_of": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "models": models(),
                 "scope": "指定的三个历史库及三个有文档来历的独立副本；不包括临时单测/QA/备份库；不读取.env、不查询业务API",
                 "privacy": "仅结构及聚合计数；不导出任何记录值、账号、标识符、密码哈希、聊天或测评原文"}
    inventory["databases"] = [inspect(*s) for s in SOURCES]
    region_path = ROOT / "docs/plan/ai-application/revision-20261027/regional-education-2024.csv"
    with region_path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    inventory["regional"] = [{k: (v if k == "region" else int(v)) for k, v in row.items()} for row in rows]
    lit_path = ROOT / "docs/plan/ai-application/sci-revision-20261027/literature-data.json"
    inventory["literature"] = json.loads(lit_path.read_text(encoding="utf-8-sig"))
    inventory["public_sources"] = [{"path": str(p.relative_to(ROOT)).replace('\\', '/'), "sha256": digest(p)} for p in [region_path, lit_path]]
    (OUT / "inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"databases": [{k: v for k, v in d.items() if k in {"source_id", "table_count", "column_count", "quick_check", "fk_issue_count", "file_unchanged_during_read"}} for d in inventory["databases"]], "model_tables": len(inventory["models"]), "regional_rows": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
