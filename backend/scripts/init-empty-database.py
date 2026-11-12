"""Create a brand-new SQLite schema at an explicitly selected nonexistent path.

Existing files, including empty files, are never opened or overwritten.
Failure retains the newly reserved file for operator inspection.
"""
import argparse
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path, help="New SQLite file in an existing directory")
    args = parser.parse_args()
    requested = args.database.expanduser().absolute()
    if requested.is_symlink() or requested.exists():
        parser.exit(2, "Initialization refused: the requested path already exists\n")
    if not requested.parent.is_dir():
        parser.exit(2, "Initialization refused: the parent directory must already exist\n")
    try:
        # O_EXCL also protects against a file/symlink appearing after the checks.
        with requested.open("xb"):
            pass
    except FileExistsError:
        parser.exit(2, "Initialization refused: the requested path already exists\n")
    except OSError:
        parser.exit(2, "Unable to reserve the new database file; check directory permissions\n")
    try:
        import dotenv
        dotenv.load_dotenv = lambda *args, **kwargs: False
        os.environ["PYTHON_DOTENV_DISABLED"] = "1"
        os.environ["DATABASE_URL"] = "sqlite:///" + requested.resolve().as_posix()
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from app import models
        from app.database import engine
        if engine.url.get_backend_name() != "sqlite" or Path(engine.url.database).resolve() != requested.resolve():
            raise RuntimeError("The configured engine does not target the reserved file")
        models.Base.metadata.create_all(bind=engine)
        engine.dispose()
    except Exception:
        parser.exit(1, "Schema initialization failed; the newly reserved file was retained. Check the runtime and schema before retrying with another new path.\n")
    print("Created a new empty SQLite schema; no existing database was opened")


if __name__ == "__main__":
    main()
