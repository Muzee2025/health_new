"""Static N+1 scanner for backend/app.

Finds database round-trips that sit *inside* a loop body, i.e. the query count
grows with the number of rows returned by the endpoint.

Usage:
    python tmp/n1_scan.py [root]            # scan a directory tree (default: backend/app)
    python tmp/n1_scan.py --git HEAD [root] # scan a git revision instead of the worktree

Exit code: 0 always (it is a reporting tool). The acceptance criterion for a
cleanup batch is an empty "real N+1" list, not the exit code.

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

# Methods that actually hit the database when called on a Query / Session.
TERMINALS = {
    'all', 'first', 'one', 'one_or_none', 'scalar', 'scalar_one',
    'scalar_one_or_none', 'count', 'get', 'execute', 'values', 'value_list',
    'scalars', 'delete', 'update', 'exists', 'paginate',
}
# Bare names that are a session, for `db.get(...)` / `db.execute(...)`.
SESSION_NAMES = {'db', 'session', 'sess', 's', 'conn', 'db_session', 'database'}

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


def scan_tree(root: Path):
    """Yield findings: (path, func, kind, lineno, count, sample)."""
    for path in sorted(root.rglob('*.py')):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except SyntaxError as exc:  # pragma: no cover - defensive
            print(f'!! parse error {path}: {exc}', file=sys.stderr)
            continue
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            qvars = _query_vars(func)
            for node in ast.walk(func):
                if isinstance(node, LOOP_NODES):
                    calls = _db_calls_in(node.body, qvars)
                    if not calls:
                        continue
                    kind = 'retry/constant' if _is_range_loop(node) else 'real'
                    yield (path, func.name, kind, node.lineno, len(calls), calls[0][1])
                elif isinstance(node, COMP_NODES):
                    # Comprehension: everything inside runs once per element.
                    calls = _db_calls_in(_comp_body(node), qvars)
                    if calls:
                        yield (path, func.name, 'real', node.lineno, len(calls), calls[0][1])


def scan_git(rev: str, root: Path):
    """Scan a git revision without touching the worktree."""
    out = subprocess.run(
        ['git', 'ls-tree', '-r', '--name-only', rev, str(root).replace('\\', '/')],
        capture_output=True, text=True, encoding='utf-8', errors='replace', check=True,
    ).stdout.split()
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
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            qvars = _query_vars(func)
            for node in ast.walk(func):
                if isinstance(node, LOOP_NODES):
                    calls = _db_calls_in(node.body, qvars)
                    if not calls:
                        continue
                    kind = 'retry/constant' if _is_range_loop(node) else 'real'
                    yield (Path(name), func.name, kind, node.lineno, len(calls), calls[0][1])
                elif isinstance(node, COMP_NODES):
                    calls = _db_calls_in(_comp_body(node), qvars)
                    if calls:
                        yield (Path(name), func.name, 'real', node.lineno, len(calls), calls[0][1])


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

    findings = list(scan_git(rev, root) if rev else scan_tree(root))
    real = [f for f in findings if f[2] == 'real']
    benign = [f for f in findings if f[2] != 'real']

    print(f'# scanned {"git:" + rev if rev else root}  '
          f'real={len(real)}  benign={len(benign)}\n')
    if real:
        print(f'{"file":44} {"function":34} {"line":>6} {"calls":>5}')
        print('-' * 95)
        for path, func, _kind, lineno, count, sample in sorted(real, key=lambda f: (str(f[0]), f[3])):
            print(f'{str(path):44} {func:34} {lineno:6} {count:5}')
            print(f'{"":44}   e.g. {sample}')
    if benign:
        print('\n# excluded as retry/constant (fixed small count, does not scale with data)')
        for path, func, _kind, lineno, count, _sample in sorted(benign, key=lambda f: (str(f[0]), f[3])):
            print(f'  {path}:{lineno} {func} ({count} call(s))')
    if fail_on_findings and real:
        print(f'\nFAIL: {len(real)} loop-local database round-trip(s) found', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
