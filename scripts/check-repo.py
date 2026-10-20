"""Read-only repository hygiene check; never prints file contents or secrets."""

import argparse
import json
import re
import subprocess
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    ".env.development", ".gitignore", "AGENTS.md", "README.md",
    "QUICK_START.md", "SETUP_AND_RUN.md", "index.html", "package.json",
    "package-lock.json", "vite.config.js",
}
SOURCE_DIRS = {
    "backend", "src", "public", "deploy", "docs", "prompts",
    "deliverables", "scripts", ".github",
}
# These are pre-existing source assets, pending the design/data migration waves.
LEGACY_DIRS = {"dashboard", "picture"}
RUNTIME = re.compile(
    r"(^|/)(__pycache__|node_modules|dist|coverage|htmlcov|logs|tmp|"
    r"\.venv|venv|\.pytest_cache|\.idea|\.workbuddy)(/|$)"
    r"|\.(py[cod]|db(?:-\w+)?|sqlite3?|log)$"
    r"|^backend/(uploads|temp|diagnostics_output|chroma[^/]*)(/|$)"
)


def git(*args):
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args], check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return result.stdout.decode("utf-8")


def secret_env(path):
    name = PurePosixPath(path).name
    return ((name == ".env" or name.startswith(".env."))
            and name != ".env.example" and path != ".env.development")


def inspect():
    tracked = [p for p in git("ls-files", "-z").split("\0") if p]
    ignored = [p for p in git("ls-files", "-ci", "--exclude-standard", "-z").split("\0") if p]
    forbidden = [p for p in tracked if RUNTIME.search(p) or secret_env(p)]
    unexpected = []
    legacy = []
    oversized = []
    missing = []
    for path in tracked:
        parts = PurePosixPath(path).parts
        if len(parts) == 1 and path not in ROOT_FILES:
            unexpected.append(path)
        elif len(parts) > 1 and parts[0] in LEGACY_DIRS:
            legacy.append(path)
        elif len(parts) > 1 and parts[0] not in SOURCE_DIRS:
            unexpected.append(path)
        local = ROOT / path
        if not local.is_file():
            missing.append(path)
        elif local.stat().st_size > 2 * 1024 * 1024:
            oversized.append(path)
    return {
        "tracked_count": len(tracked),
        "forbidden_tracked": forbidden,
        "ignored_but_tracked": ignored,
        "unexpected_tracked_paths": unexpected,
        "missing_tracked_files": missing,
        "oversized_files": oversized,
        "legacy_asset_paths": legacy,
        "passed": not any((forbidden, ignored, unexpected, missing, oversized)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable results")
    args = parser.parse_args()
    try:
        report = inspect()
    except (OSError, subprocess.CalledProcessError, UnicodeError) as exc:
        # Do not print arbitrary command output, which may include local data.
        print(f"ERROR: repository inspection failed ({type(exc).__name__})")
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print(f"Repository hygiene: {'PASS' if report['passed'] else 'FAIL'}")
        print(f"Tracked files: {report['tracked_count']}")
        for key in ("forbidden_tracked", "ignored_but_tracked", "unexpected_tracked_paths",
                    "missing_tracked_files", "oversized_files"):
            print(f"{key}: {len(report[key])}")
            for path in report[key]:
                print(f"  {path}")
        print(f"Legacy asset files deferred to later waves: {len(report['legacy_asset_paths'])}")
        for path in report["legacy_asset_paths"]:
            print(f"  {path}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
