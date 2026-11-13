"""Dump the backend route table as a stable, diffable snapshot.

Read-only: imports the app, prints routes, writes nothing unless --save is given.

Usage (from the repository root):
  .venv/Scripts/python.exe backend/scripts/dump-route-table.py
  .venv/Scripts/python.exe backend/scripts/dump-route-table.py --json
  .venv/Scripts/python.exe backend/scripts/dump-route-table.py --check
  .venv/Scripts/python.exe backend/scripts/dump-route-table.py --compare a.json b.json

Scope: the snapshot covers the fully mounted application, both HTTP and WebSocket.
Paths and prefixes come from the mounted app, so include_router() prefixes and
@app-level routes are included. Two narrower sources were tried and are wrong for a
gate:

* app.routes holds lazy _IncludedRouter wrappers on FastAPI 0.140 (18 entries, only 2
  APIRoute), so most endpoints are invisible there.
* Walking each router module's own .routes ignores the prefix given at mount time
  (advanced_chat is mounted under /api/advanced-ai, 10 pairs) and misses @app routes
  such as "/" and /api/v1/model/current. That version reported 98 pairs where the
  mounted app has 99, with every advanced-ai path spelled wrongly.

WebSocket routes are recorded with the method "WS". They are NOT in app.openapi() --
OpenAPI describes HTTP operations only -- so they cannot come from the same source as
the HTTP pairs. They are walked from APIWebSocketRoute objects instead, and counted a
second time by an independent scan of the app tree, so a FastAPI internal change that
hides them from the walk fails the gate instead of silently dropping /api/ws.

Registration order is part of the snapshot because it is semantic: /articles/page must
be registered before /articles/{article_id} on both the student and teacher routers,
otherwise the literal path is captured by the wildcard and returns 422 (article_id
fails int parsing), not 404. --check therefore fails on a pure reordering, which a set
comparison would miss.
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

# The committed snapshot that --check compares against. Regenerate with --save after
# an intended routing change, so the diff of this file is the review artefact.
BASELINE = Path(__file__).resolve().with_name("route-baseline.json")


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


WS_METHOD = "WS"


def _methods_of(route) -> list[str]:
    """HTTP methods of one route, or ["WS"] for a WebSocket endpoint.

    APIWebSocketRoute has no ``methods`` attribute at all, so the previous walk skipped
    it and the snapshot claimed to cover "the whole app" while /api/ws was invisible.
    """
    from fastapi.routing import APIWebSocketRoute

    if isinstance(route, APIWebSocketRoute):
        return [WS_METHOD]
    return [
        method.upper()
        for method in (getattr(route, "methods", None) or ())
        if method.upper() not in ("HEAD", "OPTIONS")
    ]


def _mounted_routes(application):
    """Yield (registration_index, path, method) in true registration order.

    FastAPI 0.140 stores include_router() results as lazy ``_IncludedRouter`` entries in
    app.routes, so app.openapi() knows the paths but not the order, and app.routes alone
    knows the order but not the paths. Each lazy entry keeps the router it wrapped in
    ``original_router`` and the mount arguments in ``include_context`` (whose ``prefix``
    is where e.g. /api/advanced-ai comes from), so walking both reconstructs the real
    order. collect() asserts the HTTP part matches app.openapi() exactly and the
    WebSocket part matches an independent count.
    """
    from fastapi.routing import APIRoute, APIWebSocketRoute

    index = 0
    for route in application.routes:
        if type(route).__name__ == "_IncludedRouter":
            router = route.original_router
            context = getattr(route, "include_context", None)
            mount_prefix = getattr(context, "prefix", "") or ""
            for inner in getattr(router, "routes", []):
                path = getattr(inner, "path", None)
                if not path:
                    continue
                # inner.path already contains the router's own prefix (e.g. auth's
                # "/api/register" under router.prefix "/api"); only the prefix given to
                # include_router() is still missing.
                full = f"{mount_prefix}{path}"
                for method in _methods_of(inner):
                    yield index, full, method
                    index += 1
            continue
        if isinstance(route, (APIRoute, APIWebSocketRoute)):
            for method in _methods_of(route):
                yield index, route.path, method
                index += 1


def _count_websocket_routes(node, _seen=None) -> int:
    """Count WebSocket endpoints reachable from a router or app, descending wrappers.

    Deliberately independent of _mounted_routes(): it only counts, and it descends
    original_router, so if a FastAPI internal change ever hides WS endpoints from the
    ordered walk the two numbers disagree and collect() fails instead of quietly
    dropping /api/ws from the snapshot.
    """
    from fastapi.routing import APIWebSocketRoute

    if _seen is None:
        _seen = set()
    if id(node) in _seen:
        return 0
    _seen.add(id(node))

    total = 0
    for route in getattr(node, "routes", ()) or ():
        if isinstance(route, APIWebSocketRoute):
            total += 1
        original = getattr(route, "original_router", None)
        if original is not None:
            total += _count_websocket_routes(original, _seen)
    return total


def collect() -> tuple[list[dict], list[str]]:
    """Return (routes, failures) for the fully mounted application, in registration order.

    Paths and prefixes come from the mounted app (include_router() prefixes included,
    plus @app routes such as "/"), and the order comes from walking the real route
    objects. A failure to import the app is fatal: the previous version recorded import
    errors as data, so --json exited 0 and compare() raised KeyError on the entry that
    had no "index".
    """
    try:
        from app.main import app as application
    except Exception as exc:
        return [], [f"app.main: {type(exc).__name__}: {exc}"]

    try:
        expected = {
            (path, method.upper())
            for path, operations in application.openapi().get("paths", {}).items()
            for method in operations
        }
    except Exception as exc:
        return [], [f"app.openapi(): {type(exc).__name__}: {exc}"]

    routes = [
        {"order": order, "path": path, "method": method}
        for order, path, method in _mounted_routes(application)
    ]
    http_seen = {(e["path"], e["method"]) for e in routes if e["method"] != WS_METHOD}
    ws_seen = [e for e in routes if e["method"] == WS_METHOD]

    # HTTP and WebSocket are verified separately because they have different sources of
    # truth: HTTP against app.openapi(), WebSocket against an independent count, since
    # OpenAPI never describes WebSocket endpoints.
    missing, extra = expected - http_seen, http_seen - expected
    if missing:
        return [], [f"walked routes missing from app.openapi(): {sorted(missing)[:5]}"]
    if extra:
        return [], [f"walked routes not in app.openapi(): {sorted(extra)[:5]}"]

    ws_expected = _count_websocket_routes(application)
    if len(ws_seen) != ws_expected:
        return [], [
            f"websocket routes: walk found {len(ws_seen)}, independent count found "
            f"{ws_expected}; the snapshot would silently drop a WS endpoint"
        ]
    if ws_expected and not ws_seen:
        return [], ["websocket routes exist but none were walked"]
    return routes, []


def _key(entry: dict) -> tuple:
    return (entry["path"], entry["method"])


def compare(left: list[dict], right: list[dict]) -> int:
    """Report additions, removals, and reorderings. Reordering is a failure."""
    left_keys = [_key(e) for e in left]
    right_keys = [_key(e) for e in right]
    if left_keys == right_keys:
        print(f"IDENTICAL: {len(left_keys)} path+method pairs in the same order")
        return 0

    left_set, right_set = set(left_keys), set(right_keys)
    removed = sorted(left_set - right_set)
    added = sorted(right_set - left_set)
    for path, method in removed:
        print(f"REMOVED  {method:<7} {path}")
    for path, method in added:
        print(f"ADDED    {method:<7} {path}")
    if not removed and not added:
        print("SET IDENTICAL BUT ORDER CHANGED:")
        for before, after in zip(left_keys, right_keys, strict=True):
            if before != after:
                print(f"  expected {before[1]:<7} {before[0]}")
                print(f"  actual   {after[1]:<7} {after[0]}")
    print(f"DIFFERENT: left={len(left_keys)} right={len(right_keys)}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    parser.add_argument("--compare", nargs=2, metavar=("LEFT", "RIGHT"),
                        help="compare two saved JSON snapshots")
    parser.add_argument("--save", metavar="PATH", help="also write the snapshot to PATH")
    parser.add_argument("--check", action="store_true",
                        help=f"compare the live table against {BASELINE.name} and exit 1 on any drift")
    args = parser.parse_args()

    if args.compare:
        left = json.loads(Path(args.compare[0]).read_text(encoding="utf-8"))
        right = json.loads(Path(args.compare[1]).read_text(encoding="utf-8"))
        return compare(left, right)

    _bootstrap_env()
    routes, failures = collect()
    if failures:
        # Fatal in every mode: a snapshot with a module missing is not comparable, and
        # silently succeeding here is exactly how a gate would pass on broken code.
        for failure in failures:
            print(f"IMPORT FAILURE: {failure}")
        return 1

    if args.check:
        if not BASELINE.exists():
            print(f"FAIL: baseline {BASELINE} is missing; regenerate with --save")
            return 1
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        return compare(baseline, routes)

    if args.save:
        Path(args.save).write_text(
            json.dumps(routes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    if args.json:
        print(json.dumps(routes, indent=2, ensure_ascii=False))
        return 0

    for entry in routes:
        print(f"{entry['order']:>4} {entry['method']:<7} {entry['path']}")
    print(f"\n{len(routes)} path+method pairs from the mounted app")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
