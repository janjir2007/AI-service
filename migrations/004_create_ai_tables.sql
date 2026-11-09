CREATE TABLE IF NOT EXISTS ai_document_tables (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES ai_documents (id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    chapter TEXT,
    section TEXT,
    title TEXT,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_document_tables_doc_page
    ON ai_document_tables (document_id, page_number);
