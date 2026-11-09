from __future__ import annotations

from psycopg2.extensions import connection as PgConnection


class DocumentRepository:
    def find_by_hash(self, conn: PgConnection, file_hash: str) -> dict | None:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, file_path, file_hash, total_pages, word_count, created_at
                FROM ai_documents WHERE file_hash = %s
                """,
                (file_hash,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "name": row[1],
                "file_path": row[2],
                "file_hash": row[3],
                "total_pages": row[4],
                "word_count": row[5],
                "created_at": row[6],
            }

    def create(
        self,
        conn: PgConnection,
        name: str,
        file_path: str,
        file_hash: str,
        total_pages: int,
        word_count: int,
    ) -> int:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ai_documents (name, file_path, file_hash, total_pages, word_count)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (name, file_path, file_hash, total_pages, word_count),
            )
            return int(cur.fetchone()[0])

    def delete_cascade(self, conn: PgConnection, document_id: int) -> None:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ai_documents WHERE id = %s", (document_id,))

    def insert_pages(self, conn: PgConnection, document_id: int, pages: list[tuple[int, str]]) -> None:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO ai_document_pages (document_id, page_number, text)
                VALUES (%s, %s, %s)
                ON CONFLICT (document_id, page_number) DO UPDATE SET text = EXCLUDED.text
                """,
                [(document_id, p, t) for p, t in pages],
            )

    def insert_tables(
        self,
        conn: PgConnection,
        document_id: int,
        rows: list[tuple[int, str | None, str | None, str | None, str]],
    ) -> None:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ai_document_tables WHERE document_id = %s", (document_id,))
            cur.executemany(
                """
                INSERT INTO ai_document_tables
                    (document_id, page_number, chapter, section, title, content)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                [(document_id, *r) for r in rows],
            )
