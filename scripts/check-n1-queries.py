"""Static N+1 scanner for backend/app.

Finds database round-trips that sit *inside* a loop body, i.e. the query count
grows with the number of rows returned by the endpoint.

Usage:
    python scripts/check-n1-queries.py [root]            # scan a directory (default: backend/app)
    python scripts/check-n1-queries.py --git HEAD [root] # scan a git revision, not the worktree

A single file is also accepted, which is how the fixtures under
scripts/tests/fixtures/n1_gate/ are scanned.

Two kinds of finding are reported, both blocking under --fail-on-findings:

  real   a db.query()/db.get()/db.execute() call inside a loop body
  lazy   a relationship read on a loop variable whose query has no
         joinedload/selectinload/subqueryload/contains_eager

The second one exists because the first cannot see it: `question.user` on a row
inside a `for` loop issues one query per row without any `db.query()` in the
loop, so a scanner that only matches calls goes green while the endpoint still
does N+1. Eager options are resolved per loop variable, not per function: one
`joinedload` must not silence a second, unrelated loop.

A third class, `helper`, is reported but does not fail the gate: a per-row call
to a local function that itself queries. It is advisory because the scanner
cannot tell whether the caller short-circuits that query through an argument.

Exit codes: 0 ok / nothing found, 1 findings with --fail-on-findings,
2 bad usage or a path that does not exist. The acceptance criterion for a
cleanup batch is an empty finding list, not the exit code.

Three classes of false positive are separated out on purpose, because a naive
scanner reports them and they are not bugs:

  1. `for x in db.query(...).all():` -- the query is the loop *iterable*: one
     round-trip for the whole loop. Excluded structurally (we never look at the
     loop's `iter` node).
  2. `for attempt in range(3): db.execute(...)` -- a retry loop, a fixed small
     number of round-trips that does not scale with data. Reported separately as
     "retry/constant".
  3. `vals.count(x)` -- Python list/dict `.count()`, not SQL. Excluded because
     the call chain carries no `.query(` and the receiver is not a session.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

USAGE = """\
Static N+1 scanner: finds database round-trips that sit inside a loop body.

usage: check-n1-queries.py [--fail-on-findings] [--git REV] [PATH]

  PATH                 file or directory to scan (default: backend/app)
  --git REV            scan a git revision instead of the worktree
  --fail-on-findings   exit 1 when any real or lazy finding is present
  -h, --help           show this message

Findings:
  real   a db.query()/db.get()/db.execute() call inside a loop body
  lazy   a relationship read on a loop variable without joinedload or another
         eager option (one query per row, invisible to a call-only scan)

Exit codes: 0 ok / nothing found, 1 findings with --fail-on-findings,
2 bad usage or a path that does not exist. A path that does not exist is an
error, not a clean scan: reporting real=0 for it would pass a CI gate that
looked at no code.

