"""Dump the backend route table as a stable, diffable snapshot.

Read-only: imports the app, prints routes, writes nothing.

Usage (from the repository root):
  .venv/Scripts/python.exe backend/scripts/dump-route-table.py
  .venv/Scripts/python.exe backend/scripts/dump-route-table.py --json
  .venv/Scripts/python.exe backend/scripts/dump-route-table.py --compare a.json b.json

Why not just read app.routes: FastAPI 0.140 mounts include_router() results
lazily (_IncludedRouter), so app.routes holds the router objects rather than
the expanded APIRoute list. This script therefore walks each router module's
own .routes in registration order, which is also the order FastAPI matches in.

Registration order matters and is part of the snapshot: /articles/page must be
registered before /articles/{article_id} on both the student and the teacher
router, otherwise the literal path is captured by the wildcard and returns 422
(article_id fails int parsing), not 404.

The snapshot includes the registration index so a reordering shows up in the
diff instead of hiding behind an identical set.
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

# Router modules mounted by app.main. Kept explicit so a new module is a
# deliberate edit here rather than a silent omission from the snapshot.
ROUTER_MODULES = (
    "auth",
    "health",
    "student",
    "teacher",
    "advanced_chat",
    "advanced_teacher",
    "report_v1",
    "assistant_v1",
    "llm_gateway",
    "websocket",
)


def _bootstrap_env() -> None:
    """Keep the import side-effect free of any real database or secret."""
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    for name in ("DEEPSEEK_API_KEY", "QWEN_API_KEY", "DASHSCOPE_API_KEY",
                 "ZHIPU_API_KEY", "ZAI_API_KEY", "WECHAT_SECRET", "WECHAT_APPID"):
        os.environ[name] = ""
    os.environ.setdefault("JWT_SECRET_KEY", "route-snapshot-disposable-secret-32b")
    os.environ.setdefault("RAG_ENABLED", "false")
    if not os.environ.get("DATABASE_URL"):
        # A throwaway file next to nothing important; never an existing database.
        scratch = ROOT / "tmp" / "route-snapshot"
        scratch.mkdir(parents=True, exist_ok=True)
        os.environ["DATABASE_URL"] = "sqlite:///" + (scratch / "snapshot.db").as_posix()
    sys.path.insert(0, str(BACKEND))


def collect() -> list[dict]:
    import importlib

    routes: list[dict] = []
    for name in ROUTER_MODULES:
        try:
            module = importlib.import_module(f"app.routers.{name}")
        except Exception as exc:
            routes.append({"module": name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        router = getattr(module, "router", None)
        if router is None:
            routes.append({"module": name, "error": "no module-level 'router'"})
            continue
        for index, route in enumerate(getattr(router, "routes", [])):
            methods = getattr(route, "methods", None)
            routes.append(
                {
                    "module": name,
                    "index": index,
                    "path": getattr(route, "path", "<unknown>"),
                    "methods": sorted(methods) if methods else [],
                    "name": getattr(route, "name", ""),
                }
            )
    return routes


def _key(entry: dict) -> tuple:
    return (entry["module"], entry["index"], entry["path"], tuple(entry.get("methods", [])))


def compare(left: list[dict], right: list[dict]) -> int:
    """Report additions, removals, and reorderings. Reordering is a failure."""
    left_keys = [_key(e) for e in left]
    right_keys = [_key(e) for e in right]
    if left_keys == right_keys:
        print(f"IDENTICAL: {len(left_keys)} routes in the same registration order")
        return 0

    left_set, right_set = set(left_keys), set(right_keys)
    removed = sorted(left_set - right_set)
    added = sorted(right_set - left_set)
    for entry in removed:
        print(f"REMOVED  {entry[0]}[{entry[1]}] {entry[3]} {entry[2]}")
    for entry in added:
        print(f"ADDED    {entry[0]}[{entry[1]}] {entry[3]} {entry[2]}")
    if not removed and not added:
        print("SET IDENTICAL BUT ORDER CHANGED:")
        for before, after in zip(left_keys, right_keys, strict=True):
            if before != after:
                print(f"  expected {before[3]} {before[2]}")
                print(f"  actual   {after[3]} {after[2]}")
    print(f"DIFFERENT: left={len(left_keys)} right={len(right_keys)}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    parser.add_argument("--compare", nargs=2, metavar=("LEFT", "RIGHT"),
                        help="compare two saved JSON snapshots")
    parser.add_argument("--save", metavar="PATH", help="also write the snapshot to PATH")
    args = parser.parse_args()

    if args.compare:
        left = json.loads(Path(args.compare[0]).read_text(encoding="utf-8"))
        right = json.loads(Path(args.compare[1]).read_text(encoding="utf-8"))
        return compare(left, right)

    _bootstrap_env()
    routes = collect()

    if args.save:
        Path(args.save).write_text(
            json.dumps(routes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    if args.json:
        print(json.dumps(routes, indent=2, ensure_ascii=False))
        return 0

    for entry in routes:
        if "error" in entry:
            print(f"ERROR    {entry['module']}: {entry['error']}")
            continue
        methods = ",".join(entry["methods"]) or "-"
        print(f"{entry['module']}[{entry['index']:>2}] {methods:<16} {entry['path']}")
    print(f"\n{len(routes)} route entries across {len(ROUTER_MODULES)} modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
