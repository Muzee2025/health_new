"""Exercise the transport CLI's read-only plan and port restrictions."""
import json  # noqa: I001
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "verify-nginx-transport.py"


class TransportCliTests(unittest.TestCase):
    def invoke(self, *args):
        with tempfile.TemporaryDirectory() as work:
            return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=work,
                                  capture_output=True, text=True, timeout=10)

    def test_plan_needs_no_docker_or_certificate(self):
        result = self.invoke("--openssl", "/nonexistent/openssl")
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["mode"], "plan")
        self.assertFalse(plan["pull_images"])
        self.assertEqual(plan["http_port"], 4189)
        self.assertIn("SSE incremental delivery", plan["checks"])

    def test_reserved_and_shared_ports_fail_before_resources_are_created(self):
        for args in (("--http-port", "8000"), ("--tls-port", "5173"),
                     ("--http-port", "4190"), ("--http-port", "80")):
            with self.subTest(args=args):
                result = self.invoke(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn("distinct non-reserved loopback ports", result.stderr)

    def test_run_requires_a_local_certificate_tool_before_docker(self):
        result = self.invoke("--run", "--openssl", "/nonexistent/openssl")
        self.assertEqual(result.returncode, 2)
        self.assertIn("local OpenSSL executable is required", result.stderr)


if __name__ == "__main__":
    unittest.main()
