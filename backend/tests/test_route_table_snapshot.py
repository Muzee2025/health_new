"""The route table must not drift, and registration order is part of it.

Route registration order is semantic in this app, not cosmetic: ``/articles/page``
must be registered before ``/articles/{article_id}`` on both the student and the
teacher router, or the literal path is captured by the wildcard and returns 422
(``article_id`` fails integer parsing) instead of the page. A set comparison of
paths would call that change identical, so the snapshot records order too.

``backend/scripts/route-baseline.json`` is the committed snapshot and
``dump-route-table.py`` is what regenerates it (``--save``) and checks it
(``--check``). This test is the in-suite half: it fails the baseline run when the
table drifts, so a router split cannot quietly reorder a route.

The snapshot is taken from the mounted application, not from ``app.routes``:
FastAPI 0.140 keeps ``include_router()`` results as lazy ``_IncludedRouter``
wrappers, so ``app.routes`` has 18 entries and only 6 with path+methods while the
mounted app serves 88 paths. Walking each router module's own ``.routes`` instead
would drop the mount prefix (``/api/advanced-ai``) and the ``@app`` routes.

Regenerating after an *intended* change is deliberate: run
``python backend/scripts/dump-route-table.py --save backend/scripts/route-baseline.json``
and review the diff of that file, which is the artefact this test protects.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
SCRIPT = BACKEND / "scripts" / "dump-route-table.py"
BASELINE = BACKEND / "scripts" / "route-baseline.json"


def _load_dump_module():
    """Import dump-route-table.py by path; the hyphen makes it unimportable by name."""
    spec = importlib.util.spec_from_file_location("dump_route_table", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_route_table_matches_the_committed_snapshot():
    module = _load_dump_module()

    # collect() needs DATABASE_URL because app.database refuses to guess one; the
    # baseline runner already sets a disposable value. Never fall back to a real
    # database here: a wrong URL would only be read, but it would still be the
    # developer's data and the test must not depend on the local environment.
    assert os.environ.get("DATABASE_URL"), (
        "run this through scripts/run-backend-baseline.py, which sets a disposable "
        "DATABASE_URL; app.database raises without one"
    )

    live, failures = module.collect()
    assert not failures, failures
    assert live, "collected no routes; the snapshot would be compared against nothing"

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert len(baseline) > 50, f"baseline looks truncated: {len(baseline)} entries"

    # compare() prints the offending pairs and returns 1 on any addition, removal,
    # or pure reordering. Reordering has to be caught: see the module docstring.
    assert module.compare(baseline, live) == 0, (
        "the route table drifted from backend/scripts/route-baseline.json. If the "
        "change is intended, regenerate the snapshot with --save and review its diff."
    )


def test_compare_rejects_a_pure_reordering():
    """Guard the guard: a set comparison would pass, so prove compare() does not.

    Without this, someone could "fix" a failing gate by sorting the snapshot or by
    comparing sets, and the order-dependent /articles/page bug would come back
    silently.
    """
    module = _load_dump_module()
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert len(baseline) >= 4, baseline

    swapped = [dict(entry) for entry in baseline]
    swapped[1], swapped[2] = swapped[2], swapped[1]
    for index, entry in enumerate(swapped):
        entry["order"] = index

    # Same path+method set, different order: the exact change a set comparison misses.
    assert {(e["path"], e["method"]) for e in baseline} == {
        (e["path"], e["method"]) for e in swapped
    }
    assert module.compare(baseline, swapped) == 1
