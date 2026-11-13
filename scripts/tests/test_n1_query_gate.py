"""Tests for scripts/check-n1-queries.py.

The point of this gate is its judgement, so the cases below are read-and-verified
snippets: each one is obviously an N+1 or obviously not. A gate that only ever
prints a number is useless; a gate that cannot fail is worse.
"""
import importlib.util
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / 'scripts' / 'check-n1-queries.py'


def _load():
    spec = importlib.util.spec_from_file_location('check_n1_queries', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ClassifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load()

    def _classify(self, src):
        import ast
        mod = self.mod
        tree = ast.parse(textwrap.dedent(src))
        found = []
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            qvars = mod._query_vars(func)
            for node in ast.walk(func):
                if isinstance(node, mod.LOOP_NODES):
                    calls = mod._db_calls_in(node.body, qvars)
                    if calls:
                        kind = 'retry/constant' if mod._is_range_loop(node) else 'real'
                        found.append((kind, len(calls)))
                elif isinstance(node, mod.COMP_NODES):
                    calls = mod._db_calls_in(mod._comp_body(node), qvars)
                    if calls:
                        found.append(('real', len(calls)))
        return found

    # --- real N+1: must be found -------------------------------------------

    def test_finds_per_row_lookup(self):
        got = self._classify('''
            def f(db, rows):
                for r in rows:
                    db.query(User).filter(User.id == r.uid).first()
                return rows
        ''')
        self.assertEqual(got, [('real', 1)])

    def test_finds_two_lookups_per_row(self):
        got = self._classify('''
            def f(db, rows):
                for r in rows:
                    db.query(User).filter(User.id == r.uid).first()
                    db.query(Profile).filter(Profile.id == r.uid).first()
                return rows
        ''')
        self.assertEqual(got, [('real', 2)])

    def test_finds_terminal_called_through_query_variable(self):
        # `q.count()` and `q.order_by(...).first()` carry no `.query(` in their
        # own spine, so a chain-only detector under-counts. Two round-trips.
        got = self._classify('''
            def f(db, rows):
                for r in rows:
                    q = db.query(Warning).filter(Warning.sid == r.id)
                    q.count()
                    q.order_by(Warning.created_at.desc()).first()
                return rows
        ''')
        self.assertEqual(got, [('real', 2)])

    def test_finds_query_inside_comprehension_body(self):
        got = self._classify('''
            def f(db, rows):
                return [db.query(User).filter(User.id == r.uid).first() for r in rows]
        ''')
        self.assertEqual(got, [('real', 1)])

    def test_finds_db_get_in_while_loop(self):
        got = self._classify('''
            def f(db, ids):
                i = 0
                while i < len(ids):
                    db.get(User, ids[i])
                    i += 1
                return i
        ''')
        self.assertEqual(got, [('real', 1)])

    # --- false positives: must NOT be reported -----------------------------

    def test_ignores_query_that_is_the_loop_iterable(self):
        # One round-trip for the whole loop: the batched prefetch pattern.
        got = self._classify('''
            def f(db, ids):
                for p in db.query(Profile).filter(Profile.uid.in_(ids)).all():
                    pass
                return ids
        ''')
        self.assertEqual(got, [])

    def test_ignores_dict_comprehension_built_from_batched_query(self):
        got = self._classify('''
            def f(db, ids):
                m = {p.uid: p for p in db.query(Profile).filter(Profile.uid.in_(ids)).all()}
                for k in m:
                    m.get(k)
                return m
        ''')
        self.assertEqual(got, [])

    def test_ignores_dict_get(self):
        got = self._classify('''
            def f(users, rows):
                for r in rows:
                    users.get(r.uid)
                return rows
        ''')
        self.assertEqual(got, [])

    def test_ignores_list_count(self):
        got = self._classify('''
            def f(vals):
                total = 0
                for v in vals:
                    total += vals.count(v)
                return total
        ''')
        self.assertEqual(got, [])

    def test_range_retry_loop_is_constant_not_real(self):
        got = self._classify('''
            def f(db):
                for attempt in range(3):
                    db.execute(text("update x set y = 1"))
                return True
        ''')
        self.assertEqual(got, [('retry/constant', 1)])


class LazyLoadTest(unittest.TestCase):
    """relationship reads on a loop variable are a second, separate shape.

    The db.query() detector cannot see them: there is no query call in the loop,
    SQLAlchemy emits one per row when the attribute is touched. Two endpoints
    were already green on the gate while still doing one query per row, so this
    class of finding has to be reported on its own.
    """

    @classmethod
    def setUpClass(cls):
        cls.mod = _load()

    def _lazy(self, src):
        import ast
        mod = self.mod
        tree = ast.parse(textwrap.dedent(src))
        out = []
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            by_var = mod._eager_by_var(func)
            func_eager = mod._eager_in_expr(func)
            for node in ast.walk(func):
                if isinstance(node, mod.LOOP_NODES):
                    eager = mod._eager_for_loop(node, by_var, func_eager)
                    out.extend((ln, text) for ln, text in mod._lazy_loads_in(node, eager))
        return out

    def test_flags_relationship_read_without_eager_loading(self):
        got = self._lazy('''
            def f(db):
                rows = db.query(CrisisWarning).all()
                for w in rows:
                    print(w.student.name)
        ''')
        self.assertEqual([text for _ln, text in got], ['w.student'])

    def test_joinedload_clears_the_finding(self):
        # The fix the backend applied; the gate must go quiet on it, or it would
        # report already-fixed code and lose its credibility.
        got = self._lazy('''
            def f(db):
                rows = db.query(CrisisWarning).options(joinedload(CrisisWarning.student)).all()
                for w in rows:
                    print(w.student.name)
        ''')
        self.assertEqual(got, [])

    def test_selectinload_also_clears_it(self):
        got = self._lazy('''
            def f(db):
                rows = db.query(CrisisWarning).options(selectinload(CrisisWarning.student)).all()
                for w in rows:
                    print(w.student.name)
        ''')
        self.assertEqual(got, [])

    # --- eager options must not leak across loops --------------------------

    def test_one_joinedload_does_not_silence_a_second_lazy_loop(self):
        # Regression: eager options were collected function-wide, so a joinedload
        # on one query hid a second loop over a different, still-lazy query.
        # Adding one joinedload then looked like it had fixed both loops.
        got = self._lazy('''
            def f(db):
                rows = db.query(W).options(joinedload(W.student)).all()
                for w in rows:
                    print(w.student.name)
                others = db.query(W).all()
                for o in others:
                    print(o.student.name)
        ''')
        self.assertEqual([text for _ln, text in got], ['o.student'])

    def test_joinedload_propagates_through_a_reassigned_query_variable(self):
        # The shape used by teacher.list_assigned_questions: the query is built,
        # filtered, then materialised. `questions` carries no joinedload of its
        # own but inherits it, and must not be reported.
        got = self._lazy('''
            def f(db):
                query = db.query(Question).options(joinedload(Question.user))
                query = query.filter(Question.status == "pending")
                questions = query.order_by(Question.created_at.desc()).all()
                for question in questions:
                    print(question.user.name)
        ''')
        self.assertEqual(got, [])

    def test_propagation_does_not_leak_to_an_unrelated_loop(self):
        # Same propagation, but a second query in the same function stays lazy.
        got = self._lazy('''
            def f(db):
                query = db.query(Question).options(joinedload(Question.user))
                questions = query.all()
                for q in questions:
                    print(q.user.name)
                plain = db.query(Question).all()
                for p in plain:
                    print(p.user.name)
        ''')
        self.assertEqual([text for _ln, text in got], ['p.user'])

    def test_non_relationship_attribute_is_ignored(self):
        # `w.risk_level` is a column: already loaded, no query.
        got = self._lazy('''
            def f(db):
                rows = db.query(CrisisWarning).all()
                for w in rows:
                    print(w.risk_level)
        ''')
        self.assertEqual(got, [])

    def test_two_reads_of_the_same_relationship_on_one_line_count_once(self):
        got = self._lazy('''
            def f(db):
                rows = db.query(CrisisWarning).all()
                for w in rows:
                    print(w.student.name or w.student.username)
        ''')
        self.assertEqual(len(got), 1)

    def test_while_loop_has_no_loop_variable_and_must_not_crash(self):
        got = self._lazy('''
            def f(db):
                i = 0
                while i < 3:
                    i += 1
        ''')
        self.assertEqual(got, [])


FIXTURES = REPO_ROOT / 'scripts' / 'tests' / 'fixtures' / 'n1_gate'
LAZY_BEFORE = FIXTURES / 'lazy_before.py'
EAGER_AFTER = FIXTURES / 'eager_after.py'


class LazyLoadRegressionTest(unittest.TestCase):
    """End-to-end on checked-in source snapshots, not on git history.

    These used to assert against historical revisions (`--git ec7b920`). That
    made the suite depend on full clone depth: CI checks out with fetch-depth: 1,
    the objects were absent, `git ls-tree` returned 128 and subprocess raised.
    The workflow was changed to fetch-depth: 0 to make it pass, which cost about
    100 MB per run for the sake of six tests.

    The fixtures are the same two functions cut out of those revisions, so the
    regression is still pinned to real code while needing no history at all.
    """

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=str(REPO_ROOT), capture_output=True, text=True, encoding='utf-8',
            errors='replace',
        )

    def test_fixtures_exist(self):
        # A silently missing fixture would make the two tests below vacuous.
        self.assertTrue(LAZY_BEFORE.is_file(), LAZY_BEFORE)
        self.assertTrue(EAGER_AFTER.is_file(), EAGER_AFTER)

    def test_reports_lazy_findings_before_the_fix(self):
        proc = self._run(str(LAZY_BEFORE))
        self.assertIn('lazy=4', proc.stdout, proc.stdout[:2000])
        for expected in ('w.student', 'w.processor', 'question.user'):
            self.assertIn(expected, proc.stdout)

    def test_reports_zero_lazy_findings_after_the_fix(self):
        proc = self._run(str(EAGER_AFTER))
        self.assertIn('real=0', proc.stdout)
        self.assertIn('lazy=0', proc.stdout)

    def test_fail_on_findings_trips_on_lazy_alone(self):
        # Lazy-load debt must not pass the blocking gate just because no
        # db.query() is left in a loop.
        proc = self._run('--fail-on-findings', str(LAZY_BEFORE))
        self.assertEqual(proc.returncode, 1)
        self.assertIn('FAIL:', proc.stderr)

    def test_single_file_path_is_accepted(self):
        # The fixtures are single files; scanning them used to yield nothing
        # because rglob only walks directories.
        proc = self._run(str(LAZY_BEFORE))
        self.assertIn('# scanned', proc.stdout)
        self.assertNotIn('lazy=0', proc.stdout)


