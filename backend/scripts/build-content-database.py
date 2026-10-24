"""Validate and import the reviewed platform-use article catalog into a new SQLite file."""

import argparse
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = Path(__file__).with_name("content-catalog.json")
MANAGED_FIELDS = ("title", "summary", "content", "cover_url", "source", "source_url", "category")
ALLOWED_TAGS = {"p", "h2", "ul", "ol", "li", "strong", "em", "br"}
EXPECTED_KEYS = {
    "id", "title", "category", "summary", "content", "source", "source_url",
    "cover_url", "license", "review_status", "provenance",
}


class SafeHtmlValidator(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.errors = []
        self.stack = []
        self.visible_text = []

    def handle_data(self, data):
        self.visible_text.append(data)

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            self.errors.append(f"unsupported HTML element: {tag}")
        if attrs:
            self.errors.append(f"HTML attributes are not allowed: {tag}")
        if tag != "br":
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        if tag not in ALLOWED_TAGS or attrs:
            self.errors.append(f"unsupported HTML element or attributes: {tag}")

    def handle_endtag(self, tag):
        if tag == "br":
            self.errors.append("br must be a void element")
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unbalanced HTML element: {tag}")
            return
        self.stack.pop()

    def close(self):
        super().close()
        if self.stack:
            self.errors.append("unclosed HTML elements")


def validate_catalog(path=CATALOG_PATH):
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"catalog cannot be read as UTF-8 JSON: {exc}") from None
    if (not isinstance(catalog, dict) or not isinstance(catalog.get("catalog_version"), str)
            or not catalog["catalog_version"].strip()):
        raise ValueError("catalog_version must be a non-empty string")
    articles = catalog.get("articles")
    if not isinstance(articles, list) or not articles:
        raise ValueError("articles must be a non-empty list")

    errors = []
    ids, titles = set(), set()
    for index, article in enumerate(articles):
        label = f"articles[{index}]"
        if not isinstance(article, dict):
            errors.append(f"{label} must be an object")
            continue
        missing = EXPECTED_KEYS - set(article)
        extra = set(article) - EXPECTED_KEYS
        if missing:
            errors.append(f"{label} missing fields: {', '.join(sorted(missing))}")
        if extra:
            errors.append(f"{label} has unsupported fields: {', '.join(sorted(extra))}")
        if missing:
            continue
        identifier, title = article["id"], article["title"]
        if not isinstance(identifier, str) or not identifier.strip():
            errors.append(f"{label}.id must be a non-empty string")
        else:
            if identifier in ids:
                errors.append(f"duplicate catalog id: {identifier}")
            ids.add(identifier)
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            errors.append(f"{label}.title must contain 1–200 characters")
        else:
            if title != title.strip():
                errors.append(f"{label}.title must not have surrounding whitespace")
            if title in titles:
                errors.append(f"duplicate catalog title at {label}")
            titles.add(title)
        for key, limit in (("summary", 500), ("category", 50), ("source", 100)):
            value = article[key]
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                errors.append(f"{label}.{key} must contain 1–{limit} characters")
        if article["category"] != "平台使用指南":
            errors.append(f"{label}.category must be 平台使用指南")
        if article["source"] != "心域智链·使用指南":
            errors.append(f"{label}.source must be 心域智链·使用指南")
        if article["license"] != "项目原创":
            errors.append(f"{label}.license must be 项目原创")
        if article["review_status"] != "engineering_reviewed":
            errors.append(f"{label}.review_status must be engineering_reviewed")
        if article["source_url"] is not None or article["cover_url"] is not None:
            errors.append(f"{label} must not invent external source or cover URLs")
        content = article["content"]
        if not isinstance(content, str) or not content.strip() or len(content) > 100_000:
            errors.append(f"{label}.content must contain 1–100000 characters of HTML text")
        else:
            parser = SafeHtmlValidator()
            try:
                parser.feed(content)
                parser.close()
            except Exception:
                parser.errors.append("HTML could not be parsed")
            errors.extend(f"{label}.content {error}" for error in parser.errors)
            if not ''.join(parser.visible_text).strip():
                errors.append(f"{label}.content HTML must contain visible text")
        provenance = article["provenance"]
        if not isinstance(provenance, list) or not provenance:
            errors.append(f"{label}.provenance must list existing project source paths")
        else:
            for source_path in provenance:
                if (not isinstance(source_path, str) or ".." in Path(source_path).parts
                        or Path(source_path).is_absolute() or not (ROOT / source_path).is_file()):
                    errors.append(f"{label}.provenance contains a missing or unsafe project path")
    if errors:
        raise ValueError("; ".join(errors))
    return catalog


def normalized_new_path(raw):
    requested = Path(raw).expanduser().absolute()
    if requested.is_symlink() or requested.exists():
        raise ValueError("output path must be a new, nonexistent path (including no empty file or symlink)")
    if not requested.parent.is_dir():
        raise ValueError("output parent directory must already exist")
    return requested


