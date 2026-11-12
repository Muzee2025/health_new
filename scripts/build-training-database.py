"""Import the registered project workbook into a NEW, local SQLite reference corpus.

Standard library only. Never opens app databases, loads .env, or starts training.
The workbook contains metadata/aggregates, so training_examples stays empty.
"""
from __future__ import annotations  # noqa: I001

import argparse
import hashlib
import json
import math
from pathlib import Path
import posixpath
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
TABLES = {
    "DatabaseSummary": ("数据概览", "database_snapshot", 6),
    "FieldDictionary": ("字段字典", "schema_metadata", 198),
    "TableInventory": ("数据表与记录量", "database_snapshot", 119),
    "SchemaDifferences": ("库间差异", "schema_metadata", 45),
    "JsonVariables": ("JSON子字段", "schema_metadata", 39),
    "RegionalEducation": ("地区教育数据", "public_aggregate", 31),
    "LiteratureScreening": ("文献筛查数据", "public_aggregate", 38),
}
REGISTERED_SHA256 = "79da59887ad69b1b081ea4ec9f4866bddbb2341d4e47468e1cc57bee3392649a"
DDL = """
PRAGMA foreign_keys = ON;
CREATE TABLE source_files (
 id TEXT PRIMARY KEY, filename TEXT NOT NULL, sha256 TEXT NOT NULL UNIQUE,
 snapshot_date TEXT NOT NULL, classification TEXT NOT NULL,
 supervised_examples INTEGER NOT NULL CHECK(supervised_examples = 0)
);
CREATE TABLE source_sheets (
 source_id TEXT NOT NULL REFERENCES source_files(id), name TEXT NOT NULL,
 position INTEGER NOT NULL, PRIMARY KEY(source_id,name)
);
CREATE TABLE source_cells (
 source_id TEXT NOT NULL, sheet TEXT NOT NULL, cell TEXT NOT NULL,
 value_json TEXT NOT NULL CHECK(json_valid(value_json)), formula TEXT,
 PRIMARY KEY(source_id,sheet,cell),
 FOREIGN KEY(source_id,sheet) REFERENCES source_sheets(source_id,name)
);
CREATE TABLE reference_records (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL, sheet TEXT NOT NULL,
 table_name TEXT NOT NULL, source_row INTEGER NOT NULL,
 classification TEXT NOT NULL CHECK(classification IN
 ('schema_metadata','database_snapshot','public_aggregate')),
 payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
 formulas_json TEXT NOT NULL CHECK(json_valid(formulas_json)),
 usage TEXT NOT NULL DEFAULT 'reference_only' CHECK(usage='reference_only'),
 UNIQUE(source_id,sheet,table_name,source_row),
 FOREIGN KEY(source_id,sheet) REFERENCES source_sheets(source_id,name)
);
CREATE INDEX ix_reference_table ON reference_records(table_name,source_row);
CREATE TABLE schema_tables (
 name TEXT PRIMARY KEY, module TEXT NOT NULL, field_count INTEGER NOT NULL
);
CREATE TABLE schema_fields (
 table_name TEXT NOT NULL REFERENCES schema_tables(name), name TEXT NOT NULL,
 description TEXT NOT NULL, sql_type TEXT NOT NULL,
 nullable INTEGER NOT NULL CHECK(nullable IN(0,1)),
 sensitivity TEXT NOT NULL, reference_id TEXT NOT NULL UNIQUE REFERENCES reference_records(id),
 PRIMARY KEY(table_name,name)
);
CREATE TABLE region_education (
 region TEXT PRIMARY KEY, year INTEGER NOT NULL, colleges INTEGER NOT NULL,
 undergraduate_students INTEGER NOT NULL, vocational_students INTEGER NOT NULL,
 total_students INTEGER NOT NULL CHECK(total_students = undergraduate_students + vocational_students),
 high_school_students INTEGER NOT NULL, middle_school_students INTEGER NOT NULL,
 share REAL NOT NULL CHECK(share BETWEEN 0 AND 1), students_per_college REAL NOT NULL,
 scale_rank INTEGER NOT NULL, check_difference INTEGER NOT NULL CHECK(check_difference=0),
 reference_id TEXT NOT NULL UNIQUE REFERENCES reference_records(id)
);
CREATE TABLE literature_aggregates (
 reference_id TEXT PRIMARY KEY REFERENCES reference_records(id),
 stratum TEXT NOT NULL, group_name TEXT NOT NULL, study_count INTEGER NOT NULL,
 sample_count INTEGER NOT NULL, screening_proportion REAL NOT NULL,
 ci_lower REAL NOT NULL, ci_upper REAL NOT NULL, i_squared REAL,
 limitations TEXT NOT NULL, UNIQUE(stratum,group_name),
 CHECK(0 <= ci_lower AND ci_lower <= screening_proportion AND screening_proportion <= ci_upper AND ci_upper <= 1),
 CHECK(i_squared IS NULL OR i_squared BETWEEN 0 AND 1)
);
CREATE TABLE training_examples (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES source_files(id),
 kind TEXT NOT NULL CHECK(kind IN('conversation','classification','tabular')),
 input_json TEXT NOT NULL CHECK(json_valid(input_json)),
 target_json TEXT NOT NULL CHECK(json_valid(target_json)),
 group_id TEXT NOT NULL, synthetic INTEGER NOT NULL CHECK(synthetic=1),
 label_origin TEXT NOT NULL,
 quality_status TEXT NOT NULL DEFAULT 'candidate'
 CHECK(quality_status IN('candidate','accepted','rejected')),
 content_sha256 TEXT NOT NULL UNIQUE,
 split TEXT NOT NULL DEFAULT 'unassigned'
 CHECK(split IN('unassigned','train','validation','test'))
);
CREATE TRIGGER no_reference_as_supervised BEFORE INSERT ON training_examples
WHEN (SELECT classification FROM source_files WHERE id=NEW.source_id)='metadata_and_public_aggregates'
BEGIN SELECT RAISE(ABORT,'reference-only workbook cannot supply individual training examples'); END;
CREATE TRIGGER no_reference_as_supervised_update BEFORE UPDATE OF source_id ON training_examples
WHEN (SELECT classification FROM source_files WHERE id=NEW.source_id)='metadata_and_public_aggregates'
BEGIN SELECT RAISE(ABORT,'reference-only workbook cannot supply individual training examples'); END;
CREATE TRIGGER immutable_source_provenance BEFORE UPDATE OF sha256,classification ON source_files
WHEN NEW.sha256 != OLD.sha256 OR NEW.classification != OLD.classification
BEGIN SELECT RAISE(ABORT,'source hash and classification are immutable; register a new source'); END;
"""


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def column_number(name):
    number = 0
    for ch in name:
        number = number * 26 + ord(ch) - 64
    return number


