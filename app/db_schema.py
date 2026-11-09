"""Verify ai_* tables exist (migrations + ingest)."""
from __future__ import annotations

from psycopg2.extensions import connection as PgConnection

REQUIRED_TABLES = (
    "ai_documents",
    "ai_document_pages",
    "ai_document_chunks",
)


def missing_tables(conn: PgConnection) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ANY(%s)
            """,
            (list(REQUIRED_TABLES),),
        )
        found = {row[0] for row in cur.fetchall()}
    return [t for t in REQUIRED_TABLES if t not in found]


def chunk_count(conn: PgConnection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)::bigint
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'ai_document_chunks'
            """
        )
        if cur.fetchone()[0] == 0:
            return 0
        cur.execute("SELECT COUNT(*)::bigint FROM ai_document_chunks")
        return int(cur.fetchone()[0])


def document_inventory(conn: PgConnection) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                d.id,
                d.name,
                d.file_path,
                d.total_pages,
                d.word_count,
                COUNT(c.id)::int AS chunks,
                COUNT(c.embedding)::int AS embeddings
            FROM ai_documents d
            LEFT JOIN ai_document_chunks c ON c.document_id = d.id
            GROUP BY d.id, d.name, d.file_path, d.total_pages, d.word_count
            ORDER BY d.id
            """
        )
        rows = cur.fetchall()
    from app.services.book_catalog import book_info

    out = []
    for row in rows:
        meta = book_info(row[1], row[2])
        out.append(
            {
                "id": row[0],
                "filename": meta["filename"],
                "book": meta["book"],
                "code": meta["code"],
                "file_path": row[2],
                "pages": row[3],
                "words": row[4],
                "chunks": row[5],
                "embeddings": row[6],
            }
        )
    return out


def schema_status(conn: PgConnection) -> dict:
    missing = missing_tables(conn)
    chunks = chunk_count(conn) if "ai_document_chunks" not in missing else 0
    docs: list[dict] = []
    if "ai_documents" not in missing:
        try:
            docs = document_inventory(conn)
        except Exception:
            docs = []
    ok = not missing and chunks > 0
    hint = None
    if missing:
        hint = (
            "Run: cd ai-service && source .venv/bin/activate && "
            "python scripts/run_migrations.py && python -m app.ingest"
        )
    elif chunks == 0:
        hint = "Tables exist but empty. Run: python -m app.ingest (set PDF_PATH in .env)"
    filenames = {d.get("filename") for d in docs}
    if docs and not {"8325.pdf", "8326.pdf"} <= filenames:
        hint = (
            (hint + " ") if hint else ""
        ) + "8325.pdf / 8326.pdf are not ingested as separate documents. Run: python -m app.ingest --all"
    return {
        "schema_ok": ok,
        "missing_tables": missing,
        "chunk_count": chunks,
        "document_count": len(docs),
        "documents": docs,
        "hint": hint,
    }
