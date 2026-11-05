"""Tests for workbook fidelity and isolated dataset construction (no app imports)."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("training_database", ROOT / "scripts/build-training-database.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SOURCE = ROOT / "deliverables/心域智链_数据库变量与项目数据_20261028.xlsx"


class CellFidelityTests(unittest.TestCase):
    def decode(self, xml):
        return MODULE.cell_value(ET.fromstring(xml.replace('<c ', '<c xmlns="' + MODULE.NS['s'] + '" ', 1)), [])

    def test_zero_false_blank_and_absence_remain_distinct(self):
        self.assertEqual(self.decode('<c r="A1"><v>0</v></c>')["value"], 0)
        self.assertIs(self.decode('<c r="A1" t="b"><v>0</v></c>')["value"], False)
        self.assertEqual(self.decode('<c r="A1" t="inlineStr"><is><t></t></is></c>')["value"], "")
        self.assertIsNone(self.decode('<c r="A1"/>')["value"])

    def test_formula_zero_keeps_expression_and_cache(self):
        self.assertEqual(self.decode('<c r="L7"><f>F7-SUM(D7:E7)</f><v>0</v></c>'),
                         {"value": 0, "formula": "F7-SUM(D7:E7)"})

    def test_formula_without_cache_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "cache is absent"):
            self.decode('<c r="A1"><f>SUM(A2:A3)</f></c>')

    def test_error_and_nonfinite_cells_are_rejected(self):
        for xml in ('<c r="A1" t="e"><v>#DIV/0!</v></c>', '<c r="A1"><v>1e999</v></c>'):
            with self.subTest(xml=xml), self.assertRaises(ValueError):
                self.decode(xml)

    def test_external_relationship_path_is_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.xml_target("xl/workbook.xml", "../../other.xml")


class IsolatedBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="training-db-test-")
        cls.directory = Path(cls.temp.name)
        cls.output = cls.directory / "new-package"
        cls.before = MODULE.sha256(SOURCE)
        cls.manifest = MODULE.build(SOURCE, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def connect(self):
        connection = sqlite3.connect((self.output / "training-reference.sqlite3").as_uri() + "?mode=ro", uri=True)
        connection.execute("PRAGMA query_only=ON")
        self.addCleanup(connection.close)
        return connection

    def test_source_unchanged_and_all_cells_preserved(self):
        self.assertEqual(MODULE.sha256(SOURCE), self.before)
        sheets, _ = MODULE.read_workbook(SOURCE)
        actual = {(s, c): (json.loads(v), f) for s, c, v, f in self.connect().execute(
            "SELECT sheet,cell,value_json,formula FROM source_cells")}
        expected = {(sheet, ref): (cell["value"], cell["formula"])
                    for sheet, cells in sheets.items() for ref, cell in cells.items()}
        self.assertEqual(actual, expected)

    def test_jsonl_and_database_are_identical_with_traceable_rows(self):
        records = [json.loads(line) for line in (self.output / "reference-records.jsonl").read_text(encoding="utf-8").splitlines()]
        stored = {r[0]: r[1:] for r in self.connect().execute(
            "SELECT id,sheet,source_row,payload_json,formulas_json,usage FROM reference_records")}
        self.assertEqual(len(records), len(stored))
        for record in records:
            sheet, row, data, formulas, usage = stored[record["id"]]
            self.assertEqual((sheet, row, json.loads(data), json.loads(formulas), usage),
                             (record["source"]["sheet"], record["source"]["row"], record["data"], record["formulas"], record["usage"]))
            self.assertEqual(record["source"]["sha256"], self.before)

    def test_schema_metadata_and_aggregate_invariants(self):
        connection = self.connect()
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM schema_tables").fetchone()[0], 27)
        self.assertEqual(connection.execute("SELECT SUM(field_count) FROM schema_tables").fetchone()[0], 198)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM schema_fields").fetchone()[0], 198)
        self.assertEqual(connection.execute("SELECT COUNT(*),SUM(total_students),SUM(check_difference) FROM region_education").fetchone(), (31, 38912568, 0))
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM literature_aggregates").fetchone()[0], 38)
        self.assertEqual(connection.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
        self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_reference_only_source_cannot_supply_supervised_examples(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.executescript(MODULE.DDL)
        connection.execute("INSERT INTO source_files VALUES ('s','test.xlsx','hash','2026-10-28','metadata_and_public_aggregates',0)")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "reference-only"):
            connection.execute("INSERT INTO training_examples VALUES ('x','s','classification','{}','{}','g',1,'test','candidate','hash','unassigned')")
        self.assertEqual(self.connect().execute("SELECT COUNT(*) FROM training_examples").fetchone()[0], 0)
        self.assertEqual((self.output / "training-examples.jsonl").read_bytes(), b"")

    def test_rebuild_refuses_existing_directory_and_preserves_sentinel(self):
        sentinel = self.output / "sentinel.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            MODULE.build(SOURCE, self.output)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_existing_example_cannot_be_rebound_to_reference_source(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.executescript(MODULE.DDL)
        connection.execute("INSERT INTO source_files VALUES ('ref','test.xlsx','hash','2026-10-28','metadata_and_public_aggregates',0)")
        connection.execute("INSERT INTO source_files VALUES ('synthetic','fixture.jsonl','hash2','2026-11-02','confirmed_synthetic_records',0)")
        connection.execute("INSERT INTO training_examples VALUES ('x','synthetic','classification','{}','{}','g',1,'fixture-only','candidate','hash','unassigned')")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "reference-only"):
            connection.execute("UPDATE training_examples SET source_id='ref' WHERE id='x'")
        self.assertEqual(connection.execute("SELECT source_id FROM training_examples").fetchone()[0], 'synthetic')

    def test_source_hash_and_classification_cannot_be_changed(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.executescript(MODULE.DDL)
        connection.execute("INSERT INTO source_files VALUES ('s','test.xlsx','hash','2026-10-28','metadata_and_public_aggregates',0)")
        for sql in ("UPDATE source_files SET classification='confirmed_synthetic_records' WHERE id='s'",
                    "UPDATE source_files SET sha256='other' WHERE id='s'"):
            with self.subTest(sql=sql), self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
                connection.execute(sql)

    def test_changed_source_is_rejected_before_output_creation(self):
        changed = self.directory / "changed.xlsx"
        changed.write_bytes(SOURCE.read_bytes() + b"changed")
        output = self.directory / "must-not-exist"
        with self.assertRaisesRegex(ValueError, "differs from registered"):
            MODULE.build(changed, output)
        self.assertFalse(output.exists())

    def test_manifest_matches_delivered_files(self):
        for filename, info in self.manifest["files"].items():
            path = self.output / filename
            self.assertEqual(MODULE.sha256(path), info["sha256"])
            self.assertEqual(path.stat().st_size, info["bytes"])


if __name__ == "__main__":
    unittest.main()
