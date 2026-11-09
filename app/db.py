from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2.extensions import connection as PgConnection
from pgvector.psycopg2 import register_vector

from app.config import get_settings


@contextmanager
def get_connection() -> Iterator[PgConnection]:
    settings = get_settings()
    conn = psycopg2.connect(settings.database_url)
    register_vector(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
