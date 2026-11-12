"""Synthetic-only checks for the platform-use content catalog importer."""

import hashlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app
from app.models import Base

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend" / "scripts" / "build-content-database.py"
CATALOG = ROOT / "backend" / "scripts" / "content-catalog.json"
spec = importlib.util.spec_from_file_location("content_database_tool", SCRIPT)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def _env():
    env = os.environ.copy()
    env.update({
        "DATABASE_URL": "sqlite:///inherited-must-not-be-used.db",
        "PYTHON_DOTENV_DISABLED": "1",
        "JWT_SECRET_KEY": "synthetic-catalog-test-key-only",
        "RAG_ENABLED": "false",
        "RAG_ALLOW_MODEL_DOWNLOAD": "false",
    })
    return env


def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)], cwd=cwd or ROOT,
        env=_env(), capture_output=True, text=True, check=False,
    )


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _article_count(path):
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]


def test_catalog_has_eight_original_guides_with_existing_code_provenance():
    catalog = tool.validate_catalog()

    assert len(catalog["articles"]) == 8
    assert {item["review_status"] for item in catalog["articles"]} == {"engineering_reviewed"}
    assert {item["license"] for item in catalog["articles"]} == {"项目原创"}
    assert all(item["source"] == "心域智链·使用指南" for item in catalog["articles"])
    assert all(item["source_url"] is None and item["cover_url"] is None for item in catalog["articles"])
    assert all((ROOT / source).is_file() for item in catalog["articles"] for source in item["provenance"])


def test_plan_validates_paths_without_creating_output_or_opening_database(tmp_path):
    output = tmp_path / "planned.sqlite3"
    decoy = tmp_path / "inherited-must-not-be-used.db"

    result = _run("--output", output)

    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "catalog_articles": 8, "output_available": True, "source_provided": False, "status": "plan"
    }
    assert not output.exists()
    assert not decoy.exists()


def test_apply_without_source_creates_new_schema_and_verify_is_read_only(tmp_path):
    output = tmp_path / "new-content.sqlite3"

    result = _run("--apply", "--output", output)

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "imported"
    assert report["inserted"] == 8 and report["skipped"] == 0
    assert report["articles"] == 8 and report["quick_check"] == "ok"
    assert report["foreign_key_violations"] == 0
    with sqlite3.connect(output) as connection:
        assert connection.execute("SELECT COUNT(*) FROM articles WHERE views <> 0").fetchone()[0] == 0
        table_count = connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    assert table_count == len(Base.metadata.tables)

    before = _digest(output)
    verified = _run("--verify", "--output", output)
    assert verified.returncode == 0
    assert json.loads(verified.stdout)["articles"] == 8
    assert _digest(output) == before


def test_source_is_copied_unchanged_and_matching_content_is_skipped(tmp_path):
    source = tmp_path / "synthetic-source.sqlite3"
    seed = tmp_path / "seeded-output.sqlite3"
    repeated = tmp_path / "repeat-output.sqlite3"
    created = _run("--apply", "--output", seed)
    assert created.returncode == 0, created.stderr
    source.write_bytes(seed.read_bytes())
    with sqlite3.connect(source) as connection:
        connection.execute("UPDATE articles SET views = 17, created_at = '2026-10-01 01:02:03'")
    source_hash = _digest(source)

    result = _run("--apply", "--source", source, "--output", repeated)

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["inserted"] == 0 and report["skipped"] == 8
    assert report["articles"] == 8
    assert _digest(source) == source_hash
    with sqlite3.connect(repeated) as connection:
        assert connection.execute("SELECT COUNT(*) FROM articles WHERE views = 17 AND created_at = '2026-10-01 01:02:03'").fetchone()[0] == 8