class CommandLineTest(unittest.TestCase):
    # Fixture source with findings, so "must fail" is testable without depending
    # on the current worktree or on git history.
    REV_WITH_FINDINGS = str(LAZY_BEFORE)

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=str(REPO_ROOT), capture_output=True, text=True, encoding='utf-8',
            errors='replace',
        )

    def test_reports_without_failing_by_default(self):
        # Reporting mode must not break a build while the debt is being paid down.
        proc = self._run('--git', 'HEAD', 'backend/app')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('# scanned', proc.stdout)

    def test_fail_on_findings_is_off_until_asked(self):
        self.assertNotIn('unknown option', self._run('--git', 'HEAD', 'backend/app').stderr)

    def test_unknown_option_exits_2(self):
        proc = self._run('--nonsense')
        self.assertEqual(proc.returncode, 2)
        self.assertIn('unknown option', proc.stderr)

    # --- the gate must be able to fail -------------------------------------
    #
    # These three exist because the first version parsed options only while
    # args[0] started with "--". A flag placed after the path was silently
    # dropped, so the gate printed its findings and still exited 0: it looked
    # like a passing check while checking nothing. A gate that cannot fail is
    # worse than no gate, because it is trusted.

    def test_fail_on_findings_exits_1_when_flag_comes_first(self):
        proc = self._run('--fail-on-findings', self.REV_WITH_FINDINGS)
        self.assertEqual(proc.returncode, 1, proc.stdout[-2000:])
        self.assertIn('FAIL:', proc.stderr)

    def test_fail_on_findings_exits_1_when_flag_comes_last(self):
        # Regression: options after the positional path used to be ignored.
        proc = self._run(self.REV_WITH_FINDINGS, '--fail-on-findings')
        self.assertEqual(proc.returncode, 1, proc.stdout[-2000:])
        self.assertIn('FAIL:', proc.stderr)

    def test_unknown_option_after_path_exits_2(self):
        # Regression: `backend/app --bogus` used to exit 0 silently.
        proc = self._run(self.REV_WITH_FINDINGS, '--bogus')
        self.assertEqual(proc.returncode, 2)
        self.assertIn('unknown option', proc.stderr)

    def test_git_without_revision_exits_2(self):
        proc = self._run('--git')
        self.assertEqual(proc.returncode, 2)
        self.assertIn('--git needs a revision', proc.stderr)

    def test_two_paths_exit_2(self):
        proc = self._run('backend/app', 'backend/tests')
        self.assertEqual(proc.returncode, 2)
        self.assertIn('unexpected extra arguments', proc.stderr)

    def test_help_exits_0_and_documents_the_flags(self):
        # Not a bug fix, a usability one: `--help` used to exit 2 and report
        # "unknown option --help", which reads like the script is broken.
        proc = self._run('--help')
        self.assertEqual(proc.returncode, 0)
        self.assertIn('--fail-on-findings', proc.stdout)
        self.assertIn('--git', proc.stdout)
        self.assertIn('usage:', proc.stdout)

    def test_short_help_flag_also_works(self):
        self.assertEqual(self._run('-h').returncode, 0)

    # --- a missing path must not read as a clean scan -----------------------
    #
    # `Path('backend/nope').rglob('*.py')` yields nothing, so the first version
    # printed `real=0 lazy=0` and exited 0 for a path that does not exist. In CI
    # that turns a typo in the step's path into a green gate that scanned no
    # code. Same for `git ls-tree`, which prints nothing and exits 0.

    def test_missing_path_exits_2_instead_of_reporting_clean(self):
        proc = self._run('backend/does-not-exist')
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn('no such path', proc.stderr)
        self.assertNotIn('real=0', proc.stdout)

    def test_missing_path_in_a_revision_exits_2(self):
        proc = self._run('--git', 'HEAD', 'backend/does-not-exist')
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn('no such path in HEAD', proc.stderr)
        self.assertNotIn('real=0', proc.stdout)


if __name__ == '__main__':
    unittest.main()