def column_name(number):
    out = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        out = chr(65 + remainder) + out
    return out


def xml_target(base, target):
    result = (target.lstrip("/") if target.startswith("/") else
              posixpath.normpath(posixpath.join(posixpath.dirname(base), target)))
    if not result.startswith("xl/") or ".." in result.split("/"):
        raise ValueError("Workbook relationship leaves xl/ directory")
    return result


def relationships(archive, file):
    rel_file = posixpath.join(posixpath.dirname(file), "_rels", posixpath.basename(file) + ".rels")
    if rel_file not in archive.namelist():
        return {}
    return {r.attrib["Id"]: xml_target(file, r.attrib["Target"])
            for r in ET.fromstring(archive.read(rel_file))
            if r.attrib.get("TargetMode") != "External"}


def cell_value(cell, shared_strings):
    value_node, formula_node = cell.find("s:v", NS), cell.find("s:f", NS)
    text = value_node.text if value_node is not None else None
    kind = cell.attrib.get("t", "n")
    if kind == "e":
        raise ValueError("Excel error cell: " + cell.attrib["r"])
    if formula_node is not None and text is None:
        raise ValueError("Formula cache is absent: " + cell.attrib["r"])
    if kind == "s":
        value = shared_strings[int(text)]
    elif kind == "inlineStr":
        value = "".join(cell.find("s:is", NS).itertext())
    elif kind == "b":
        if text not in ("0", "1"):
            raise ValueError("Invalid boolean")
        value = text == "1"
    elif kind in ("str", "d"):
        value = text if text is not None else ""
    elif text is None:
        value = None
    else:
        value = float(text) if any(c in text.lower() for c in ".e") else int(text)
        if not math.isfinite(value):
            raise ValueError("Non-finite numeric cell")
    return {"value": value, "formula": formula_node.text if formula_node is not None else None}


