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
