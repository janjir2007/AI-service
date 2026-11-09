-- Do NOT paste this file raw into psql — {{EMBEDDING_DIMENSION}} must become a number (768 for nomic-embed-text).
-- Use: python scripts/run_migrations.py
-- Manual psql: embedding vector(768)  (must match EMBEDDING_DIMENSION in .env)
CREATE TABLE IF NOT EXISTS ai_document_chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES ai_documents (id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    chapter TEXT,
    section TEXT,
    section_title TEXT,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'text'
        CHECK (content_type IN ('text', 'table', 'formula')),
    token_estimate INTEGER NOT NULL DEFAULT 0,
    search_vector TSVECTOR,
    embedding vector({{EMBEDDING_DIMENSION}}),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_ai_document_chunks_doc
    ON ai_document_chunks (document_id);

CREATE INDEX IF NOT EXISTS idx_ai_document_chunks_section
    ON ai_document_chunks (document_id, section);

CREATE INDEX IF NOT EXISTS idx_ai_document_chunks_fts
    ON ai_document_chunks USING GIN (search_vector);
