# RCOS Norm AI

Self-hosted Mongolian road-norm assistant. A FastAPI service answers questions about Mongolian
road and building norms from three PDF books, with cited sources, using local models through
Ollama (no OpenAI, Claude or Gemini API, no token costs). Users can write in Cyrillic, Latin or a
mix of both, and get small-talk replies in their own script.

Based on the RAG service built by our coworker (ingest, hybrid search, grounded answers). This
repo adds input routing, script handling and small talk; see "Changes" below.

## How a message is handled

```
message ─► detect script (cyrillic / latin / mixed)
        ─► normalize Latin → Cyrillic
        ─► route:
             greeting / thanks / bye / who are you / what can you do ─► template reply (no DB, no LLM)
             road question ─► RAG over the books ─► grounded answer + sources
             unknown ─► RAG; nothing relevant found ─► polite "roads only" reply
        ─► reply in the user's script (Latin in → Latin out)
```

## Quick start: small talk only (no database needed)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Then in Postman: **Import → `postman/rcos-norm-ai.postman_collection.json`** and run folder
**2. Small talk**. Or with curl:

```bash
curl -s localhost:8000/api/v1/chat -H 'Content-Type: application/json' -d '{"message":"Sain bnu?"}'
```

```json
{
  "answer": "Sain baina uu! Bi RCOS Norm AI — avto zam, barilgiin normiin tuslah. Tand yuugaar tuslah ve?",
  "answer_cyrillic": "Сайн байна уу! Би RCOS Norm AI — авто зам, барилгын нормын туслах. Танд юугаар туслах вэ?",
  "intent": "greeting",
  "input_script": "latin",
  "reply_script": "latin",
  "normalized_message": "сайн байна уу?",
  "sources": []
}
```

## Full setup: road questions

Requirements: Python 3.9+ (3.11 recommended), PostgreSQL with the **pgvector** extension, and
[Ollama](https://ollama.com).

1. Put the three books in `data/`: `mybook.pdf` (БНбД), `8325.pdf`, `8326.pdf`.
   PDFs are git-ignored; never commit them.
2. Set `DATABASE_URL` in `.env`.
3. Pull models: `bash scripts/pull_ollama_models.sh`
4. Create tables: `python scripts/run_migrations.py`
   (`EMBEDDING_DIMENSION` must match the embedding model *before* this step.)
5. Ingest the books: `python -m app.ingest --all`
6. Run the API and use Postman folders **3** and **4**.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service, database and Ollama status |
| POST | `/api/v1/chat` | Chat: small talk or RAG answer with sources |
| POST | `/api/v1/rag/search` | Raw hybrid search results |
| GET | `/api/v1/documents` | Ingested books |
| GET | `/api/v1/standards-pdf?file=8326.pdf` | Download a source book |

New `/chat` response fields: `intent`, `input_script`, `reply_script`, `normalized_message`,
`answer_cyrillic`. All original fields are unchanged.

## Tests

```bash
pytest -q
```

## Changes from the original service

- `app/services/script_utils.py`: script detection, Latin→Cyrillic normalizer (word dictionary +
  letter rules), Cyrillic→Latin output.
- `app/services/intent_router.py`: small-talk intents and replies, greeting + question handling,
  off-topic reply.
- `app/api/routes/chat.py`: routes before any database call; replies in the user's script.
- Fix: `standards_pdf.py` crashed on Python 3.9 (`str | None` without `from __future__`).
- Postman collection in `postman/`; new tests for routing and scripts.

## Roadmap

- [x] Switch embeddings to `bge-m3` (multilingual, 1024 dims; migration + re-ingest)
- [x] Switch LLM to Gemma 4 E2B (`gemma4:e2b-it-qat`) with facts mode
- [ ] Fix chunking: text is labeled with the last section heading on its page
- [ ] Replace the rule-based normalizer with the ByT5 mongolian-translit model
- [ ] Cyrillic / Latin / mixed evaluation set for road answers
- [ ] Greeting spelling variants (ugluuni mend, udrin mend), looser "mend" matching
