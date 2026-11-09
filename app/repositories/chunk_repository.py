from __future__ import annotations

from psycopg2.extensions import connection as PgConnection
from pgvector import Vector


class ChunkRepository:
    def delete_for_document(self, conn: PgConnection, document_id: int) -> None:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ai_document_chunks WHERE document_id = %s", (document_id,))

    def insert_chunks(
        self,
        conn: PgConnection,
        document_id: int,
        rows: list[dict],
    ) -> None:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO ai_document_chunks (
                    document_id, page_number, chapter, section, section_title,
                    chunk_index, content, content_type, token_estimate,
                    search_vector, embedding
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    to_tsvector('simple', %s),
                    %s
                )
                ON CONFLICT (document_id, chunk_index) DO UPDATE SET
                    page_number = EXCLUDED.page_number,
                    chapter = EXCLUDED.chapter,
                    section = EXCLUDED.section,
                    section_title = EXCLUDED.section_title,
                    content = EXCLUDED.content,
                    content_type = EXCLUDED.content_type,
                    token_estimate = EXCLUDED.token_estimate,
                    search_vector = EXCLUDED.search_vector,
                    embedding = EXCLUDED.embedding
                """,
                [
                    (
                        document_id,
                        r["page_number"],
                        r.get("chapter"),
                        r.get("section"),
                        r.get("section_title"),
                        r["chunk_index"],
                        r["content"],
                        r["content_type"],
                        r["token_estimate"],
                        r["content"],
                        Vector(r["embedding"]) if r.get("embedding") is not None else None,
                    )
                    for r in rows
                ],
            )

    def ensure_vector_index(self, conn: PgConnection) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM pg_indexes
                WHERE indexname = 'idx_ai_document_chunks_embedding'
                """
            )
            if cur.fetchone():
                return
            cur.execute("SELECT COUNT(*) FROM ai_document_chunks WHERE embedding IS NOT NULL")
            count = cur.fetchone()[0]
            if count < 100:
                return
            cur.execute(
                """
                CREATE INDEX idx_ai_document_chunks_embedding
                ON ai_document_chunks
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
                """
            )
