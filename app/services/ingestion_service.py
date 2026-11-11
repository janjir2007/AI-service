from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.chunking_service import build_chunks_from_pages
from app.services.embedding_service import get_embedding_provider
from app.services.pdf_service import extract_pdf_pages, plain_text

logger = logging.getLogger(__name__)

def _embed_batch_size() -> int:
    from app.config import get_settings

    return max(4, get_settings().ingest_embed_batch_size)


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class IngestionService:
    def __init__(self) -> None:
        self.doc_repo = DocumentRepository()
        self.chunk_repo = ChunkRepository()
        self.embedder = get_embedding_provider()

    def run(self, pdf_path: str, force: bool = False) -> dict:
        path = Path(pdf_path)
        if not path.is_file():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        file_hash = file_sha256(str(path))
        name = path.name

        from app.db import get_connection

        with get_connection() as conn:
            existing = self.doc_repo.find_by_hash(conn, file_hash)
            if existing and not force:
                raise RuntimeError(
                    f"Document already ingested (id={existing['id']}, hash={file_hash}). "
                    "Use --force to re-ingest."
                )
            if existing and force:
                logger.info("Re-ingesting document id=%s", existing["id"])
                self.doc_repo.delete_cascade(conn, existing["id"])

            from app.config import get_settings

            settings = get_settings()
            logger.info(
                "Extracting PDF: %s (tables=%s)",
                pdf_path,
                settings.ingest_extract_tables,
            )
            page_extracts = extract_pdf_pages(
                str(path), extract_tables=settings.ingest_extract_tables
            )
            total_pages = len(page_extracts)
            word_count = sum(len(p.text.split()) for p in page_extracts)

            document_id = self.doc_repo.create(
                conn,
                name=name,
                file_path=str(path.resolve()),
                file_hash=file_hash,
                total_pages=total_pages,
                word_count=word_count,
            )

            page_rows = [(p.page_number, plain_text(p.text)) for p in page_extracts]
            self.doc_repo.insert_pages(conn, document_id, page_rows)

            page_tuples = [
                (p.page_number, p.text, p.tables, p.chapter, p.chapter_title) for p in page_extracts
            ]
            chunks, _, _ = build_chunks_from_pages(page_tuples, strict_headings=True)

            sections_detected = len(
                {
                    (c.section, c.section_title)
                    for c in chunks
                    if c.section and c.section_title
                }
            )

            table_rows: list[tuple[int, str | None, str | None, str | None, str]] = []
            tables_detected = 0
            for c in chunks:
                if c.content_type == "table":
                    tables_detected += 1
                    title = c.content.split("\n", 1)[0]
                    table_rows.append((c.page_number, c.chapter, c.section, title, c.content))
            self.doc_repo.insert_tables(conn, document_id, table_rows)

            batch_size = _embed_batch_size()
            logger.info("Creating embeddings for %s chunks (batch=%s)", len(chunks), batch_size)
            self.chunk_repo.delete_for_document(conn, document_id)
            conn.commit()

            embeddings_created = 0
            for start in range(0, len(chunks), batch_size):
                batch = chunks[start : start + batch_size]
                texts = [c.content for c in batch]
                try:
                    vectors = self.embedder.embed_texts(texts)
                except Exception as exc:
                    logger.error("Embedding batch failed at %s: %s", start, exc)
                    raise
                batch_payloads: list[dict] = []
                for c, vec in zip(batch, vectors):
                    batch_payloads.append(
                        {
                            "page_number": c.page_number,
                            "chapter": c.chapter,
                            "section": c.section,
                            "section_title": c.section_title,
                            "chunk_index": c.chunk_index,
                            "content": c.content,
                            "content_type": c.content_type,
                            "token_estimate": c.token_estimate,
                            "embedding": vec,
                        }
                    )
                self.chunk_repo.insert_chunks(conn, document_id, batch_payloads)
                conn.commit()
                embeddings_created += len(batch_payloads)
                logger.info(
                    "Stored %s/%s chunks in DB",
                    min(start + batch_size, len(chunks)),
                    len(chunks),
                )

            self.chunk_repo.ensure_vector_index(conn)

            stats = {
                "document": name,
                "document_id": document_id,
                "pages": total_pages,
                "words": word_count,
                "sections_detected": sections_detected,
                "chunks_created": len(chunks),
                "tables_detected": tables_detected,
                "embeddings_created": embeddings_created,
            }
            return stats
