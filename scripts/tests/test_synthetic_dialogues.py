"""Verify synthetic provenance, context integrity, fidelity and isolated writes."""
import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("synthetic_import", ROOT / "scripts/import-synthetic-dialogues.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SOURCE = ROOT / "backend/training_data/synthetic-qa-20261102"
REFERENCE = ROOT / "deliverables/心域智链_通用训练资料包_20261102"


class SourceValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records, cls.sources = MODULE.load_records(SOURCE)

    def changed(self):
        return copy.deepcopy(self.records)

    def test_invented_acceptance_flag_is_rejected(self):
        records = self.changed()
        records[0]["quality_status"] = "accepted"
        with self.assertRaisesRegex(ValueError, "source keys"):
            MODULE.validate_records(records)

    def test_duplicate_questions_ignore_unicode_punctuation_and_spacing(self):
        records = self.changed()
        records[1]["question"] = records[0]["question"] + " ！？"
        with self.assertRaisesRegex(ValueError, "duplicate question"):
            MODULE.validate_records(records)

    def test_duplicate_answers_are_rejected(self):
        records = self.changed()
        records[1]["answer"] = records[0]["answer"]
        with self.assertRaisesRegex(ValueError, "duplicate answer"):
            MODULE.validate_records(records)

    def test_wrong_or_missing_history_is_rejected(self):
        records = self.changed()
        next(r for r in records if r["turn_index"] == 2)["history"] = []
        with self.assertRaisesRegex(ValueError, "History differs"):
            MODULE.validate_records(records)

    def test_cross_scenario_history_is_rejected(self):
        records = self.changed()
        turn = next(r for r in records if r["turn_index"] == 2)
        turn["history"][0]["content"] = "another fictional scenario"
        with self.assertRaisesRegex(ValueError, "History differs"):
            MODULE.validate_records(records)

    def test_boolean_turn_index_cannot_masquerade_as_one(self):
        records = self.changed()
        records[0]["turn_index"] = True
        with self.assertRaisesRegex(ValueError, "turn index"):
            MODULE.validate_records(records)

    def test_out_of_order_turn_is_rejected(self):
        records = self.changed()
        index = next(i for i, r in enumerate(records) if r["turn_index"] == 2)
        records[index], records[index - 1] = records[index - 1], records[index]
        with self.assertRaisesRegex(ValueError, "turn order"):
            MODULE.validate_records(records)

    def test_raw_source_cannot_inject_internal_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            for name in MODULE.SOURCE_NAMES:
                (path / name).write_bytes((SOURCE / name).read_bytes())
            lines = (path / MODULE.SOURCE_NAMES[0]).read_text(encoding="utf-8").splitlines()
            record = json.loads(lines[0])
            record["_source_line"] = 999
            lines[0] = json.dumps(record, ensure_ascii=False)
            (path / MODULE.SOURCE_NAMES[0]).write_text("\n".join(lines), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "authored source keys"):
                MODULE.load_records(path)


class NewDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="synthetic-db-test-")
        cls.output = Path(cls.temp.name) / "new-package"
        cls.old_db_hash = MODULE.sha256(REFERENCE / "training-reference.sqlite3")
        cls.source_hashes = {name: MODULE.sha256(SOURCE / name) for name in MODULE.SOURCE_NAMES}
        cls.manifest = MODULE.build(REFERENCE, SOURCE, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def connect(self, path=None):
        connection = sqlite3.connect((path or self.output / "synthetic-training.sqlite3").resolve().as_uri() + "?mode=ro", uri=True)
        connection.execute("PRAGMA query_only=ON")
        self.addCleanup(connection.close)
        return connection

    def test_prior_database_and_source_bytes_unchanged(self):
        self.assertEqual(MODULE.sha256(REFERENCE / "training-reference.sqlite3"), self.old_db_hash)
        for name, value in self.source_hashes.items():
            self.assertEqual(MODULE.sha256(SOURCE / name), value)

    def test_every_old_reference_row_is_preserved(self):
        old = self.connect(REFERENCE / "training-reference.sqlite3")
        new = self.connect()
        for table in MODULE.COPY_TABLES:
            if table == "training_examples":
                continue
            with self.subTest(table=table):
                expected = sorted(old.execute('SELECT * FROM "' + table + '"').fetchall(), key=str)
                if table == "source_files":
                    actual = new.execute("SELECT * FROM source_files WHERE classification='metadata_and_public_aggregates'").fetchall()
                else:
                    actual = new.execute('SELECT * FROM "' + table + '"').fetchall()
                self.assertEqual(sorted(actual, key=str), expected)

    def test_candidate_flags_and_source_counts_are_consistent(self):
        connection = self.connect()
        self.assertEqual(connection.execute("SELECT COUNT(*),COUNT(DISTINCT group_id),SUM(synthetic) FROM training_examples").fetchone(), (96, 72, 96))
        self.assertEqual(connection.execute("SELECT DISTINCT quality_status,split,label_origin FROM training_examples").fetchall(), [('candidate', 'unassigned', 'ai_synthetic_authored')])
        self.assertEqual(connection.execute("SELECT DISTINCT professional_reviewed,author_model_id FROM synthetic_example_metadata").fetchall(), [(0, 'unknown')])
        self.assertEqual(connection.execute("SELECT candidate_examples,scenario_count,accepted_examples,professional_reviewed,training_started FROM synthetic_batches").fetchone(), (96, 72, 0, 0, 0))
        for _, declared, actual in connection.execute("SELECT s.id,s.candidate_examples,COUNT(t.id) FROM source_files s LEFT JOIN training_examples t ON s.id=t.source_id GROUP BY s.id"):
            self.assertEqual(declared, actual)

    def test_exported_messages_and_metadata_match_database_and_authored_history(self):
        connection = self.connect()
        records, _ = MODULE.load_records(SOURCE)
        originals = {MODULE.BATCH_ID + ':' + r['id']: r for r in records}
        exported = [json.loads(line) for line in (self.output / "training-examples.jsonl").read_text(encoding="utf-8").splitlines()]
        stored = {row[0]: row[1:] for row in connection.execute("SELECT id,input_json,target_json,group_id,content_sha256 FROM training_examples")}
        for record in exported:
            inputs, target, group_id, digest = stored[record['id']]
            original = originals[record['id']]
            self.assertEqual(record['messages'], json.loads(inputs)['messages'] + [json.loads(target)])
            self.assertEqual(record['messages'][:-2], original['history'])
            self.assertEqual(record['messages'][-2:], [{'role': 'user', 'content': original['question']}, {'role': 'assistant', 'content': original['answer']}])
            self.assertEqual(record['metadata']['group_id'], group_id)
            self.assertEqual(record['metadata']['content_sha256'], digest)
            self.assertIs(record['metadata']['synthetic'], True)
            self.assertIs(record['metadata']['professional_reviewed'], False)
        self.assertEqual(len(exported), len(stored))

    def test_reference_source_remains_blocked_and_integrity_valid(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        MODULE.copy_reference(connection, REFERENCE)
        reference_id = connection.execute("SELECT id FROM source_files").fetchone()[0]
        with self.assertRaisesRegex(sqlite3.IntegrityError, "reference-only"):
            connection.execute("INSERT INTO training_examples VALUES ('invalid',?,'conversation','{}','{}','g',1,'test','candidate','hash','unassigned')", (reference_id,))
        with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
            connection.execute("UPDATE source_files SET classification='ai_synthetic_candidate'")
        self.assertEqual(self.connect().execute("PRAGMA integrity_check").fetchall(), [('ok',)])
        self.assertEqual(self.connect().execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_existing_output_is_not_overwritten(self):
        before = MODULE.sha256(self.output / "synthetic-training.sqlite3")
        with self.assertRaises(FileExistsError):
            MODULE.build(REFERENCE, SOURCE, self.output)
        self.assertEqual(MODULE.sha256(self.output / "synthetic-training.sqlite3"), before)

    def test_changed_reference_is_rejected_without_creating_output(self):
        altered = Path(self.temp.name) / "changed-reference"
        altered.mkdir()
        (altered / "manifest.json").write_bytes((REFERENCE / "manifest.json").read_bytes())
        (altered / "training-reference.sqlite3").write_bytes((REFERENCE / "training-reference.sqlite3").read_bytes() + b'changed')
        output = Path(self.temp.name) / "must-not-exist"
        with self.assertRaisesRegex(ValueError, "differs from verified"):
            MODULE.build(altered, SOURCE, output)
        self.assertFalse(output.exists())

    def test_all_manifest_files_and_quality_profile_match(self):
        for name, info in self.manifest['files'].items():
            path = self.output / name
            self.assertEqual(MODULE.sha256(path), info['sha256'])
            self.assertEqual(path.stat().st_size, info['bytes'])
        quality = json.loads((self.output / 'quality-report.json').read_text(encoding='utf-8'))
        self.assertEqual(quality['unique_normalized_questions'], 96)
        self.assertEqual(quality['unique_normalized_answers'], 96)
        self.assertEqual(quality['near_duplicate_candidates'], [])
        self.assertFalse(quality['clinical_quality_assessed'])


if __name__ == '__main__':
    unittest.main()