def test_conflicting_title_rolls_back_all_catalog_insertions_and_retains_output(tmp_path):
    source = tmp_path / "conflict-source.sqlite3"
    output = tmp_path / "conflict-output.sqlite3"
    engine = create_engine(f"sqlite:///{source.as_posix()}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO articles (title, summary, content, source, category, views) "
            "VALUES (:title, 'old summary', 'old content', 'synthetic', '平台使用指南', 7)"
        ), {"title": "如何阅读平台中的心理科普文章"})
    engine.dispose()
    source_hash = _digest(source)

    result = _run("--apply", "--source", source, "--output", output)

    assert result.returncode == 1
    assert "conflicts" in result.stderr
    assert output.is_file()
    assert _article_count(output) == 1
    assert _digest(source) == source_hash


@pytest.mark.parametrize("bad_html", [
    "<script>alert(1)</script>",
    "<p onclick=\"x()\">unsafe</p>",
    "<img src=x>",
])
def test_catalog_rejects_unsafe_html(tmp_path, bad_html):
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    data["articles"][0]["content"] = bad_html
    candidate = tmp_path / "catalog.json"
    candidate.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="HTML"):
        tool.validate_catalog(candidate)


def test_catalog_rejects_external_or_placeholder_sources_and_duplicate_titles(tmp_path):
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    data["articles"][0]["source_url"] = "https://example.com/fake"
    candidate = tmp_path / "catalog.json"
    candidate.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="URLs"):
        tool.validate_catalog(candidate)

    data["articles"][0]["source_url"] = None
    data["articles"][1]["title"] = data["articles"][0]["title"]
    candidate.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate catalog title"):
        tool.validate_catalog(candidate)


def test_existing_empty_file_and_symlink_outputs_are_refused(tmp_path):
    existing = tmp_path / "existing.sqlite3"
    existing.touch()
    result = _run("--apply", "--output", existing)
    assert result.returncode == 1
    assert existing.stat().st_size == 0


def test_symlink_output_guard_is_enforced(tmp_path, monkeypatch):
    linked = tmp_path / "synthetic-link.sqlite3"
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda self: self == linked or original(self))
    with pytest.raises(ValueError, match="symlink"):
        tool.normalized_new_path(linked)


def test_real_symlink_output_is_refused_when_available(tmp_path):
    existing = tmp_path / "symlink-target.sqlite3"
    existing.touch()
    link = tmp_path / "linked.sqlite3"
    try:
        link.symlink_to(existing)
    except (OSError, NotImplementedError):
        pytest.skip("real symlink creation is not available in this environment")
    linked = _run("--apply", "--output", link)
    assert linked.returncode == 1
    assert existing.stat().st_size == 0


@pytest.mark.parametrize("field,value", [
    ("title", []), ("title", " surrounded "), ("content", "x" * 100_001),
    ("content", "<p> </p>"), ("content", "<p>&nbsp;</p>"),
], ids=["invalid-title-type", "title-whitespace", "long-content", "empty-html", "empty-entity"])
def test_catalog_rejects_invalid_or_empty_content(tmp_path, field, value):
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    data["articles"][0][field] = value
    candidate = tmp_path / "invalid-catalog.json"
    candidate.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        tool.validate_catalog(candidate)


def test_built_catalog_is_readable_through_actual_article_api(tmp_path):
    output = tmp_path / "api-content.sqlite3"
    result = _run("--apply", "--output", output)
    assert result.returncode == 0, result.stderr
    engine = create_engine(f"sqlite:///{output.as_posix()}", connect_args={"check_same_thread": False})
    sessions = sessionmaker(bind=engine)

    def database():
        with sessions() as db:
            yield db

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = database
    try:
        with TestClient(app) as client:
            response = client.get("/api/student/articles")
            assert response.status_code == 200
            rows = response.json()
            assert len(rows) == 8
            expected = {item["title"]: item for item in tool.validate_catalog()["articles"]}
            for row in rows:
                detail = client.get(f"/api/student/articles/{row['id']}")
                assert detail.status_code == 200
                assert detail.json()["content"] == expected[row["title"]]["content"]
                assert row["views"] == 0 and row["cover_url"] is None
            with sessions() as db:
                assert db.execute(text("SELECT COUNT(*) FROM users")).scalar() == 0
                assert db.execute(text("SELECT COUNT(*) FROM teacher_student_assignments")).scalar() == 0
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        engine.dispose()
