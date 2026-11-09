# AI schema migrations

Run in order via:

```bash
cd ai-service && source .venv/bin/activate
python scripts/run_migrations.py
```

**Do not** copy SQL into `psql` as-is. File `003_create_ai_chunks.sql` contains `{{EMBEDDING_DIMENSION}}`; the runner replaces it with `768` (or your `.env` value).

Manual equivalent for `003` when `EMBEDDING_DIMENSION=768`:

```sql
CREATE TABLE IF NOT EXISTS ai_document_chunks (
    ...
    embedding vector(768),
    ...
);
```

Apply `001` → `005` in filename order. Requires `CREATE EXTENSION vector;` (included in `001`).
