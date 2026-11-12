"""Run an isolated HTTP/Docker acceptance pass for the full-stack image.

Default mode performs a read-only preflight and prints the planned stages. Use
--run only after reviewing the plan. All run artifacts live in a new private
directory below the repository's ignored tmp/ directory.
"""
from __future__ import annotations  # noqa: I001

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys  # noqa: F401
import urllib.error
import urllib.request


STAGES = ["preflight", "setup", "config", "build", "init_empty", "up_wait", "http_smoke", "backup_restore", "inspect", "cleanup"]
RESERVED_PORTS = {8000, 5173, 18080, 18081}
PROJECT_PREFIX = "healthnew-qa-"
HEALTH_PATH = "database/health.db"


class SafetyError(RuntimeError):
    pass


class Runner:
    def __init__(self, root: Path, port: int, timeout: int, run: bool):
        self.root = root.resolve(strict=True)
        self.port, self.timeout, self.run = port, timeout, run
        self.project = PROJECT_PREFIX + secrets.token_hex(6)
        self.output = self.root / "tmp" / self.project
        self.compose = self.root / "deploy" / "fullstack" / "docker-compose.yml"
        self.env_file = self.output / "qa.env"
        self.summary = {"task": "W3-RUNNER", "project": self.project, "mode": "run" if run else "plan", "port": port,
                       "stages": {s: {"status": "not_run"} for s in STAGES}, "cleanup": {"status": "not_run"}}
        self.log_dir: Path | None = None
        self.output_owned = False
        self.started = False
        self.compose_invoked = False
        self.last_returncode: int | None = None

    def stage(self, name: str, fn):
        self.summary["stages"][name] = {"status": "running"}
        try:
            detail = fn()
            self.summary["stages"][name] = {"status": "passed", **(detail or {})}
        except Exception as exc:
            self.summary["stages"][name] = {"status": "failed", "error": safe_error(exc)}
            raise

    def preflight(self):
        if self.root.name == "" or self.root not in self.output.parents:
            raise SafetyError("invalid repository root")
        expected_tmp = self.root / "tmp"
        if expected_tmp.exists() and (expected_tmp.is_symlink() or (hasattr(expected_tmp, "is_junction") and expected_tmp.is_junction())):
            raise SafetyError("repository tmp path must not be a symlink or junction")
        resolved_tmp = expected_tmp.resolve(strict=False)
        resolved_output = self.output.resolve(strict=False)
        try:
            if resolved_tmp != expected_tmp or resolved_output.parent != resolved_tmp or resolved_output.name != self.project:
                raise SafetyError("QA output path resolves outside the repository tmp directory")
            resolved_output.relative_to(self.root)
        except ValueError as exc:
            raise SafetyError("QA output path resolves outside the repository") from exc
        if self.port in RESERVED_PORTS or not 1 <= self.port <= 65535:
            raise SafetyError("HTTP port is reserved or outside the valid range")
        if not port_is_free(self.port):
            raise SafetyError("selected HTTP port is already occupied")
        if not self.compose.is_file() or self.compose.is_symlink():
            raise SafetyError("expected Compose file is missing or is a symlink")
        if self.output.exists() or self.output.is_symlink():
            raise SafetyError("refusing to reuse an existing QA output directory")
        self.docker(["compose", "ls", "--format", "json"], "compose-project-list")
        # Query only project labels and IDs, never inspect environment/configuration.
        ids = self.docker(["ps", "-aq", "--filter", f"label=com.docker.compose.project={self.project}"], "project-container-ids", allow_fail=False)
        volumes = self.docker(["volume", "ls", "-q", "--filter", f"label=com.docker.compose.project={self.project}"], "project-volume-check")
        networks = self.docker(["network", "ls", "-q", "--filter", f"label=com.docker.compose.project={self.project}"], "project-network-check")
        if ids.strip() or volumes.strip() or networks.strip():
            raise SafetyError("refusing to reuse an existing Compose project")
        return {"project_prefix": PROJECT_PREFIX, "output_is_new": True, "port_free": True}

    def create_private_dir(self):
        tmp_dir = self.root / "tmp"
        if tmp_dir.exists() and (tmp_dir.is_symlink() or (hasattr(tmp_dir, "is_junction") and tmp_dir.is_junction())):
            raise SafetyError("repository tmp path must not be a symlink or junction")
        self.output.parent.mkdir(parents=True, exist_ok=True)
        if tmp_dir.resolve(strict=True) != tmp_dir:
            raise SafetyError("repository tmp path resolves outside the repository")
        self.output.mkdir(mode=0o700)
        self.output_owned = True
        if os.name != "nt":
            os.chmod(self.output, 0o700)
        else:
            user = os.environ.get("USERNAME")
            if not user or shutil.which("icacls") is None:
                raise SafetyError("cannot establish private Windows ACL")
            p = subprocess.run(["icacls", str(self.output), "/inheritance:r", "/grant:r", f"{user}:(OI)(CI)F"],
                               capture_output=True, text=True, timeout=self.timeout, shell=False)
            if p.returncode:
                raise SafetyError("could not establish private Windows ACL")
        self.log_dir = self.output / "logs"
        self.log_dir.mkdir(mode=0o700)
        config = {
            "JWT_SECRET_KEY": secrets.token_urlsafe(48),
            "HTTP_PORT": str(self.port),
            "PUBLIC_ORIGIN": f"http://127.0.0.1:{self.port}",
            "RUNTIME_ENV_FILE": self.env_file.resolve().as_posix(),
        }
        # Compose requires an env_file. It is the same fresh QA-only file; it
        # contains no provider keys, database URL, or values from a user config.
        self.env_file.write_text("\n".join(f"{k}={v}" for k, v in config.items()) + "\n", encoding="utf-8")
        try:
            os.chmod(self.env_file, 0o600)
        except OSError:
            pass
        self.started = True

    def docker(self, args: list[str], log_name: str, allow_fail: bool = False, stdin: str | None = None) -> str:
        cmd = ["docker", *args]
        env = docker_environment(os.environ)
        try:
            proc = subprocess.run(cmd, cwd=self.root, input=stdin, capture_output=True, text=True,
                                  timeout=self.timeout, shell=False, env=env)
        except subprocess.TimeoutExpired as exc:
            if self.log_dir is not None:
                (self.log_dir / f"{log_name}.log").write_text("command timed out\n", encoding="utf-8")
            raise RuntimeError(f"docker command timed out: {log_name}") from exc
        # Docker output is kept private; summaries expose only allowlisted metadata.
        self.last_returncode = proc.returncode
        if self.log_dir is not None:
            (self.log_dir / f"{log_name}.log").write_text((proc.stdout or "") + (proc.stderr or ""), encoding="utf-8")
        if proc.returncode and not allow_fail:
            raise RuntimeError(f"docker command failed: {log_name} (exit {proc.returncode})")
        return proc.stdout or ""

    def compose_cmd(self, action: list[str], name: str, allow_fail: bool = False, stdin: str | None = None) -> str:
        self.compose_invoked = True
        return self.docker(["compose", "--env-file", str(self.env_file), "-f", str(self.compose), "-p", self.project, *action], name, allow_fail, stdin=stdin)

    def config(self):
        self.compose_cmd(["config", "--quiet"], "compose-config")
        return {"config_quiet": True}

    def build(self):
        self.compose_cmd(["build", "--pull=false"], "compose-build")
        return {"built": True}

    def init_empty(self):
        # `run --rm` creates only this project's service container and mounted
        # volume. It reserves health.db inside the new project database volume.
        self.compose_cmd(["run", "--rm", "--no-deps", "--entrypoint", "python", "backend",
                          "scripts/init-empty-database.py", "--database", "/var/lib/health-new/database/health.db"], "init-empty")
        return {"database_path": HEALTH_PATH}

    def up_wait(self):
        self.compose_cmd(["up", "-d", "--wait", "--wait-timeout", str(self.timeout)], "compose-up")
        return {"healthy": True}

    def request(self, method: str, path: str, payload: dict | None = None, token: str | None = None):
        headers = {"Accept": "application/json, text/html, */*"}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode()
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=body, headers=headers, method=method)
        class LoopbackRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(inner_self, original, response, code, msg, headers, newurl):
                if not newurl.startswith(f"http://127.0.0.1:{self.port}/"):
                    raise RuntimeError("HTTP redirect left the loopback QA origin")
                return super().redirect_request(original, response, code, msg, headers, newurl)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), LoopbackRedirect())
        try:
            with opener.open(req, timeout=self.timeout) as resp:
                data = resp.read(4_000_000)
                return resp.status, resp.headers.get_content_type(), data
        except urllib.error.HTTPError as exc:
            return exc.code, exc.headers.get_content_type(), exc.read(100_000)

    def http_smoke(self):
        health_code, _, health_body = self.request("GET", "/api/health/ready")
        if health_code != 200 or json.loads(health_body).get("schema_ready") is not True:
            raise RuntimeError("database readiness check failed")
        code, ctype, page = self.request("GET", "/")
        if code != 200 or "text/html" not in ctype or b"<html" not in page.lower():
            raise RuntimeError("SPA root check failed")
        refs = re.findall(rb'<script[^>]+src=["\']([^"\']+\.js)["\']', page, re.I)
        if not refs:
            # Vite module script may carry query params; retain only local paths.
            refs = re.findall(rb'<script[^>]+src=["\']([^"\']+)["\']', page, re.I)
        if not refs:
            raise RuntimeError("SPA JavaScript reference missing")
        for ref in refs:
            path = ref.decode("utf-8", "strict")
            if path.startswith(("http:", "https:", "//")):
                raise RuntimeError("SPA references a remote script")
            js_code, js_type, js_data = self.request("GET", path)
            if js_code != 200 or "javascript" not in js_type and not path.endswith(".js") or not js_data:
                raise RuntimeError("SPA JavaScript asset check failed")
        reg = {"username": "qa_" + secrets.token_hex(6), "password": "Qa9-" + secrets.token_urlsafe(18), "role": "student", "name": "QA"}
        code, _, body = self.request("POST", "/api/register", reg)
        if code != 200:
            raise RuntimeError("synthetic registration failed")
        token = json.loads(body).get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("registration token missing")
        code, _, login_body = self.request("POST", "/api/login", {"username": reg["username"], "password": reg["password"]})
        if code != 200:
            raise RuntimeError("synthetic student login failed")
        token = json.loads(login_body).get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("login token missing")
        code, _, body = self.request("GET", "/api/me", token=token)
        if code != 200 or json.loads(body).get("role") != "student":
            raise RuntimeError("student identity check failed")
        code, _, _ = self.request("POST", "/api/register", {**reg, "username": "qa_teacher_" + secrets.token_hex(4), "role": "teacher"})
        if code != 422:
            raise RuntimeError("public teacher registration was not denied")
        code, _, _ = self.request("GET", "/api/teacher/students", token=token)
        if code != 403:
            raise RuntimeError("student access to teacher route was not denied")
        msg = "qa-question-" + secrets.token_hex(8)
        code, _, body = self.request("POST", "/api/student/questions", {"question_text": msg}, token)
        if code != 200:
            raise RuntimeError("synthetic unassigned student question failed")
        if json.loads(body).get("response_state") != "unassigned":
            raise RuntimeError("synthetic question did not report unassigned state")
        code, _, _ = self.request("POST", "/api/student/questions/ask", {"question_text": "   "}, token)
        if code != 422:
            raise RuntimeError("blank question was not rejected")
        self.summary["synthetic"] = {"username": reg["username"], "message_marker": msg}
        return {"health_ready": True, "spa": True, "js_assets": len(refs), "registration": True, "login": True,
                "me_role": "student", "teacher_registration_422": True, "teacher_route_403": True,
                "unassigned_question_200": True, "blank_question_422": True}

    def exec_python(self, script: str, name: str):
        return self.compose_cmd(["exec", "-T", "backend", "python", "-"], name, stdin=script)

    def backup_restore(self):
        values = self.summary["synthetic"]
        username, marker = values["username"], values["message_marker"]
        script = f'''import json, os, sqlite3, subprocess
src="/var/lib/health-new/database/health.db"
backup="/var/lib/health-new/database/{self.project}-backup.db"
restored="/var/lib/health-new/database/{self.project}-restored.db"
marker={marker!r}; username={username!r}
def count(path, text):
 c=sqlite3.connect("file:"+path+"?mode=ro",uri=True)
 try:
  quick=c.execute("PRAGMA quick_check").fetchone()[0]
  tables=c.execute("select count(*) from sqlite_master where type='table' and name not like 'sqlite_%'").fetchone()[0]
  triggers=c.execute("select count(*) from sqlite_master where type='trigger'").fetchone()[0]
  fk=sum(1 for _ in c.execute("pragma foreign_key_check"))
  rows=c.execute("select count(*) from questions q join users u on u.id=q.user_id where u.username=? and q.question_text=?",(username,text)).fetchone()[0]
  return {{"quick_check":quick,"tables":tables,"triggers":triggers,"foreign_key_violations":fk,"message_count":rows}}
 finally: c.close()
before=count(src,marker)
if before["message_count"] != 1: raise SystemExit("synthetic baseline count mismatch")
subprocess.run(["python","scripts/backup-restore-database.py","backup","--source",src,"--destination",backup],check=True,capture_output=True,text=True)
c=sqlite3.connect(src); c.execute("insert into questions (user_id, question_text, status, created_at) select id, ?, 'pending', CURRENT_TIMESTAMP from users where username=?",("qa-second-"+{self.project!r},username)); c.commit(); c.close()
source=count(src,"qa-second-"+{self.project!r})
subprocess.run(["python","scripts/backup-restore-database.py","restore","--source",backup,"--destination",restored],check=True,capture_output=True,text=True)
old=count(restored,marker); absent=count(restored,"qa-second-"+{self.project!r})
summary={{"source_after_second":source,"restored_old_marker":old,"restored_second_marker":absent,"table_count":old["tables"],"trigger_count":old["triggers"],"quick_check":old["quick_check"],"foreign_key_violations":old["foreign_key_violations"]}}
if source["message_count"] != 1 or old["message_count"] != 1 or absent["message_count"] != 0: raise SystemExit("backup restore message comparison failed")
if old["tables"] != 27 or old["triggers"] != 6 or old["quick_check"].lower() != "ok" or old["foreign_key_violations"] != 0: raise SystemExit("database integrity expectations failed")
print(json.dumps(summary))
'''
        output = self.exec_python(script, "backup-restore").strip().splitlines()
        try:
            data = json.loads(output[-1])
        except Exception as exc:
            raise RuntimeError("backup/restore verification returned no safe summary") from exc
        return backup_restore_summary(data)

    def inspect(self):
        # Return safe selected fields only. Never request Config.Env or full inspect.
        ids = self.compose_cmd(["ps", "-q"], "service-container-ids").split()
        selected = []
        for index, cid in enumerate(ids):
            raw = self.docker(["inspect", "--format", "{{.Name}}|{{.Config.User}}|{{.HostConfig.ReadonlyRootfs}}|{{.State.Running}}|{{.State.Health.Status}}", cid], f"inspect-safe-{index}")
            parts = raw.strip().lstrip("/").split("|")
            if len(parts) != 5:
                raise RuntimeError("safe container inspection format invalid")
            name, user, readonly, running, health = parts
            selected.append({"name": name, "non_root": user not in ("", "0", "root", "0:0"), "readonly_root": readonly.lower() == "true",
                             "running": running.lower() == "true", "health": health})
        service_names = {x["name"].rsplit("-", 2)[-2] for x in selected}
        if len(selected) != 2 or service_names != {"backend", "frontend"} or not all(
            x["non_root"] and x["readonly_root"] and x["running"] and x["health"] == "healthy" for x in selected
        ):
            raise RuntimeError("container hardening/runtime inspection failed")
        return {"containers": selected}

    def cleanup(self):
        if not self.compose_invoked or self.log_dir is None or not self.env_file.is_file():
            self.summary["cleanup"] = {"status": "not_needed", "reason": "Compose was never invoked with a complete QA config"}
            return {"status": "not_needed"}
        errors = []
        before = []
        try:
            before = self.docker(["volume", "ls", "--quiet", "--filter", f"label=com.docker.compose.project={self.project}"], "project-volumes-before-cleanup", allow_fail=True).split()
            if self.last_returncode != 0:
                errors.append("project volume listing before cleanup failed")
        except Exception:
            errors.append("project volume listing before cleanup failed")
        try:
            self.compose_cmd(["down", "--remove-orphans"], "compose-down", allow_fail=True)
            if self.last_returncode != 0:
                errors.append("project-scoped Compose down failed")
        except Exception:
            errors.append("project-scoped Compose down failed")
        after = []
        try:
            after = self.docker(["volume", "ls", "--quiet", "--filter", f"label=com.docker.compose.project={self.project}"], "project-volumes-after-cleanup", allow_fail=True).split()
            if self.last_returncode != 0:
                errors.append("project volume listing after cleanup failed")
        except Exception:
            errors.append("project volume listing after cleanup failed")
        failed = bool(errors)
        self.summary["cleanup"] = {"status": "failed" if failed else "passed", "scope": self.project,
                                   "command": "docker compose -p <this-project> down --remove-orphans",
                                   "volumes_before": before, "volumes_after": after,
                                   "volume_lifecycle": "retained" if after else "no project volume found after down",
                                   "volumes_preserved": True, "errors": errors}
        if failed:
            raise RuntimeError("project-scoped Compose cleanup failed")
        return {k: v for k, v in self.summary["cleanup"].items() if k != "status"}

    def write_summary(self):
        if self.output_owned and self.output.exists():
            target = self.output / "summary.json"
            target.write_text(json.dumps(self.summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            try:
                os.chmod(target, 0o600)
            except OSError:
                pass

    def execute(self):
        self.stage("preflight", self.preflight)
        if not self.run:
            self.summary["plan"] = ["compose config --quiet", "compose build", "compose run init-empty", "compose up --wait",
                                     "HTTP smoke", "backup/restore comparison", "safe inspect", "compose down"]
            return 0
        try:
            self.stage("setup", self.create_private_dir)
            self.stage("config", self.config)
            self.stage("build", self.build)
            self.stage("init_empty", self.init_empty)
            self.stage("up_wait", self.up_wait)
            self.stage("http_smoke", self.http_smoke)
            self.stage("backup_restore", self.backup_restore)
            self.stage("inspect", self.inspect)
        except Exception:
            pass
        finally:
            # Any attempted run may have created resources, even if build/init failed.
            try:
                self.cleanup()
            except Exception as exc:
                if self.summary["cleanup"].get("status") != "failed":
                    self.summary["cleanup"] = {"status": "failed", "scope": self.project, "error": safe_error(exc), "volumes_preserved": True}
                self.summary["stages"]["cleanup"] = {"status": "failed", "error": safe_error(exc)}
            else:
                self.summary["stages"]["cleanup"] = {"status": "passed"} if self.summary["cleanup"].get("status") == "passed" else {"status": "not_run"}
            self.write_summary()
        return 0 if all(self.summary["stages"][s]["status"] == "passed" for s in STAGES) else 1


def safe_error(exc: Exception) -> str:
    # Keep exception messages narrow and scrub generated secrets / likely values.
    message = str(exc).splitlines()[0][:240]
    return re.sub(r"(?i)(password|token|secret|key|authorization)\s*[:=]\s*\S+", r"\1=[redacted]", message)


def backup_restore_summary(data: dict) -> dict:
    old, second, live = data["restored_old_marker"], data["restored_second_marker"], data["source_after_second"]
    if old["message_count"] != 1 or second["message_count"] != 0 or live["message_count"] != 1:
        raise RuntimeError("backup/restore message comparison failed")
    if data["table_count"] != 27 or data["trigger_count"] != 6 or data["quick_check"].lower() != "ok" or data["foreign_key_violations"] != 0:
        raise RuntimeError("database integrity expectations failed")
    return {"tables": data["table_count"], "triggers": data["trigger_count"], "quick_check": data["quick_check"],
            "foreign_key_violations": data["foreign_key_violations"], "backup_kept_original_message": True,
            "backup_excludes_second_message": True, "runtime_kept_second_message": True,
            "restored_path": "new project volume path"}


def port_is_free(port: int) -> bool:
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def docker_environment(source: dict[str, str]) -> dict[str, str]:
    """Keep only process plumbing and Docker endpoint selectors.

    In particular, Compose interpolation variables and application secrets from
    the host never reach Docker/Compose. QA configuration is passed only via
    this runner's explicit generated --env-file.
    """
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "USERPROFILE", "HOME",
               "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432", "PROGRAMDATA", "APPDATA", "LOCALAPPDATA",
               "HOMEDRIVE", "HOMEPATH", "PATHEXT",
               "DOCKER_CONFIG", "DOCKER_HOST", "DOCKER_CONTEXT"}
    return {key: value for key, value in source.items() if key.upper() in allowed}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="execute the isolated Docker/HTTP acceptance; default is read-only plan")
    parser.add_argument("--port", type=int, default=4188, help="free loopback HTTP port (default: 4188; never 8000/5173/18080/18081)")
    parser.add_argument("--timeout", type=int, default=120, help="timeout seconds for each Docker command and HTTP request")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1], help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    runner = Runner(args.repo_root, args.port, args.timeout, args.run)
    code = 1
    try:
        code = runner.execute()
    except Exception as exc:
        runner.summary["stages"]["preflight"] = {"status": "failed", "error": safe_error(exc)}
        code = 1
    finally:
        runner.write_summary()
        print(json.dumps(runner.summary, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
