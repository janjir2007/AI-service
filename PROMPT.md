# RCOS Norm AI — Project Context

Self-hosted Mongolian road-norm assistant. A FastAPI service answers questions about Mongolian
road and building norms from three PDF books, with cited sources, using local models through
Ollama (no OpenAI / Claude / Gemini APIs, no token costs). Users write in Cyrillic, Latin or a mix.

- Repo: github.com/janjir2007/AI-service (public for now; may switch to private)
- Based on a coworker's FastAPI RAG service; I own this repo.
- Testing via Postman only (no Flutter / Node for now). Priority: Python input and output.

## How I work

- Discuss decisions with me before writing code.
- Give Terminal steps one at a time, with exact commands. I'm on a MacBook Air with 8 GB RAM.

## Setup (working)

| Part | Value |
|---|---|
| Server | `uvicorn app.main:app --reload --port 8001` (port 8000 = my capstone API) |
| Python | activate venv in each new tab: `source .venv/bin/activate` |
| Database | Docker container `norm-db` (`pgvector/pgvector:pg16`), port 5433 |
| DATABASE_URL | `postgresql://norm:normpass@localhost:5433/norm_ai` (local dev only) |
| LLM | Ollama `gemma3:4b` |
| Embeddings | Ollama `bge-m3`, `EMBEDDING_DIMENSION=1024` |
| Postman | collection imported, `base_url = http://localhost:8001` |

- Capstone containers `ocp-api` / `ocp-db` (~700 MB): stop them while testing the LLM
  (`docker stop ocp-api ocp-db`, later `docker start ocp-db ocp-api`).
- Docker Desktop memory limit: lowered from 4 GB to 2 GB.

## Done

- Small-talk routing (greeting / thanks / bye / identity / capabilities) with template replies,
  answered without database or LLM. Replies in the user's script (Latin in → Latin out);
  `answer_cyrillic` is always returned too. 54 tests pass.
- `mybook.pdf` (БНбД) ingested: 661 pages, 549 sections, 158 tables, 1373 chunks.
- `8325.pdf` and `8326.pdf` (cost-estimate norms) not ingested yet.

## Current problem (next step)

Question: «II ангиллын замын хөдөлгөөний зурвасын өргөн хэд вэ?»

- Search found the right page: p. 139, section 3.2, lane width 3.5–3.75 m.
- But gemma3 answered from p. 447 (road boundary strip, 2.4–3.6 m), which is wrong. Took 1 min 27 s.
- Likely cause: the prompt (8 chunks × up to 6000 chars) is longer than Ollama's default
  context window, so the start (instructions + best chunk) gets cut off.
- Proposed fix, **not yet approved**: send the top 4 chunks, ~1500 chars each, and set
  `num_ctx` 8192 via a new `.env` setting.
- Open question: does "II ангилал" match the book's classes ("гол зам",
  "гол замаас дээшхи ангилал")? Affects whether 3.5–3.75 m is the right answer.

## Known issues / roadmap

- [ ] Latin input robustness: spelling variants, shortcuts, typos, mixed English
      (e.g. "ugluuni mend" not recognized). Plan: collect real messages, fuzzy matching,
      then the ByT5 normalizer.
- [ ] `app/db.py` registers the vector type before the extension exists; a fresh database
      needs `CREATE EXTENSION vector;` by hand first.
- [ ] Chunking labels text with the last section heading on its page.
- [ ] Heading-only chunks pollute search results.
- [ ] Switch LLM to the Mongolian Gemma 3 4B model (GGUF in Ollama).
- [ ] Cyrillic / Latin / mixed evaluation set with known correct answers and pages.
