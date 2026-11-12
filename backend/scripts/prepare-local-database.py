"""Prepare a new private SQLite deployment; existing databases remain read-only.

No destructive legacy init script, app startup import, automatic assignment or
credential output. Refuse existing output paths and incompatible existing columns.
"""
import argparse
import hashlib
import json
import os
import re
import secrets
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def private_directory(target):
    target.mkdir(exist_ok=False)
    if os.name == 'nt':
        identity = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'], capture_output=True, check=True, text=True)
        sid = re.search(r'S-1-\d+(?:-\d+)+', identity.stdout)
        if not sid:
            raise RuntimeError('Unable to determine private directory owner')
        result = subprocess.run(['icacls', str(target), '/inheritance:r', '/grant:r',
                                 f'*{sid.group()}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'], capture_output=True)
        if result.returncode:
            raise RuntimeError('Unable to restrict the new deployment directory')
    else:
        target.chmod(0o700)


def open_existing(path, mode='ro'):
    return sqlite3.connect(path.as_uri() + '?mode=' + mode, uri=True)


def copy_database(source, destination):
    with destination.open('xb'):
        pass
    with open_existing(source) as old, open_existing(destination, 'rw') as new:
        old.backup(new)
        if new.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity check failed')


def table_fingerprints(connection):
    result = {}
    tables = sorted(row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
    for name in tables:
        quoted = '"' + name.replace('"', '""') + '"'
        rows = []
        for row in connection.execute(f'SELECT * FROM {quoted}'):
            rows.append(hashlib.sha256(repr(tuple(row)).encode('utf8')).digest())
        result[name] = hashlib.sha256(b''.join(sorted(rows))).hexdigest()
    return result


def prepare(output, source=None):
    output = output.expanduser().absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir() or output.parent.is_symlink():
        raise ValueError('Use a nonexistent deployment directory under an existing regular parent')
    if source is not None:
        source = source.expanduser().resolve(strict=True)
        if not source.is_file():
            raise ValueError('Use an existing SQLite source file')
    # Inspect model metadata only. No existing .env discovery or application import.
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    os.environ['PYTHON_DOTENV_DISABLED'] = '1'
    sys.path.insert(0, str(BACKEND))
    from sqlalchemy import create_engine, inspect

    from app.models import Base
    private_directory(output)
    active = output / 'health.db'
    backup = output / 'source-backup.db'
    before = {}
    if source:
        copy_database(source, backup)
        copy_database(backup, active)
        with open_existing(backup) as db:
            before = table_fingerprints(db)
    else:
        with active.open('xb'):
            pass
    engine = create_engine('sqlite:///' + active.as_posix())
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    # create_all only creates absent tables; never pretend it migrates columns.
    for name, table in Base.metadata.tables.items():
        if name in existing:
            columns = {column['name'] for column in inspector.get_columns(name)}
            if {column.name for column in table.columns} - columns:
                engine.dispose()
                raise ValueError('Existing schema has missing columns; review a versioned migration before deployment')
    Base.metadata.create_all(engine)
    engine.dispose()
    with open_existing(active) as db:
        after = table_fingerprints(db)
        if any(after.get(name) != fingerprint for name, fingerprint in before.items()):
            raise ValueError('Copy verification failed; source database was not modified')
        if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('Prepared SQLite integrity check failed')
        assignment_rows = db.execute('SELECT COUNT(*) FROM teacher_student_assignments').fetchone()[0]
    # A login deployment does not inherit provider credentials from an old .env.
    values = dict(DATABASE_URL='sqlite:///' + active.as_posix(), JWT_SECRET_KEY=secrets.token_urlsafe(48),
                  ACCESS_TOKEN_EXPIRE_MINUTES='30', CORS_ALLOWED_ORIGINS='http://localhost:5173,http://127.0.0.1:5173',
                  RAG_ENABLED='false', RAG_ALLOW_MODEL_DOWNLOAD='false')
    envfile = output / '.env'
    with envfile.open('x', encoding='utf8', newline='\n') as stream:
        for key,value in sorted(values.items()):
            stream.write(f'{key}={json.dumps(value,ensure_ascii=False)}\n')
    if os.name != 'nt':
        envfile.chmod(0o600)
    report = {'schemaVersion':1, 'status':'prepared', 'database':'sqlite', 'expectedTables':len(Base.metadata.tables),
              'copiedExistingTables':len(before), 'newTables':sorted(set(Base.metadata.tables)-existing),
              'existingTableDataPreserved':True, 'sourceChanged':False, 'assignmentRowsPreserved':assignment_rows,
              'createdAssignments':0, 'settingsFile':'.env', 'backupCreated':source is not None}
    with (output/'deployment.json').open('x',encoding='utf8') as stream:
        json.dump(report,stream,indent=2)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--source',type=Path)
    source.add_argument('--empty',action='store_true')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    try:
        report=prepare(args.output,args.source)
    except Exception:
        parser.exit(2,'Local database preparation failed; source files are unchanged. Any newly created output was retained for inspection. Review schema, runtime and directory permissions.\n')
    print(json.dumps(report))


if __name__=='__main__':
    main()
