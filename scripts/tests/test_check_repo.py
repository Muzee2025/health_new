"""Lock the classification rules check-repo.py uses to decide what fails the job.

check-repo.py is a CI gate but had no test of its own, so a loosened pattern
would silently stop failing the job rather than fail this suite. The module is
imported by path (its filename has a hyphen) and only the pure helpers are
exercised; inspect() shells out to git and is left to the real run in CI.
"""
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "check-repo.py"

spec = importlib.util.spec_from_file_location("check_repo_under_test", SCRIPT)
check_repo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_repo)


class SecretEnvTests(unittest.TestCase):
    """A false negative here tracks a real .env into the repository."""

    def test_plain_env_is_secret(self):
        self.assertTrue(check_repo.secret_env(".env"))

    def test_env_variants_are_secret(self):
        for path in (".env.local", ".env.production", "backend/.env"):
            with self.subTest(path=path):
                self.assertTrue(check_repo.secret_env(path))

    def test_documented_exceptions_are_not_secret(self):
        # Both are tracked on purpose: one is the template, the other is the
        # committed development defaults the project ships.
        self.assertFalse(check_repo.secret_env(".env.example"))
        self.assertFalse(check_repo.secret_env(".env.development"))

    def test_similar_names_are_not_mistaken_for_env_files(self):
        for path in ("env", "backend/env.py", ".envrc"):
            with self.subTest(path=path):
                self.assertFalse(check_repo.secret_env(path))


class RuntimePathTests(unittest.TestCase):
    """These paths must never be tracked; the gate depends on matching them."""

    def test_runtime_directories_match_at_any_depth(self):
        for path in (
            "tmp/report.json",
            "backend/tmp/x.db",
            "node_modules/pkg/index.js",
            "dist/assets/app.js",
            "coverage/index.html",
            "logs/app.log",
            ".venv/pyvenv.cfg",
            "backend/uploads/avatar.png",
            "backend/temp/session.db",
            "backend/chroma/chroma.sqlite3",
            "backend/__pycache__/x.pyc",
        ):
            with self.subTest(path=path):
                self.assertTrue(check_repo.RUNTIME.search(path))

    def test_source_paths_do_not_match(self):
        for path in (
            "src/assets/logo.png",
            "backend/app/main.py",
            "scripts/check-repo.py",
            "docs/team/进度看板.md",
            "templates/index.html",
        ):
            with self.subTest(path=path):
                self.assertIsNone(check_repo.RUNTIME.search(path))


class AllowListTests(unittest.TestCase):
    """Allow-lists are exact paths, so a new file of the same kind still fails."""

    def test_pinned_artifacts_are_exact_paths(self):
        for path in check_repo.PINNED_ARTIFACTS:
            with self.subTest(path=path):
                self.assertTrue(check_repo.RUNTIME.search(path),
                                "pinned entries should be runtime-looking files")
                self.assertNotIn("*", path)

    def test_acknowledged_oversized_are_exact_paths(self):
        self.assertTrue(check_repo.ACKNOWLEDGED_OVERSIZED)
        for path in check_repo.ACKNOWLEDGED_OVERSIZED:
            with self.subTest(path=path):
                self.assertNotIn("*", path)

    def test_allow_lists_do_not_overlap(self):
        self.assertFalse(check_repo.PINNED_ARTIFACTS & check_repo.ACKNOWLEDGED_OVERSIZED)

    def test_legacy_dirs_are_not_also_source_dirs(self):
        # LEGACY_DIRS is an elif branch, so a directory in both sets would
        # silently classify its files as legacy and skip the unexpected-path check.
        self.assertFalse(check_repo.LEGACY_DIRS & check_repo.SOURCE_DIRS)


class RootFileTests(unittest.TestCase):
    def test_known_root_files_are_allowed(self):
        for name in ("package.json", "vite.config.js", "AGENTS.md", "ruff.toml"):
            with self.subTest(name=name):
                self.assertIn(name, check_repo.ROOT_FILES)

    def test_root_files_are_bare_names(self):
        for name in check_repo.ROOT_FILES:
            with self.subTest(name=name):
                self.assertNotIn("/", name)

    def test_source_dirs_cover_the_top_level_tree(self):
        for name in ("backend", "src", "scripts", "docs", ".github"):
            with self.subTest(name=name):
                self.assertIn(name, check_repo.SOURCE_DIRS)


if __name__ == "__main__":
    unittest.main()