Loop-local queries whose cost does not grow with data are reported separately
as retry/constant and never fail the gate: a query that is the loop iterable
(one round-trip for the whole loop), a fixed `for attempt in range(n)` retry
loop, and dict/list methods such as `mapping.get(k)` or `vals.count(v)`.
"""

# Methods that actually hit the database when called on a Query / Session.
TERMINALS = {
    'all', 'first', 'one', 'one_or_none', 'scalar', 'scalar_one',
    'scalar_one_or_none', 'count', 'get', 'execute', 'values', 'value_list',
    'scalars', 'delete', 'update', 'exists', 'paginate',
}
# Bare names that are a session, for `db.get(...)` / `db.execute(...)`.
SESSION_NAMES = {'db', 'session', 'sess', 's', 'conn', 'db_session', 'database'}

# Attributes declared as `relationship(...)` in app/models.py. Accessing one on a
# row inside a loop is a lazy load: one query per row, invisible to the
# db.query() detector above. Kept as a literal so the scanner stays stdlib-only
# and does not import the app; keep it in sync when a relationship is added.
RELATIONSHIP_ATTRS = {
    'user', 'student', 'teacher', 'processor', 'post', 'parent', 'session',
    'likes', 'comments', 'favorites',
}
# Options that make an attribute eager, so the access is free.
EAGER_OPTIONS = {'joinedload', 'selectinload', 'subqueryload', 'contains_eager'}

LOOP_NODES = (ast.For, ast.AsyncFor, ast.While)
COMP_NODES = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _chain(node: ast.AST):
    """Yield every node in the attribute/call spine of a call expression."""
    cur = node
    while True:
        yield cur
        if isinstance(cur, ast.Call):
            cur = cur.func
        elif isinstance(cur, ast.Attribute):
            cur = cur.value
        elif isinstance(cur, ast.Subscript):
            cur = cur.value
        else:
            return


def _is_query_expr(node: ast.AST) -> bool:
    """True when this expression evaluates to a Query object (not yet executed).

    Must be the outermost call spine of a plain `db.query(...)...` expression.
    A dict/list comprehension that merely *contains* a query is a materialised
    mapping, not a Query: treating it as one makes `profiles.get(t.id)` look
    like a database call, which is a false positive.
    """
    if not isinstance(node, ast.Call):
        return False
    for sub in _chain(node):
        if isinstance(sub, ast.Attribute) and sub.attr == 'query':
            return True
    return False


def _query_vars(func) -> set[str]:
    """Local names bound to a Query, e.g. `q = db.query(CrisisWarning).filter(...)`.

    Needed because the terminal call is often made through such a variable:

        pending_crisis_query = db.query(CrisisWarning).filter(...)
        pending_crisis_query.count()
        pending_crisis_query.first()

    Two round-trips per row, but the terminal calls carry no `.query(` in their
    own spine, so a chain-only detector under-counts them.
    """
    names: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and _is_query_expr(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _root_name(node: ast.AST):
    """The leftmost Name of an attribute/call/subscript spine, or None."""
    cur = node
    while True:
        if isinstance(cur, ast.Name):
            return cur
        if isinstance(cur, ast.Attribute):
            cur = cur.value
        elif isinstance(cur, ast.Call):
            cur = cur.func
        elif isinstance(cur, ast.Subscript):
            cur = cur.value
        else:
            return None


def _is_db_call(call: ast.Call, query_vars: set[str] = frozenset()) -> bool:
    """True when this call expression performs one database round-trip."""
    func = call.func
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr not in TERMINALS:
        return False

    spine = list(_chain(call))

    # `db.query(...)...<terminal>()` or `Model.query...<terminal>()`
    for node in spine:
        if isinstance(node, ast.Attribute) and node.attr == 'query':
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == 'query':
            return True

    # `q.count()` / `q.order_by(...).first()` where `q` is a Query bound earlier.
    root = _root_name(func.value)
    if root is not None and root.id in query_vars:
        return True

    # `db.get(...)`, `db.execute(...)`, `db.scalar(...)`
    if func.attr in {'get', 'execute', 'scalar', 'scalars'}:
        if root is not None and root.id in SESSION_NAMES:
            return True
    return False


def _db_calls_in(nodes, query_vars: set[str] = frozenset()) -> list[tuple[int, str]]:
    """Collect (lineno, text) of database round-trips in the given statements."""
    found = []
    for stmt in nodes:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call) and _is_db_call(node, query_vars):
                found.append((node.lineno, ast.unparse(node)[:90]))
    return found


def _is_range_loop(loop) -> bool:
    it = getattr(loop, 'iter', None)
    return isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range'


def _eager_in_expr(node) -> set[str]:
    """Relationship names made eager by an expression.

    `db.query(CrisisWarning).options(joinedload(CrisisWarning.student))` makes
    `w.student` free for the rows that query returns.
    """
    eager: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                and sub.func.id in EAGER_OPTIONS:
            for arg in sub.args:
                # joinedload(CrisisWarning.student) -> "student"
                if isinstance(arg, ast.Attribute):
                    eager.add(arg.attr)
                elif isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    eager.add(arg.value)
    return eager


def _is_query_bound(node) -> bool:
    """True when an expression is a query result or a Query object."""
    if not isinstance(node, (ast.Call, ast.Attribute)):
        return False
    for sub in _chain(node) if isinstance(node, ast.Call) else [node]:
        if isinstance(sub, ast.Attribute) and sub.attr in TERMINALS | {'query'}:
            return True
    return False


def _eager_by_var(func) -> dict[str, set[str]]:
    """Map every local name bound to a query to the relationships it eager-loads.

    Every query-bound name is recorded, including ones with an empty eager set.
    Scoping matters in both directions:

    - collecting eager options function-wide let one `joinedload` silence *every*
      loop in the function, so a second loop over a different, still-lazy query
      stopped being reported. Adding a joinedload to one query then looked like
      it had fixed a different loop.
    - recording only the names that *do* have eager options was not enough
      either: the second loop's variable was absent, so it fell back to the
      function-wide set and was silenced anyway. A name bound to a plain query
      has an empty eager set, and that empty set is the correct answer.

    Eager options propagate through chained assignments, because the common
    shape builds a query first and materialises it later:

        query = db.query(Question).options(joinedload(Question.user))
        query = query.filter(...)
        questions = query.order_by(...).all()

    `questions` carries no joinedload of its own; it inherits it from `query`.
    Without the propagation that pattern reports a lazy load the backend had
    already fixed, which is exactly the false positive this must avoid.
    """
    by_var: dict[str, set[str]] = {}
    # Two passes: a query built up over several statements needs the earlier
    # names resolved before the later ones inherit from them.
    for _ in range(3):
        changed = False
        for node in ast.walk(func):
            if not isinstance(node, ast.Assign):
                continue
            eager = set(_eager_in_expr(node.value))
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.Name) and sub.id in by_var:
                    eager |= by_var[sub.id]
            if not (_is_query_bound(node.value) or eager
                    or any(isinstance(s, ast.Name) and s.id in by_var
                           for s in ast.walk(node.value))):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    before = by_var.get(target.id, set())
                    merged = before | eager
                    if merged != before:
                        changed = True
                    by_var[target.id] = merged
        if not changed:
            break
    return by_var


def _eager_for_loop(loop, eager_by_var: dict[str, set[str]], func_eager: set[str]) -> set[str]:
    """The eager set that applies to this loop's rows.

    Resolved through the variable the loop iterates over. Only when that variable
    cannot be traced back to a query at all (a parameter, a helper's return
    value) does it fall back to the function-wide set, where a false positive on
    already-fixed code would cost more credibility than a miss.
    """
    it = getattr(loop, 'iter', None)
    if isinstance(it, ast.Name) and it.id in eager_by_var:
        return eager_by_var[it.id]
    inline = _eager_in_expr(it) if it is not None else set()
    if inline:
        return inline
    if _is_query_bound(it):
        return set()
    return func_eager


def _lazy_loads_in(loop, eager: set[str]) -> list[tuple[int, str]]:
    """Relationship reads on this loop's own variable that are not eager-loaded.

    Only the variable this loop binds counts. A nested loop rebinds the name, so
    the inner one reports its own accesses; nothing is double-counted.
    """
    target = getattr(loop, 'target', None)
    if target is None:  # while loop: no loop variable, so no per-row relationship
        return []
    names = {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}
    if not names:
        return []
    found = []
    for node in ast.walk(loop):
        if isinstance(node, ast.Attribute) and node.attr in RELATIONSHIP_ATTRS \
                and node.attr not in eager \
                and isinstance(node.value, ast.Name) and node.value.id in names:
            found.append((node.lineno, ast.unparse(node)[:90]))
    # One entry per line: `w.student.name` and `w.student.username` are the same
    # lazy load, not two.
    seen: dict[int, str] = {}
    for lineno, text in found:
        seen.setdefault(lineno, text)
    return sorted(seen.items())


def _comp_body(node):
    """The part of a comprehension that runs once per element.

    Never the `.generators` part: a comprehension's iterator is evaluated once
    and is where the batched prefetch query lives
    (`{p.user_id: p for p in db.query(TeacherProfile).filter(...).all()}`).
    Walking the whole node instead reports that prefetch as a per-row query,
    which is exactly the false positive this tool exists to avoid.
    """
    if isinstance(node, ast.DictComp):
        return [node.key, node.value]
    return [node.elt]


def _guarded_by_param(func) -> set[str]:
    """Parameters that guard a query in this helper: `if p is not None: ... query`.

    A helper can make its query conditional on an argument the caller supplies,
    which turns a per-row call into zero queries per row:

        def _serialize(db, warning, message_content=None):
            if message_content is not None:   # batched caller passes it
                msg_content = message_content
            else:
                msg = db.query(...).first()    # single-record path only

    The scanner cannot evaluate the branch, but it can see that the branch exists
    and that it is keyed on a parameter. A caller that passes a value for that
    parameter may be short-circuiting the query, so the finding is downgraded
    rather than reported as a certain per-row query. Deciding it exactly needs
    the runtime statement count, which a static AST scan cannot produce.
    """
    params = {a.arg for a in func.args.args}
    guarded: set[str] = set()
    for node in ast.walk(func):
        if not isinstance(node, ast.If):
            continue
        names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
        keyed = names & params
        if not keyed:
            continue
        for branch in (node.body, node.orelse):
            for sub in branch:
                for inner in ast.walk(sub):
                    if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute) \
                            and inner.func.attr in TERMINALS:
                        try:
                            if '.query(' in ast.unparse(inner):
                                guarded |= keyed
                        except Exception:  # pragma: no cover
                            pass
    return guarded


def _helper_queries(tree) -> dict[str, list[str]]:
    """Local functions that hit the database, keyed by name.

    This is the cross-function half of the problem. A loop that calls a local
    helper once per row is doing N+1 just as surely as one that calls
    `db.query()` inline, but the call itself carries no `.query(` and the
    relationship read happens inside the helper, on a *parameter* -- so both
    existing detectors miss it:

        posts = query.all()
        return [_get_treehole_response(p, uid, db) for p in posts]

    `_get_treehole_response` runs five counts per post. The gate reported
    `real=0 lazy=0` on that endpoint.

    Only helpers that actually issue a query or read a relationship off one of
    their parameters are recorded, so `_format_dt` or `_sse_event` in a loop
    stays invisible: a helper that does no I/O cannot turn a loop into N+1.
    """
    helpers: dict[str, list[str]] = {}
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params = [a.arg for a in func.args.args]
        reasons: list[str] = []
        for node in ast.walk(func):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr in TERMINALS:
                try:
                    if '.query(' in ast.unparse(node) or 'session.' in ast.unparse(node):
                        reasons.append('query')
                        break
                except Exception:  # pragma: no cover - unparse is total on real code
                    pass
        if not reasons:
            for node in ast.walk(func):
                if isinstance(node, ast.Attribute) and node.attr in RELATIONSHIP_ATTRS \
                        and isinstance(node.value, ast.Name) and node.value.id in params:
                    reasons.append(f'relationship:{node.attr}')
                    break
        if reasons:
            helpers[func.name] = reasons
    return helpers


def _helper_guards(tree) -> dict[str, tuple[list[str], set[str]]]:
    """Map helper name -> (parameter order, parameters that guard its query)."""
    guards: dict[str, tuple[list[str], set[str]]] = {}
    for func in ast.walk(tree):
        if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            guarded = _guarded_by_param(func)
            if guarded:
                params = [a.arg for a in func.args.args]
                guards[func.name] = (params, guarded)
    return guards


def _call_passes_guard(call, params: list[str], guarded: set[str]) -> bool:
    """True when the call site supplies a value for a parameter that guards the query.

    A default (`None`) is the "go query" path, so only an explicitly passed
    positional or keyword argument counts: passing it is what lets the helper
    skip the query. Positional arguments are mapped by index, because a guard on
    the third parameter must not be considered fed by a call that passes only
    the first two.
    """
    supplied = {params[i] for i in range(len(call.args)) if i < len(params)}
    supplied |= {kw.arg for kw in call.keywords if kw.arg}
    return bool(supplied & guarded)


def _per_row_helper_calls(loop, helpers: dict[str, list[str]], self_name: str,
                          guards: dict[str, set[str]] | None = None):
    """Calls to DB-touching local helpers from a per-row position.

    The comprehension's iterator is skipped for the same reason `_comp_body`
    exists: a helper called once to build the batch is not a per-row call.

    A helper whose query is guarded by a parameter the caller supplies is
    reported with `?` after the reason, meaning "may be short-circuited": the
    scanner can see the branch but cannot evaluate it.
    """
    guards = guards or {}
    parts: list = []
    if isinstance(loop, (ast.For, ast.AsyncFor)):
        parts = loop.body if isinstance(loop.body, list) else [loop.body]
    elif isinstance(loop, COMP_NODES):
        parts = _comp_body(loop)
    else:
        return  # while loop: no per-row iteration variable to speak of
    for sub in parts:
        for call in ast.walk(sub):
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)):
                continue
            name = call.func.id
            if name == self_name or name not in helpers:
                continue
            why = helpers[name]
            entry = guards.get(name)
            if entry and _call_passes_guard(call, *entry):
                why = [*why, 'may be short-circuited by an argument']
            yield call.lineno, name, why


def scan_tree(root: Path):
    """Yield findings: (path, func, kind, lineno, count, sample).

    A single file is accepted as well as a directory, so a fixture can be scanned
    directly instead of having to sit in its own folder.

    A path that does not exist yields nothing, and the caller must treat that as
    an error: `rglob` on a missing directory silently returns an empty iterator,
    so a typo in the CI step's path would print `real=0` and pass the gate while
    scanning no code at all.
    """
    if not root.exists():
        raise FileNotFoundError(str(root))
    paths = [root] if root.is_file() else sorted(root.rglob('*.py'))
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except SyntaxError as exc:  # pragma: no cover - defensive
            print(f'!! parse error {path}: {exc}', file=sys.stderr)
            continue
        helpers = _helper_queries(tree)
        guards = _helper_guards(tree)
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            qvars = _query_vars(func)
            eager_by_var = _eager_by_var(func)
            func_eager = _eager_in_expr(func)
            for node in ast.walk(func):
                if isinstance(node, LOOP_NODES):
                    calls = _db_calls_in(node.body, qvars)
                    if calls:
                        kind = 'retry/constant' if _is_range_loop(node) else 'real'
                        yield (path, func.name, kind, node.lineno, len(calls), calls[0][1])
                    for lineno, text in _lazy_loads_in(node, _eager_for_loop(node, eager_by_var, func_eager)):
                        yield (path, func.name, 'lazy', lineno, 1, text)
                    if not _is_range_loop(node):
                        for lineno, helper, why in _per_row_helper_calls(node, helpers, func.name, guards):
                            yield (path, func.name, 'helper', lineno, 1,
                                   f'{helper}() [{", ".join(why)}]')
                elif isinstance(node, COMP_NODES):
                    # Comprehension: everything inside runs once per element.
                    calls = _db_calls_in(_comp_body(node), qvars)
                    if calls:
                        yield (path, func.name, 'real', node.lineno, len(calls), calls[0][1])
                    for lineno, helper, why in _per_row_helper_calls(node, helpers, func.name, guards):
                        yield (path, func.name, 'helper', lineno, 1,
                               f'{helper}() [{", ".join(why)}]')


def scan_git(rev: str, root: Path):
    """Scan a git revision without touching the worktree.

    Same trap as scan_tree: `git ls-tree` on a path that is not in the revision
    prints nothing and exits 0, so a typo would look like a clean scan.
    """
    out = subprocess.run(
        ['git', 'ls-tree', '-r', '--name-only', rev, str(root).replace('\\', '/')],
        capture_output=True, text=True, encoding='utf-8', errors='replace', check=True,
    ).stdout.split()
    if not out:
        raise FileNotFoundError(f'{rev}:{root}')
    for name in out:
        if not name.endswith('.py'):
            continue
        src = subprocess.run(['git', 'show', f'{rev}:{name}'],
                             capture_output=True, text=True, encoding='utf-8',
                             errors='replace', check=True).stdout
        try:
            tree = ast.parse(src, filename=name)
        except SyntaxError:
            continue
        helpers = _helper_queries(tree)
        guards = _helper_guards(tree)
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            qvars = _query_vars(func)
            eager_by_var = _eager_by_var(func)
            func_eager = _eager_in_expr(func)
            for node in ast.walk(func):
                if isinstance(node, LOOP_NODES):
                    calls = _db_calls_in(node.body, qvars)
                    if calls:
                        kind = 'retry/constant' if _is_range_loop(node) else 'real'
                        yield (Path(name), func.name, kind, node.lineno, len(calls), calls[0][1])
                    for lineno, text in _lazy_loads_in(node, _eager_for_loop(node, eager_by_var, func_eager)):
                        yield (Path(name), func.name, 'lazy', lineno, 1, text)
                    if not _is_range_loop(node):
                        for lineno, helper, why in _per_row_helper_calls(node, helpers, func.name, guards):
                            yield (Path(name), func.name, 'helper', lineno, 1,
                                   f'{helper}() [{", ".join(why)}]')
                elif isinstance(node, COMP_NODES):
                    calls = _db_calls_in(_comp_body(node), qvars)
                    if calls:
                        yield (Path(name), func.name, 'real', node.lineno, len(calls), calls[0][1])
                    for lineno, helper, why in _per_row_helper_calls(node, helpers, func.name, guards):
                        yield (Path(name), func.name, 'helper', lineno, 1,
                               f'{helper}() [{", ".join(why)}]')


def main(argv: list[str]) -> int:
    rev = None
    fail_on_findings = False
    positional: list[str] = []
    args = argv[1:]
    i = 0
    # Scan *every* argument, not just the leading ones. Parsing only while
    # args[0] starts with "--" silently drops anything after the path, so
    # `check-n1-queries.py backend/app --fail-on-findings` looked like a
    # passing gate while checking nothing. An unknown option is an error, never
    # silently ignored.
    while i < len(args):
        arg = args[i]
        if arg in ('--help', '-h'):
            print(USAGE)
            return 0
        if arg == '--git':
            if i + 1 >= len(args):
                print('--git needs a revision', file=sys.stderr)
                return 2
            rev = args[i + 1]
            i += 2
        elif arg == '--fail-on-findings':
            fail_on_findings = True
            i += 1
        elif arg.startswith('--'):
            print(f'unknown option {arg}', file=sys.stderr)
            return 2
        else:
            positional.append(arg)
            i += 1
    if len(positional) > 1:
        print(f'unexpected extra arguments: {" ".join(positional[1:])}', file=sys.stderr)
        return 2
    root = Path(positional[0]) if positional else Path('backend/app')

    if rev:
        try:
            findings = list(scan_git(rev, root))
        except FileNotFoundError:
            print(f'no such path in {rev}: {root}', file=sys.stderr)
            return 2
    else:
        try:
            findings = list(scan_tree(root))
        except FileNotFoundError:
            # A missing path must not read as a clean scan: rglob on a typo'd
            # directory yields nothing, and "real=0" would pass the CI gate
            # without having looked at a single file.
            print(f'no such path: {root}', file=sys.stderr)
            return 2
    real = [f for f in findings if f[2] == 'real']
    lazy = [f for f in findings if f[2] == 'lazy']
    helper = [f for f in findings if f[2] == 'helper']
    benign = [f for f in findings if f[2] not in ('real', 'lazy', 'helper')]

    print(f'# scanned {"git:" + rev if rev else root}  '
          f'real={len(real)}  lazy={len(lazy)}  helper={len(helper)}  '
          f'benign={len(benign)}\n')
    if real:
        print(f'{"file":44} {"function":34} {"line":>6} {"calls":>5}')
        print('-' * 95)
        for path, func, _kind, lineno, count, sample in sorted(real, key=lambda f: (str(f[0]), f[3])):
            print(f'{str(path):44} {func:34} {lineno:6} {count:5}')
            print(f'{"":44}   e.g. {sample}')
    if lazy:
        print('\n# relationship read on a loop variable without eager loading '
              '(one query per row; joinedload/selectinload clears it)')
        for path, func, _kind, lineno, _count, sample in sorted(lazy, key=lambda f: (str(f[0]), f[3])):
            print(f'  {path}:{lineno} {func} -> {sample}')
    if benign:
        print('\n# excluded as retry/constant (fixed small count, does not scale with data)')
        for path, func, _kind, lineno, count, _sample in sorted(benign, key=lambda f: (str(f[0]), f[3])):
            print(f'  {path}:{lineno} {func} ({count} call(s))')
    if helper:
        print('\n# per-row call to a local helper that itself queries or reads a '
              'relationship (one query per row, invisible to a call-only scan)')
        for path, func, _kind, lineno, _count, sample in sorted(helper, key=lambda f: (str(f[0]), f[3])):
            print(f'  {path}:{lineno} {func} -> {sample}')
    if fail_on_findings and (real or lazy):
        print(f'\nFAIL: {len(real)} loop-local query call(s) and '
              f'{len(lazy)} un-eager relationship read(s) found', file=sys.stderr)
        return 1
    if helper:
        # Advisory, not blocking, and deliberately so. This class has a
        # false-positive mode the scanner cannot decide: a helper whose query is
        # short-circuited by an argument the caller supplies.
        #
        #   def _serialize(db, warning, message_content=None):
        #       if message_content is not None:   # caller passes it -> no query
        #           ...
        #       else:
        #           db.query(...).first()
        #
        # `get_pending_crisis_records` is reported here for exactly that reason,
        # although its batched caller pre-computes the message and the
        # relationship it reads is joinedloaded. Measured on this tree, 1 of 3
        # findings is of that kind. A gate that fails a third of the time on
        # code that is already correct is a gate that gets switched off, so this
        # stays visible in the report and out of the exit code until the
        # short-circuit can be decided statically.
        print('\nNOTE: the per-row helper calls above are advisory and do not fail '
              'the gate (see _helper_queries).', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
