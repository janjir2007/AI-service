from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2.extensions import connection as PgConnection
from pgvector.psycopg2 import register_vector

from app.config import get_settings


def _register_vector(conn: PgConnection) -> None:
    """Register the pgvector type; on a brand-new database create the extension first."""
    try:
        register_vector(conn)
    except psycopg2.ProgrammingError:  # "vector" type missing -> fresh database
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()
        register_vector(conn)


@contextmanager
def get_connection() -> Iterator[PgConnection]:
    settings = get_settings()
    conn = psycopg2.connect(settings.database_url)
    _register_vector(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
