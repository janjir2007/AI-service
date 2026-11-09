#!/usr/bin/env python3
"""Apply SQL migrations in order."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.db import get_connection


def _ensure_pgvector(conn) -> None:
    with conn.cursor() as cur:
        try:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        except Exception as exc:
            print(
                "ERROR: PostgreSQL pgvector extension is required.\n"
                "  Ubuntu/Debian: install postgresql-*-pgvector, then as superuser:\n"
                "    CREATE EXTENSION vector;\n"
                f"  Details: {exc}",
                file=sys.stderr,
            )
            raise


def main() -> int:
    settings = get_settings()
    print(f"DATABASE_URL host/db: ...@{_redact_url(settings.database_url)}")
    migrations_dir = ROOT / "migrations"
    files = sorted(migrations_dir.glob("*.sql"))
    if not files:
        print("No migrations found.")
        return 1

    with get_connection() as conn:
        _ensure_pgvector(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_schema_migrations (
                    id SERIAL PRIMARY KEY,
                    filename TEXT NOT NULL UNIQUE,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            for path in files:
                cur.execute(
                    "SELECT 1 FROM ai_schema_migrations WHERE filename = %s",
                    (path.name,),
                )
                if cur.fetchone():
                    print(f"skip {path.name}")
                    continue
                sql = path.read_text(encoding="utf-8")
                if "{{EMBEDDING_DIMENSION}}" in sql:
                    sql = sql.replace(
                        "{{EMBEDDING_DIMENSION}}",
                        str(settings.embedding_dimension),
                    )
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO ai_schema_migrations (filename) VALUES (%s)",
                    (path.name,),
                )
                print(f"applied {path.name}")
    with get_connection() as conn:
        from app.db_schema import missing_tables

        missing = missing_tables(conn)
        if missing:
            print(f"WARNING: still missing tables: {', '.join(missing)}", file=sys.stderr)
            return 1
    print("Migrations complete.")
    return 0


def _redact_url(url: str) -> str:
    if "@" in url:
        return url.split("@", 1)[1]
    return url


if __name__ == "__main__":
    raise SystemExit(main())