def validate_source_path(raw, output):
    source = Path(raw).expanduser().absolute()
    if source.is_symlink() or not source.is_file():
        raise ValueError("source must be an existing regular SQLite file, not a symlink")
    if source.resolve() == output.resolve():
        raise ValueError("source and output must be different files")
    return source


def isolated_schema_environment(database):
    keep = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LOCALAPPDATA", "APPDATA", "USERPROFILE"}
    env = {key: value for key, value in os.environ.items() if key.upper() in keep}
    env.update({
        "PYTHON_DOTENV_DISABLED": "1",
        "DATABASE_URL": "sqlite:///" + database.resolve().as_posix(),
        "JWT_SECRET_KEY": "synthetic-content-catalog-schema-only",
        "RAG_ENABLED": "false",
        "RAG_ALLOW_MODEL_DOWNLOAD": "false",
    })
    return env


def create_empty_schema(output):
    initializer = ROOT / "backend" / "scripts" / "init-empty-database.py"
    result = subprocess.run(
        [sys.executable, str(initializer), "--database", str(output)],
        cwd=ROOT,
        env=isolated_schema_environment(output),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"empty schema initialization failed (exit {result.returncode}); new output retained")


def backup_source_to_new_output(source, output):
    # Reserve the destination exclusively so an existing file can never be replaced.
    descriptor = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    source_uri = source.as_uri() + "?mode=ro"
    source_db = sqlite3.connect(source_uri, uri=True)
    target_db = sqlite3.connect(output)
    try:
        source_db.backup(target_db)
        target_db.commit()
    finally:
        target_db.close()
        source_db.close()


def article_rows(catalog):
    for item in catalog["articles"]:
        yield tuple(item[field] for field in MANAGED_FIELDS)


def validate_article_schema(connection):
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "articles" not in tables:
        raise ValueError("database schema has no articles table")
    columns = {row[1] for row in connection.execute("PRAGMA table_info(articles)")}
    missing = set(MANAGED_FIELDS) - columns
    if missing:
        raise ValueError("articles table lacks required columns: " + ", ".join(sorted(missing)))


def import_catalog(catalog, output):
    connection = sqlite3.connect(output, timeout=30, isolation_level=None)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        validate_article_schema(connection)
        planned = []
        for values in article_rows(catalog):
            title = values[0]
            rows = connection.execute(
                "SELECT title, summary, content, cover_url, source, source_url, category, views "
                "FROM articles WHERE title = ?", (title,),
            ).fetchall()
            if not rows:
                planned.append(values)
                continue
            if len(rows) != 1 or tuple(rows[0][:len(MANAGED_FIELDS)]) != values:
                raise ValueError("article title conflicts with existing managed content; no articles were inserted")
            # Existing view counts are intentionally preserved.
        for values in planned:
            connection.execute(
                "INSERT INTO articles (title, summary, content, cover_url, source, source_url, category, views) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 0)", values,
            )
        connection.commit()
        return {"inserted": len(planned), "skipped": len(catalog["articles"]) - len(planned)}
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()


def verify_database(output):
    uri = output.as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        article_count = connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        return {"quick_check": quick_check, "foreign_key_violations": len(violations), "articles": article_count}
    finally:
        connection.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="new SQLite output path, or explicit database for --verify")
    parser.add_argument("--source", help="optional explicit SQLite source; read-only copied to new output")
    parser.add_argument("--apply", action="store_true", help="create new output and import validated catalog")
    parser.add_argument("--verify", action="store_true", help="read-only integrity and article count report")
    args = parser.parse_args(argv)
    if args.apply and args.verify:
        parser.error("--apply and --verify are separate modes")
    if args.source and not args.apply:
        parser.error("--source is available only with --apply")
    try:
        catalog = validate_catalog()
        output = Path(args.output).expanduser().absolute()
        if args.verify:
            if output.is_symlink() or not output.is_file():
                raise ValueError("verify target must be an existing regular file, not a symlink")
            result = verify_database(output)
            print(json.dumps({"status": "verified", **result}, ensure_ascii=False, sort_keys=True))
            return 0 if result["quick_check"] == "ok" and result["foreign_key_violations"] == 0 else 1
        output = normalized_new_path(args.output)
        source = validate_source_path(args.source, output) if args.source else None
        if not args.apply:
            print(json.dumps({
                "status": "plan", "catalog_articles": len(catalog["articles"]),
                "source_provided": source is not None, "output_available": True,
            }, ensure_ascii=False, sort_keys=True))
            return 0
        if source:
            backup_source_to_new_output(source, output)
        else:
            create_empty_schema(output)
        result = import_catalog(catalog, output)
        integrity = verify_database(output)
        print(json.dumps({"status": "imported", **result, **integrity}, ensure_ascii=False, sort_keys=True))
        return 0 if integrity["quick_check"] == "ok" and integrity["foreign_key_violations"] == 0 else 1
    except (OSError, sqlite3.Error, ValueError, RuntimeError) as exc:
        print(f"content database operation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
