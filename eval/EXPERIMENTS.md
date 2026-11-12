# Experiments

| Date | Change | Score | Keep? | Notes |
|---|---|---|---|---|
| 2026-11-09 | Baseline: prompt-size fix (4 chunks, num_ctx 8192) | 8/21 | yes | |
| 2026-11-11 | New ingestion: clean tables, correct sections | 13/21 | yes | regraded with fixed grader |
| 2026-11-11 | LLM_CONTEXT_CHUNKS 4 → 5 | 10/21 | no | lost q07, q10, q15; tables not fixed |
| 2026-11-11 | Number check (loose) + no filler rules + Rule 1 removed | 13 ✓ / 1 ~ / 7 ✗ | yes | Rule 1 dropped good questions (relevance check broken by «хурд»); fillers produced lucky passes |
| 2026-11-11 | Strict number check (line + 2 question words) | 13 ✓ / 2 ~ / 6 ✗ | yes | q20 fixed; q19 wrongly blocked |
| 2026-11-11 | Fixes: q11 accepts 185 (p.425/464), ү/у folding in check | 15 ✓ / 1 ~ / 5 ✗ | yes | stable over repeated runs |
| 2026-11-11 | Tables one fact per line (re-ingest: 2613 chunks, 1284 table chunks) | 13 ✓ / 1 ~ / 7 ✗ | no | q03 only a lucky pass; q15, q16, q19 lost: big tables split up, crowding search |
| 2026-11-11 | Facts mode (JSON facts + checks, overview/yes-no path, exact-match priority, row check) | 13 ✓ / 3 ~ / 5 ✗ | ANSWER_MODE=facts (default still text) | same ✗ as text, q04/q19 now honest; q08 book conflict; q03/q05/q09/q14 table reading |
| 2026-11-12 | LLM gemma3:4b → gemma4:e2b-it-qat (facts mode, think off) | 15 ✓ / 1 ~ / 5 ✗ | yes (local .env) | +q03 q08 q19 (better table reading), -q02 (prose 3.5-3.75 vs Table 3.2), -q04 (one value instead of column) |
| 2026-12-12 | Table lookup (row+column from table chunks, before LLM; reads search results before same-page removal) | 16 ✓ / 1 ~ / 4 ✗ | yes | q02 fixed; q04 still ✗; found: same-page removal drops tables from LLM context |
| 2026-11-12 | Table lookup (row+column from table chunks, before LLM; reads search results before same-page removal) | 16 ✓ / 1 ~ / 4 ✗ | yes | q02 fixed; q04 still ✗; found: same-page removal drops tables from LLM context |
| 2026-11-12 | Table lookup (row+column from table chunks, before LLM; reads search results before same-page removal) | 16 ✓ / 1 ~ / 4 ✗ | yes | q02 fixed; q04 still ✗; found: same-page removal drops tables from LLM context |
| 2026-11-12 | Latin letter rules (ii→ий, vowel+i→й), эгнээ synonym, answer-type check (зай fixed), number words; q22/q23 added. Reverted: хурд rule change and хурдны авто зам synonym (both lost Table 3.2 for q01/q17) | 17 ✓ / 2 ~ / 4 ✗ (of 23) | yes | lesson: search-word tweaks change results for other questions; table lookup depends on luck |
| 2026-11-12 | Latin letter rules (ii→ий, vowel+i→й), эгнээ synonym, answer-type check (зай fixed), number words; q22/q23 added. Reverted: хурд rule change and хурдны авто зам synonym (both lost Table 3.2 for q01/q17) | 17 ✓ / 2 ~ / 4 ✗ (of 23) | yes | q01-q21 same as 1208, q22 now ✓ |
| 2026-11-12 | Table-only search for the lookup (+ grader fix: dash before a number no longer glued, so 'case — value' lists are graded right) | 18 ✓ / 2 ~ / 3 ✗ (of 23) | yes | q04 was always right, old grader hid list values |
| 2026-11-12 | Off-topic reply when router says unknown and RAG finds no answer; more road words in router (машин, цэнэгл, станц…) | 19 ✓ / 1 ~ / 3 ✗ (of 23) | yes | q21 fixed; q20 kept honest |
| 2026-11-12 | Class names not used in the book (II ангилал, 3-р ангилал…): answer without them + note with the book's Зэрэг 1–3 | 20 ✓ / 1 ~ / 2 ✗ (of 23) | yes | q05 fixed without guessing a mapping |
| 2026-11-12 | sources: the answer's own chunk (table lookup / Gemma's pick / overview sentences) listed first | 20 ✓ / 1 ~ / 2 ✗ (of 23) | yes | right page cited: see run 1258 |
