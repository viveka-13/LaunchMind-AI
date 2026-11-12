import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from agent.memory import init_database

@pytest.fixture(scope="session", autouse=True)
def setup_test_db(tmp_path_factory):
    """Isolate tests from production database by pointing DB_PATH to a temporary sqlite file."""
    test_db_dir = tmp_path_factory.mktemp("test_db")
    test_db_path = str(test_db_dir / "test_startup_history.db")
    os.environ["DB_PATH"] = test_db_path
    init_database()
    yield test_db_path
