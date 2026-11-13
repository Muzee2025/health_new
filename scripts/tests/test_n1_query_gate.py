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


class CommandLineTest(unittest.TestCase):
    # A revision known to contain findings, so "must fail" is testable without
    # depending on the current worktree being dirty or clean.
    REV_WITH_FINDINGS = '4a39036'

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
        proc = self._run('--fail-on-findings', '--git', self.REV_WITH_FINDINGS, 'backend/app')
        self.assertEqual(proc.returncode, 1, proc.stdout[-2000:])
        self.assertIn('FAIL:', proc.stderr)

    def test_fail_on_findings_exits_1_when_flag_comes_last(self):
        # Regression: options after the positional path used to be ignored.
        proc = self._run('--git', self.REV_WITH_FINDINGS, 'backend/app', '--fail-on-findings')
        self.assertEqual(proc.returncode, 1, proc.stdout[-2000:])
        self.assertIn('FAIL:', proc.stderr)

    def test_unknown_option_after_path_exits_2(self):
        # Regression: `backend/app --bogus` used to exit 0 silently.
        proc = self._run('--git', self.REV_WITH_FINDINGS, 'backend/app', '--bogus')
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


if __name__ == '__main__':
    unittest.main()
