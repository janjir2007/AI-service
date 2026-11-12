"""Build data/vocab.json: every Cyrillic word in the ingested books with its count.

Used to correct Latin input (u = у/ү/ө, o = о/ө ...). Re-run after ingesting books:
  python scripts/build_vocab.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import psycopg2  # noqa: E402

from app.config import get_settings  # noqa: E402

WORD = re.compile(r"[а-яөүё]+")
CHECK = ["ерөнхий", "нөхцөл", "урсгалын", "төсөллөлтийн", "хөвөө", "хүний", "төмөр", "төгс"]


def main() -> None:
    conn = psycopg2.connect(get_settings().database_url)
    counts: Counter = Counter()
    with conn.cursor() as cur:
        cur.execute("SELECT content FROM ai_document_chunks")
        for (content,) in cur:
            counts.update(w for w in WORD.findall((content or "").lower()) if len(w) >= 2)
    conn.close()
    out = ROOT / "data" / "vocab.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(dict(counts.most_common()), ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(counts)} distinct words, {sum(counts.values())} total -> {out.relative_to(ROOT)} "
          f"({out.stat().st_size // 1024} KB)")
    for w in CHECK:
        print(f"  {w}: {counts.get(w, 0)}")


if __name__ == "__main__":
    main()
