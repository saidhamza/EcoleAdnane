import os
import tempfile
import pytest
from models.database import init_db


@pytest.fixture(autouse=True, scope="session")
def isolate_database():
    """Ensure all test runs use an isolated temporary database, protecting the production database from mutation or pollution."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_db_path = f.name

    os.environ["DATABASE_PATH"] = temp_db_path
    init_db(temp_db_path)

    yield temp_db_path

    if os.path.exists(temp_db_path):
        try:
            os.remove(temp_db_path)
        except Exception:
            pass
