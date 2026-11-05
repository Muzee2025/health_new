
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
