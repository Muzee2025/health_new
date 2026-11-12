"""Reject unsafe test collection before application imports can load local data."""
import os

import pytest

if os.environ.get("HEALTH_TEST_ISOLATED") != "1":
    raise pytest.UsageError(
        "Run backend tests with: python scripts/run-backend-baseline.py. "
        "It isolates SQLite/files, disables dotenv/RAG and blocks Python networking."
    )