def read_workbook(path):
    sheets, tables = {}, {}
    with zipfile.ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = ["".join(item.itertext()) for item in
                      ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("s:si", NS)]
        rels = relationships(archive, "xl/workbook.xml")
        for sheet in ET.fromstring(archive.read("xl/workbook.xml")).find("s:sheets", NS):
            name = sheet.attrib["name"]
            file = rels[sheet.attrib["{" + REL + "}id"]]
            root = ET.fromstring(archive.read(file))
            cells = {}
            for cell in root.findall("s:sheetData/s:row/s:c", NS):
                decoded = cell_value(cell, shared)
                if decoded["value"] is not None or decoded["formula"] is not None:
                    cells[cell.attrib["r"]] = decoded
            sheets[name] = cells
            sheet_rels = relationships(archive, file)
            for part in root.findall("s:tableParts/s:tablePart", NS):
                table = ET.fromstring(archive.read(sheet_rels[part.attrib["{" + REL + "}id"]]))
                table_name = table.attrib["name"]
                if table_name in tables:
                    raise ValueError("Duplicate table name")
                match = re.fullmatch(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", table.attrib["ref"])
                if not match:
                    raise ValueError("Unsupported table range")
                first, header, last, end = match.groups()
                columns = [column_name(c) for c in range(column_number(first), column_number(last) + 1)]
                headers = [cells[c + header]["value"] for c in columns]
                if len(set(headers)) != len(headers) or not all(isinstance(h, str) and h for h in headers):
                    raise ValueError("Invalid or duplicate table headers")
                rows = []
                for row in range(int(header) + 1, int(end) + 1):
                    payload, formulas = {}, {}
                    for col, label in zip(columns, headers):  # noqa: B905
                        cell = cells.get(f"{col}{row}", {"value": None, "formula": None})
                        payload[label] = cell["value"]
                        if cell["formula"] is not None:
                            formulas[label] = cell["formula"]
                    rows.append({"row": row, "payload": payload, "formulas": formulas})
                tables[table_name] = {"sheet": name, "rows": rows}
    return sheets, tables


def validate_source(sheets, tables):
    if set(tables) != set(TABLES) or set(sheets) != {v[0] for v in TABLES.values()}:
        raise ValueError("Unexpected workbook sheets or tables")
    for name, (sheet, _, count) in TABLES.items():
        if tables[name]["sheet"] != sheet or len(tables[name]["rows"]) != count:
            raise ValueError("Unexpected table shape: " + name)
    fields = [r["payload"] for r in tables["FieldDictionary"]["rows"]]
    keys = {(r["数据表"], r["字段变量"]) for r in fields}
    if len(keys) != 198 or len({key[0] for key in keys}) != 27:
        raise ValueError("Field dictionary has duplicate/missing definitions")


def populate(connection, sheets, tables, source, digest):
    source_id = "xlsx:" + digest
    connection.executescript(DDL)
    connection.execute("INSERT INTO source_files VALUES (?,?,?,?,?,0)",
                       (source_id, source.name, digest, "2026-10-28", "metadata_and_public_aggregates"))
    for position, (name, cells) in enumerate(sheets.items(), 1):
        connection.execute("INSERT INTO source_sheets VALUES (?,?,?)", (source_id, name, position))
        connection.executemany("INSERT INTO source_cells VALUES (?,?,?,?,?)", [
            (source_id, name, ref, dumps(c["value"]), c["formula"]) for ref, c in cells.items()])
    records = []
    for name, (_, classification, _) in TABLES.items():
        sheet = tables[name]["sheet"]
        for row in tables[name]["rows"]:
            record_id = hashlib.sha256(f"{digest}:{sheet}:{name}:{row['row']}".encode()).hexdigest()
            connection.execute("INSERT INTO reference_records VALUES (?,?,?,?,?,?,?,?,?)", (
                record_id, source_id, sheet, name, row["row"], classification,
                dumps(row["payload"]), dumps(row["formulas"]), "reference_only"))
            records.append({"id": record_id, "kind": classification, "usage": "reference_only",
                            "source": {"filename": source.name, "sha256": digest, "sheet": sheet,
                                       "table": name, "row": row["row"]},
                            "data": row["payload"], "formulas": row["formulas"]})
    dictionary = [r for r in records if r["source"]["table"] == "FieldDictionary"]
    for table in sorted({r["data"]["数据表"] for r in dictionary}):
        fields = [r for r in dictionary if r["data"]["数据表"] == table]
        connection.execute("INSERT INTO schema_tables VALUES (?,?,?)", (table, fields[0]["data"]["模块"], len(fields)))
        for record in fields:
            d = record["data"]
            if d["允许NULL"] not in ("允许", "不允许"):
                raise ValueError("Unknown nullable value")
            connection.execute("INSERT INTO schema_fields VALUES (?,?,?,?,?,?,?)", (
                table, d["字段变量"], d["中文含义"], d["SQLite类型"],
                int(d["允许NULL"] == "允许"), d["数据敏感性"], record["id"]))
    for record in records:
        d = record["data"]
        if record["source"]["table"] == "RegionalEducation":
            values = [d[k] for k in ("地区", "年份", "普通/职业高校数（所）", "普通本科在校生（人）",
                      "职业本专科在校生（人）", "本专科合计（人）", "普通高中在校生（人）", "初中在校生（人）",
                      "本专科占31地比重", "每所高校平均本专科生（人/所）", "本专科规模排序", "合计校验差额（人）")]
            connection.execute("INSERT INTO region_education VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (*values, record["id"]))
        elif record["source"]["table"] == "LiteratureScreening":
            values = [d[k] for k in ("层级", "组别", "研究数k", "样本数n", "筛查阳性合并比例", "95%CI下限", "95%CI上限", "I²", "口径与限制")]
            connection.execute("INSERT INTO literature_aggregates VALUES (?,?,?,?,?,?,?,?,?,?)", (record["id"], *values))
    return records


def build(source, output):
    source, output = Path(source).resolve(), Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError("Output must be a NEW directory; existing files are never replaced")
    digest = sha256(source)
    if digest != REGISTERED_SHA256:
        raise ValueError("Workbook differs from registered source; inspect before importing")
    sheets, tables = read_workbook(source)
    validate_source(sheets, tables)
    # Validate in memory first, leaving no partially populated deliverable on validation errors.
    with sqlite3.connect(":memory:") as connection:
        records = populate(connection, sheets, tables, source, digest)
        connection.commit()
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("SQLite integrity check failed")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("SQLite foreign key check failed")
        if sha256(source) != digest:
            raise ValueError("Source changed during import")
        output.mkdir(parents=True, exist_ok=False)
        db_path = output / "training-reference.sqlite3"
        with sqlite3.connect(db_path) as target:
            connection.backup(target)
    (output / "reference-records.jsonl").write_text("".join(dumps(r) + "\n" for r in records), encoding="utf-8")
    (output / "training-examples.jsonl").write_text("", encoding="utf-8")
    (output / "schema.sql").write_text(DDL, encoding="utf-8")
    (output / "使用说明.md").write_text("""> owner: A ｜ version: 1.0 ｜ status: 本地资料库已建立，监督样本为空 ｜ updated: 2026-11-02

# 心域智链通用训练资料包

SQLite 文件可直接用支持 SQLite 的数据库工具打开，不需要另启数据库服务。
这是独立资料库，不是现有网站的运行库。登记的27张业务表/198个字段是结构定义，
不会据此创建虚拟学生、消息或诊断记录。原 Excel 与已有数据库保留。

- `training-reference.sqlite3`：9张资料/来源/样本管理表；全量工作簿有效单元格及公式缓存保存在 `source_cells`。
- `reference-records.jsonl`：476条工作簿表格记录；每条带文件名、SHA256、工作表、表名、行号、类别及 `reference_only` 标记。
- `training-examples.jsonl`：空文件，对应 `training_examples` 空表；可用监督样本0条。
- `schema.sql`：可复建的资料库结构；`manifest.json`：源及输出校验值、数量和用途。

字段字典198条；数据库快照/表计数/差异/JSON键是结构资料。
31条地区教育数据和38条文献汇总可用于资料查询、统计复现与检索原型，
不能当作个人心理标签、逐条问答或项目用户量。文献亚组不能跨组相加。
来源 URL、统计口径与原说明都在 `source_cells` 中；结构化记录保留原表限制列。
统计是2026-10-28工作簿快照，不代表当前运行库的状态。

未读取历史聊天正文、未补造样本、未生成模型/专家标签、未拆分训练/验证/测试集，
未训练或上传。公式使用工作簿缓存值，未重算。底层来源的许可/适用性需要按后续用途核对。
以后有真实存在且确认合成的逐条数据时，再按来源、会话分组、去重结果和标签依据导入样本表。
表中预留 `input_json`、`target_json`、`group_id`、`label_origin`、`content_sha256` 和 `split`；
本轮 Excel 来源不能作为个人监督样本插入或改绑，来源哈希和类别保持不可变；
数据库触发器会拒绝这些误操作。此规则是数据质量约束，不替代文件访问控制。

示例只读 SQL：

```sql
SELECT name, field_count FROM schema_tables ORDER BY name;
SELECT region, total_students FROM region_education ORDER BY total_students DESC;
SELECT stratum, group_name, screening_proportion, limitations FROM literature_aggregates;
SELECT COUNT(*) FROM training_examples; -- 0
SELECT sheet, cell, value_json FROM source_cells WHERE sheet='文献筛查数据' AND cell IN ('A47','A48','A49');
```

复建（输出必须使用全新目录）：

```powershell
python scripts/build-training-database.py --source 'deliverables/心域智链_数据库变量与项目数据_20261028.xlsx' --output 'tmp/training-reference-rebuild'
```
""", encoding="utf-8")
    manifest = {"format_version": "1.0", "source_file": source.name, "source_sha256": digest,
                "snapshot_date": "2026-10-28", "built_for": "2026-11-02",
                "database": db_path.name, "reference_records": len(records),
                "source_sheets": len(sheets), "source_cells": sum(map(len, sheets.values())),
                "cached_formulas": sum(c["formula"] is not None for s in sheets.values() for c in s.values()),
                "table_rows": {n: len(t["rows"]) for n, t in tables.items()},
                "application_schema_tables": 27, "application_schema_fields": 198,
                "supervised_training_examples": 0, "training_started": False,
                "data_usage": "reference_only", "formula_policy": "cached values preserved; not recalculated",
                "files": {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size}
                          for p in sorted(output.iterdir())}}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New directory only")
    args = parser.parse_args()
    manifest = build(args.source, args.output)
    print(dumps({k: manifest[k] for k in ("reference_records", "source_cells", "cached_formulas", "supervised_training_examples")}))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
