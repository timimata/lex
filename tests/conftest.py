import os
import uuid
from collections.abc import Iterator

import psycopg
import pytest

from lex.store import db

# Set by the first failed connection, so the other store tests skip at once instead of each
# waiting for its own timeout.
_no_database: list[str] = []


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    """A store connection whose tables live in a throwaway schema. Skipped without a database,
    except in CI, where LEX_REQUIRE_DB makes a missing database a failure."""
    if _no_database and not os.environ.get("LEX_REQUIRE_DB"):
        pytest.skip(_no_database[0])
    try:
        connection = db.connect(timeout=3)
    except psycopg.OperationalError:
        if os.environ.get("LEX_REQUIRE_DB"):
            raise
        _no_database.append("no database; start one with `docker compose up -d`")
        pytest.skip(_no_database[0])
    connection.autocommit = True
    db.create_extensions(connection)  # in public, so dropping the test schema keeps them
    schema = f"test_{uuid.uuid4().hex[:8]}"
    connection.execute(f"CREATE SCHEMA {schema}")
    connection.execute(f"SET search_path TO {schema}, public")
    db.create_schema(connection)
    try:
        yield connection
    finally:
        connection.execute(f"DROP SCHEMA {schema} CASCADE")
        connection.close()
