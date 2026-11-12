"""Unit tests for the safety boundary and stage reporting of verify-fullstack."""
import importlib.util  # noqa: I001
from contextlib import nullcontext
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "verify-fullstack.py"
SPEC = importlib.util.spec_from_file_location("verify_fullstack", SCRIPT)
vf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vf)


class FullstackVerificationTests(unittest.TestCase):
    def test_windows_plugin_discovery_paths_are_kept_without_compose_settings(self):
        source = {"ProgramFiles": "plugins", "APPDATA": "app-settings", "COMPOSE_FILE": "foreign.yml",
                  "COMPOSE_PROJECT_NAME": "foreign", "RUNTIME_ENV_FILE": "foreign.env", "HTTP_PORT": "8000"}
        self.assertEqual(vf.docker_environment(source), {"ProgramFiles": "plugins", "APPDATA": "app-settings"})

    def test_reserved_ports_and_output_reuse_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "deploy/fullstack").mkdir(parents=True)
            (root / "deploy/fullstack/docker-compose.yml").write_text("services: {}\n")
            with patch.object(vf, "port_is_free", return_value=True):
                runner = vf.Runner(root, 18080, 5, False)
                with self.assertRaises(vf.SafetyError):
                    runner.preflight()
                runner = vf.Runner(root, 4188, 5, True)
                runner.output.parent.mkdir()
                runner.output.mkdir()
                with self.assertRaises(vf.SafetyError):
                    runner.preflight()

    def test_summary_writer_does_not_touch_reused_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = vf.Runner(root, 4188, 5, False)
            runner.output.mkdir(parents=True)
            marker = runner.output / "keep.txt"
            marker.write_text("existing")
            runner.write_summary()
            self.assertEqual(marker.read_text(), "existing")
            self.assertFalse((runner.output / "summary.json").exists())
    def test_only_unique_project_prefix_and_new_tmp_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "deploy/fullstack").mkdir(parents=True)
            compose = root / "deploy/fullstack/docker-compose.yml"
            compose.write_text("services: {}\n")
            with patch.object(vf, "port_is_free", return_value=True):
                runner = vf.Runner(root, 4188, 5, False)
                calls = []
                runner.docker = lambda args, name, **kw: calls.append((args, name)) or ("[]" if args[:2] == ["compose", "ls"] else "")
                runner.preflight()
                self.assertRegex(runner.project, r"^healthnew-qa-[0-9a-f]{12}$")
                self.assertEqual(runner.output.parent, root / "tmp")
                self.assertTrue(all(runner.project in " ".join(c[0]) or c[0][0] == "compose" for c in calls))

    def test_tmp_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / "tmp").mkdir()
            (root / "deploy/fullstack").mkdir(parents=True)
            (root / "deploy/fullstack/docker-compose.yml").write_text("services: {}\n")
            path_type = type(root / "tmp")
            for method_name in ("is_symlink", "is_junction"):
                if not hasattr(path_type, method_name):
                    continue
                original = getattr(path_type, method_name)
                with patch.object(path_type, method_name, lambda path, orig=original, m=method_name: path == root / "tmp" or orig(path)):
                    with patch.object(vf, "port_is_free", return_value=True):
                        runner = vf.Runner(root, 4188, 5, False)
                        with self.assertRaisesRegex(vf.SafetyError, "symlink or junction"):
                            runner.preflight()

    def test_run_artifacts_are_qa_only_and_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "deploy/fullstack").mkdir(parents=True)
            (root / "deploy/fullstack/docker-compose.yml").write_text("services: {}\n")
            runner = vf.Runner(root, 4188, 5, True)
            with patch.object(vf, "port_is_free", return_value=True):
                runner.preflight = lambda: {}
                runner.create_private_dir()
            raw = runner.env_file.read_text()
            self.assertIn("JWT_SECRET_KEY=", raw)
            self.assertNotIn("DATABASE_URL", raw)
            self.assertNotIn("OPENAI_API_KEY", raw)
            self.assertEqual(runner.output.parent, root / "tmp")
            if vf.os.name != "nt":
                self.assertEqual(runner.output.stat().st_mode & 0o777, 0o700)

    def test_docker_targets_are_scoped_and_no_config_env_or_inspect_dump(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"-p", self.project', source)
        self.assertIn('"config", "--quiet"', source)
        self.assertIn('"down", "--remove-orphans"', source)
        self.assertNotIn('"Config.Env"', source)
        self.assertNotIn('"inspect", cid]', source)
        self.assertNotIn("read_text(encoding=\"utf-8\")", source[source.index("def preflight"):source.index("def create_private_dir")])

    def test_compose_host_sentinels_are_not_inherited_by_docker_children(self):
        sentinels = {"PATH": "safe-path", "RUNTIME_ENV_FILE": "host-secret-path", "COMPOSE_FILE": "foreign.yml",
                     "COMPOSE_PROJECT_NAME": "foreign-project", "PUBLIC_ORIGIN": "https://foreign.invalid",
                     "DATABASE_URL": "sqlite:///private.db", "JWT_SECRET_KEY": "host-secret"}
        filtered = vf.docker_environment(sentinels)
        self.assertEqual(filtered, {"PATH": "safe-path"})
        with tempfile.TemporaryDirectory() as tmp:
            runner = vf.Runner(Path(tmp), 4188, 5, True)
            runner.log_dir = Path(tmp) / "logs"
            runner.log_dir.mkdir()
            captured = {}
            def fake_run(*args, **kwargs):
                captured.update(kwargs["env"])
                return SimpleNamespace(returncode=0, stdout="ok", stderr="")
            with patch.dict(vf.os.environ, sentinels, clear=True), patch.object(vf.subprocess, "run", side_effect=fake_run):
                runner.docker(["version"], "fake")
            self.assertNotIn("COMPOSE_FILE", captured)
            self.assertNotIn("COMPOSE_PROJECT_NAME", captured)
            self.assertNotIn("RUNTIME_ENV_FILE", captured)
            self.assertNotIn("PUBLIC_ORIGIN", captured)
            self.assertNotIn("DATABASE_URL", captured)
            self.assertNotIn("JWT_SECRET_KEY", captured)
            self.assertTrue((runner.log_dir / "fake.log").is_file())

    def test_compose_stdin_is_forwarded_and_project_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = vf.Runner(Path(tmp), 4188, 5, True)
            calls = []
            runner.env_file = Path(tmp) / "qa.env"
            runner.docker = lambda args, name, allow_fail=False, stdin=None: calls.append((args, name, allow_fail, stdin)) or "ok"
            runner.compose_cmd(["exec", "-T", "backend", "python", "-"], "backup-restore", stdin="print('qa')")
            args, name, allow_fail, stdin = calls[0]
            self.assertEqual(args[0:2], ["compose", "--env-file"])
            self.assertIn(runner.project, args)
            self.assertEqual(args[-5:], ["exec", "-T", "backend", "python", "-"])
            self.assertEqual(stdin, "print('qa')")
            self.assertEqual(name, "backup-restore")

    def test_http_smoke_uses_required_health_auth_role_and_question_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = vf.Runner(Path(tmp), 4188, 5, True)
            calls = []
            def request(method, path, payload=None, token=None):
                calls.append((method, path, payload, token))
                if path == "/api/health/ready": return 200, "application/json", b'{"schema_ready":true}'  # noqa: E701
                if path == "/": return 200, "text/html", b'<html><script type="module" src="/assets/main.js"></script></html>'  # noqa: E701
                if path == "/assets/main.js": return 200, "application/javascript", b"export{}"  # noqa: E701
                if path == "/api/register" and payload.get("role") == "teacher": return 422, "application/json", b"{}"  # noqa: E701
                if path == "/api/register": return 200, "application/json", b'{"access_token":"register-token"}'  # noqa: E701
                if path == "/api/login": return 200, "application/json", b'{"access_token":"login-token"}'  # noqa: E701
                if path == "/api/me": return 200, "application/json", b'{"role":"student"}'  # noqa: E701
                if path == "/api/teacher/students": return 403, "application/json", b"{}"  # noqa: E701
                if path == "/api/student/questions" and payload.get("question_text", "").strip():
                    return 200, "application/json", b'{"response_state":"unassigned"}'
                if path == "/api/student/questions/ask": return 422, "application/json", b"{}"  # noqa: E701
                raise AssertionError((method, path))
            runner.request = request
            result = runner.http_smoke()
            self.assertTrue(result["login"] and result["health_ready"] and result["unassigned_question_200"])
            self.assertIn(("POST", "/api/login"), [(m, p) for m, p, _, _ in calls])
            question = next(c for c in calls if c[1] == "/api/student/questions")
            self.assertEqual(question[2]["question_text"], runner.summary["synthetic"]["message_marker"])
            self.assertEqual(question[3], "login-token")
            registration = next(c for c in calls if c[1] == "/api/register" and c[2].get("role") == "student")
            self.assertRegex(registration[2]["password"], r"^Qa9-.+")

    def test_http_request_disables_host_proxy(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = vf.Runner(Path(tmp), 4188, 5, True)
            response = SimpleNamespace(status=200, headers=SimpleNamespace(get_content_type=lambda: "application/json"), read=lambda n: b"{}")
            opener = SimpleNamespace(open=lambda req, timeout: nullcontext(response))
            with patch.object(vf.urllib.request, "build_opener", return_value=opener) as build_opener:
                self.assertEqual(runner.request("GET", "/api/health/ready")[0], 200)
            proxies = [handler for handler in build_opener.call_args.args if isinstance(handler, vf.urllib.request.ProxyHandler)]
            self.assertEqual(len(proxies), 1)
            self.assertEqual(proxies[0].proxies, {})

    def test_inspect_requires_exactly_backend_and_frontend_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = vf.Runner(Path(tmp), 4188, 5, True)
            runner.compose_cmd = lambda *args, **kw: "one two"
            rows = iter(["/qa-backend-1|appuser|true|true|healthy", "/qa-frontend-1|101|true|true|healthy"])
            runner.docker = lambda *args, **kw: next(rows)
            self.assertEqual(len(runner.inspect()["containers"]), 2)
            runner.compose_cmd = lambda *args, **kw: "one"
            runner.docker = lambda *args, **kw: "/qa-backend-1|appuser|true|true|healthy"
            with self.assertRaises(RuntimeError):
                runner.inspect()

    def test_stage_failure_leaves_later_stages_not_run_and_cleanup_stays_project_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = vf.Runner(Path(tmp), 4188, 5, True)
            calls = []
            with self.assertRaises(RuntimeError):
                runner.stage("build", lambda: (_ for _ in ()).throw(RuntimeError("synthetic failure")))
            self.assertEqual(runner.summary["stages"]["build"]["status"], "failed")
            self.assertEqual(runner.summary["stages"]["http_smoke"]["status"], "not_run")
            runner.cleanup = lambda: calls.append(runner.project) or {"scope": runner.project}
            runner.cleanup()
            self.assertEqual(calls, [runner.project])
            self.assertTrue(runner.project.startswith(vf.PROJECT_PREFIX))

    def test_execute_failure_attempts_only_project_scoped_down_and_preserves_volumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = vf.Runner(Path(tmp), 4188, 5, True)
            runner.preflight = lambda: {}
            def setup():
                runner.output.mkdir(parents=True)
                runner.output_owned = True
                runner.log_dir = runner.output / "logs"
                runner.log_dir.mkdir()
                runner.env_file.write_text("QA only")
            runner.create_private_dir = setup
            def failing_config():
                runner.compose_invoked = True
                raise RuntimeError("config failure")
            runner.config = failing_config
            runner.write_summary = lambda: None
            calls = []
            def fake_docker(args, name, allow_fail=False, stdin=None):
                calls.append((args, name))
                runner.last_returncode = 0
                return "healthnew-qa-test_database\n" if args[:2] == ["volume", "ls"] else ""
            runner.docker = fake_docker
            self.assertEqual(runner.execute(), 1)
            self.assertEqual(runner.summary["stages"]["config"]["status"], "failed")
            self.assertEqual(runner.summary["stages"]["build"]["status"], "not_run")
            down = next(args for args, _ in calls if "down" in args)
            self.assertIn(runner.project, down)
            self.assertIn("--remove-orphans", down)
            self.assertNotIn("-v", down)
            self.assertEqual(runner.summary["cleanup"]["volumes_before"], ["healthnew-qa-test_database"])
            self.assertEqual(runner.summary["cleanup"]["volumes_after"], ["healthnew-qa-test_database"])

    def test_setup_failure_is_recorded_without_compose_cleanup_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = vf.Runner(Path(tmp), 4188, 5, True)
            runner.preflight = lambda: {}
            runner.create_private_dir = lambda: (_ for _ in ()).throw(RuntimeError("ACL setup failed"))
            runner.write_summary = lambda: None
            self.assertEqual(runner.execute(), 1)
            self.assertEqual(runner.summary["stages"]["setup"]["status"], "failed")
            self.assertEqual(runner.summary["stages"]["config"]["status"], "not_run")
            self.assertEqual(runner.summary["stages"]["cleanup"]["status"], "not_run")
            self.assertEqual(runner.summary["cleanup"]["status"], "not_needed")

    def test_backup_restore_comparison_summary(self):
        item = {"message_count": 1, "tables": 27, "triggers": 6, "quick_check": "ok", "foreign_key_violations": 0}
        data = {"restored_old_marker": item, "restored_second_marker": {**item, "message_count": 0},
                "source_after_second": item, "table_count": 27, "trigger_count": 6, "quick_check": "ok", "foreign_key_violations": 0}
        result = vf.backup_restore_summary(data)
        self.assertTrue(result["backup_kept_original_message"])
        self.assertTrue(result["backup_excludes_second_message"])
        self.assertTrue(result["runtime_kept_second_message"])
        data["restored_second_marker"] = item
        with self.assertRaises(RuntimeError):
            vf.backup_restore_summary(data)


if __name__ == "__main__":
    unittest.main()
