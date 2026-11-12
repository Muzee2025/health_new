"""Read-only repository hygiene check; never prints file contents or secrets."""

import argparse
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    ".editorconfig", ".env.development", ".gitattributes", ".gitignore",
    ".prettierignore", ".prettierrc.json", "AGENTS.md", "README.md",
    "QUICK_START.md", "SETUP_AND_RUN.md", "eslint.config.js", "index.html",
    "package.json", "package-lock.json", "ruff.toml", "tsconfig.json",
    "vite.config.js",
}
# Tracked despite matching RUNTIME below, and deliberately so. This database is
# a manifest-declared deliverable whose sha256 is pinned in the package record,
# and the backend baseline needs it to exist in a clean checkout: without it
# setUpClass fails and the suite drops from 196 tests to 47 plus an error. The
# .gitignore exception that keeps it tracked was added in 08a4266; this is the
# same decision on the checker's side, kept as an explicit path rather than a
# loosened pattern so no other *.sqlite3 file can slip in.
PINNED_ARTIFACTS = {
    "deliverables/心域智链_通用训练资料包_20261102/training-reference.sqlite3",
}
# Tracked files above the 2 MB ceiling, all of them deliverables that predate
# it. The ceiling exists to stop new blobs of this size entering the tree, so
# these are recorded by exact path rather than by raising the limit, which
# would also let anything new through. Clearing them is plan A's job (see
# docs/ops/方案A执行清单_20261113.md); deleting the entries here is the signal
# that a file left the tree.
ACKNOWLEDGED_OVERSIZED = {
    "deliverables/心域智链_公开文献数据包_20261028.zip",
    "deliverables/心域智链_六章答辩PPT_图片比例与原理可视化版_20261031.pptx",
    "deliverables/心域智链_六章答辩PPT_多智能体与专家模型扩展版_20261031.pptx",
    "deliverables/心域智链_六章答辩PPT_多智能体协作机制优化版_20261031.pptx",
    "deliverables/心域智链_六章答辩PPT_批注修订版_20261031.pptx",
    "deliverables/心域智链_高校两学期模拟库_20261104.zip",
    "deliverables/心域智链_高校两学期模拟库_20261104/platform-events.csv",
    "deliverables/心域智链_高校两学期模拟库_20261104/student-semesters.csv",
    "deliverables/心域智链项目策划书_内容完善修订稿_20261029.docx",
    "deliverables/心域智链项目计划书_系统内容与截图补充_20261029.docx",
    "deliverables/逐页优化预览_20261101/心域智链_18页逐页优化参考稿_20261101.pptx",
}
SOURCE_DIRS = {
    "backend", "src", "public", "deploy", "docs", "prompts",
    "deliverables", "scripts", ".github",
}
# These are pre-existing source assets, pending the design/data migration waves.
# `picture` left this set once its three PNGs moved to
# src/assets/avatars/teachers/legacy/ (with manifest entries). It must be removed
# only after the move: the branch below is an `elif`, so a still-present
# picture/*.png would otherwise fall through to `unexpected_tracked_paths` and
# fail the check.
LEGACY_DIRS = {"dashboard"}
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
    forbidden = [p for p in tracked
                 if (RUNTIME.search(p) or secret_env(p)) and p not in PINNED_ARTIFACTS]
    unexpected = []
    legacy = []
    oversized = []
    acknowledged = []
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
            if path in ACKNOWLEDGED_OVERSIZED:
                acknowledged.append(path)
            else:
                oversized.append(path)
    return {
        "tracked_count": len(tracked),
        "forbidden_tracked": forbidden,
        "ignored_but_tracked": ignored,
        "unexpected_tracked_paths": unexpected,
        "missing_tracked_files": missing,
        "oversized_files": oversized,
        "acknowledged_oversized": acknowledged,
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
        print(f"Oversized deliverables accepted for now: {len(report['acknowledged_oversized'])}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
