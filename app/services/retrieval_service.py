from __future__ import annotations

import logging
import re

from psycopg2.extensions import connection as PgConnection
from pgvector import Vector

from app.config import Settings, get_settings
from app.services.book_catalog import preferred_filenames
from app.services.embedding_service import get_embedding_provider
from app.services.query_enhance import enhance_search_query

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"[\w\u0400-\u04FF]+", re.UNICODE)


def _or_tsquery(query: str) -> str:
    parts = []
    for raw in _TOKEN.findall(query.lower()):
        if len(raw) < 3:
            continue
        safe = re.sub(r"[!&|():*']", "", raw)
        if safe:
            parts.append(safe)
    return " | ".join(parts) if parts else ""


def _like_pattern(query: str) -> str:
    parts = [p for p in _TOKEN.findall(query) if len(p) > 1]
    if not parts:
        return f"%{query.strip()}%"
    return "%" + "%".join(parts) + "%"


def _has_phrase(content: str, query: str) -> bool:
    if not content or not query.strip():
        return False
    text = re.sub(r"\s+", " ", content.lower())
    q = re.sub(r"\s+", " ", query.lower()).strip()
    if q and q in text:
        return True
    tokens = [t for t in _TOKEN.findall(q) if len(t) > 2]
    return bool(tokens) and all(t in text for t in tokens)


class RetrievalService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.embedder = get_embedding_provider(self.settings)

    def search(
        self,
        conn: PgConnection,
        query: str,
        top_k: int | None = None,
        filenames: list[str] | None = None,
    ) -> list[dict]:
        top_k = top_k or self.settings.rag_top_k
        raw_query = query.strip()
        query = enhance_search_query(raw_query)
        if not query:
            return []

        preferred = preferred_filenames(raw_query, filenames)
        try:
            query_vector = self.embedder.embed_texts([query])[0]
        except Exception as exc:
            logger.error("Failed to embed query: %s", exc)
            raise

        pool = max(top_k * 4, 16)
        hits = self._search_sql(
            conn,
            query=query,
            raw_query=raw_query,
            query_vector=query_vector,
            limit=pool,
            filenames=preferred,
        )
        useful = [
            h
            for h in hits
            if h["score"] >= 0.12 or _has_phrase(h.get("content") or "", raw_query)
        ]
        if preferred and not useful:
            logger.info("Preferred books %s had no useful hits; searching all PDFs", preferred)
            hits = self._search_sql(
                conn,
                query=query,
                raw_query=raw_query,
                query_vector=query_vector,
                limit=pool,
                filenames=None,
            )
        elif preferred:
            hits = useful

        return hits[:top_k]

    def _search_sql(
        self,
        conn: PgConnection,
        *,
        query: str,
        raw_query: str,
        query_vector: list[float],
        limit: int,
        filenames: list[str] | None,
    ) -> list[dict]:
        vw = self.settings.rag_vector_weight
        kw = self.settings.rag_keyword_weight
        or_q = _or_tsquery(raw_query)
        like = _like_pattern(raw_query)
        file_filter = "AND d.name = ANY(%s)" if filenames else ""

        sql = f"""
        WITH ranked AS (
            SELECT
                c.content,
                c.page_number AS page,
                c.chapter,
                c.section,
                c.section_title AS title,
                c.content_type,
                d.name AS filename,
                CASE
                    WHEN c.embedding IS NULL THEN 0.0
                    ELSE 1 - (c.embedding <=> %s::vector)
                END AS vector_score,
                GREATEST(
                    COALESCE(ts_rank(c.search_vector, plainto_tsquery('simple', %s)), 0.0),
                    COALESCE(
                        CASE
                            WHEN %s = '' THEN 0.0
                            ELSE ts_rank(c.search_vector, to_tsquery('simple', %s))
                        END,
                        0.0
                    )
                ) AS keyword_score,
                CASE
                    WHEN regexp_replace(c.content, '\\s+', ' ', 'g') ILIKE %s THEN 3.0
                    WHEN c.content ILIKE %s THEN 2.0
                    ELSE 0.0
                END AS phrase_score
            FROM ai_document_chunks c
            JOIN ai_documents d ON d.id = c.document_id
            WHERE (c.search_vector IS NOT NULL OR c.embedding IS NOT NULL)
              {file_filter}
        )
        SELECT
            content, page, chapter, section, title, content_type, filename,
            (vector_score * %s + keyword_score * %s + phrase_score) AS score,
            vector_score,
            keyword_score
        FROM ranked
        ORDER BY score DESC
        LIMIT %s
        """
        vec = Vector(query_vector)
        params: list = [vec, query, or_q, or_q, like, like]
        if filenames:
            params.append(list(filenames))
        params.extend([vw, kw, limit])

        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

        return [
            {
                "content": r[0],
                "page": r[1],
                "chapter": r[2],
                "section": r[3],
                "title": r[4],
                "content_type": r[5],
                "filename": r[6] or "",
                "score": float(r[7]),
                "vector_score": float(r[8]),
                "keyword_score": float(r[9]),
            }
            for r in rows
        ]
