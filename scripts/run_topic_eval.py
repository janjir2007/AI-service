"""Automatic topic eval: every short section title asked as a topic, in Cyrillic and Latin.

No server, no LLM. Goes through the same steps as /chat (router -> topic_of ->
build_topic_answer). Pass = "Дэлгэрэнгүй: хэсэг X" cites a section with this title.

Usage:
  python scripts/run_topic_eval.py                  # summary + up to 5 examples per bucket
  python scripts/run_topic_eval.py --show nothing   # list every case in one bucket
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import psycopg2  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.services import topic_answer as ta  # noqa: E402
from app.services.intent_router import classify_message  # noqa: E402
from app.services.script_utils import cyrillic_to_latin  # noqa: E402

TITLES_SQL = """
SELECT section_title, array_agg(DISTINCT section)
FROM ai_document_chunks
WHERE COALESCE(section, '') <> '' AND section_title IS NOT NULL
GROUP BY section_title
ORDER BY MIN(page_number)
"""
_MAIN = re.compile(r"Дэлгэрэнгүй: хэсэг (\S+?),")
BUCKETS = ["pass", "wrong_section", "list_only", "nothing", "not_topic", "small_talk", "error"]


def ask(conn, message: str) -> dict:
    route = classify_message(message)
    if route.intent not in ("road", "unknown"):
        return {"bucket": "small_talk", "query": "", "cited": None}
    query = route.query
    topic = ta.topic_of(query)
    if not topic:
        return {"bucket": "not_topic", "query": query, "cited": None}
    try:
        res = ta.build_topic_answer(conn, topic)
    except Exception as exc:  # keep going; report it
        return {"bucket": "error", "query": query, "cited": None, "error": str(exc)}
    if not res:
        return {"bucket": "nothing", "query": query, "cited": None}
    m = _MAIN.search(res["answer"])
    return {"bucket": "main" if m else "list_only", "query": query, "cited": m.group(1) if m else None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-words", type=int, default=4)
    ap.add_argument("--show", default="", help="list every case in this bucket")
    args = ap.parse_args()

    conn = psycopg2.connect(get_settings().database_url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(TITLES_SQL)
        titles = [(t.strip(), sorted(s)) for t, s in cur.fetchall() if t and t.strip()]
    short = [x for x in titles if len(x[0].split()) <= args.max_words]

    t0 = time.time()
    counts = {"cyr": Counter(), "lat": Counter()}
    results = []
    for title, secs in short:
        latin = cyrillic_to_latin(title)
        entry = {"title": title, "sections": secs, "latin": latin}
        for key, msg in (("cyr", title), ("lat", latin)):
            r = ask(conn, msg)
            if r["bucket"] == "main":
                r["bucket"] = "pass" if r["cited"] in secs else "wrong_section"
            entry[key] = r
            counts[key][r["bucket"]] += 1
        results.append(entry)
    conn.close()

    n = len(short)
    print(f"Topic eval: {n} titles with <= {args.max_words} words "
          f"({len(titles) - n} longer titles skipped), {time.time() - t0:.1f}s")
    print(f"{'':10}" + "".join(f"{b:>14}" for b in BUCKETS))
    for key, label in (("cyr", "Cyrillic"), ("lat", "Latin")):
        print(f"{label:10}" + "".join(f"{counts[key][b]:>14}" for b in BUCKETS)
              + f"   pass {100 * counts[key]['pass'] / max(n, 1):.0f}%")

    for key, label in (("cyr", "Cyrillic"), ("lat", "Latin")):
        for b in BUCKETS[1:]:
            cases = [e for e in results if e[key]["bucket"] == b]
            if not cases or (args.show and b != args.show):
                continue
            limit = None if args.show == b else 5
            print(f"\n[{label}] {b}: {len(cases)}")
            for e in cases[:limit]:
                r = e[key]
                shown = e["latin"] if key == "lat" else e["title"]
                print(f"  {shown!r} -> query {r['query']!r} cited {r['cited']} "
                      f"(want {', '.join(e['sections'])}){' ' + r['error'] if r.get('error') else ''}")

    out_dir = ROOT / "eval" / "topic_results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{time.strftime('%Y%m%d-%H%M')}.json"
    out.write_text(json.dumps({"max_words": args.max_words, "counts": {k: dict(v) for k, v in counts.items()},
                               "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nSaved: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
