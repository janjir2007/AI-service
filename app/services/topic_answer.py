"""Topic questions: a student types just a topic ("хөвөө", "явган хүний зам").

topic_of() decides whether a (Cyrillic-normalized) message is a bare topic and returns the
topic phrase. build_topic_answer() answers it straight from the database, without search or
LLM: the definition (copied from the matched section, else from the glossary), the section to
read, and related sections. It returns None when the book has neither, so the caller falls
back to the normal paths.
"""
from __future__ import annotations

import os
import re
from typing import Any, Optional

from app.services.facts_answer import _GENERIC_SUBJECTS

# ---- Detection ------------------------------------------------------------------------------

# Everything from "талаар" / "тухай" onward is a request tail.
_CUT_AFTER = re.compile(r"\s+(?:талаар|тухай)(?=\s|$|[?!.,]).*$", re.IGNORECASE | re.DOTALL)
_LEAD = re.compile(r"^(?:надад|бидэнд|чи|та)\s+", re.IGNORECASE)
_TAIL = re.compile(
    r"(?:^|\s+)(?:"
    r"гэж\s+юу\s+(?:вэ|бэ)"
    r"|гэдэг\s+(?:нь\s+)?юу\s+(?:вэ|бэ)"
    r"|юу\s+гэсэн\s+үг(?:\s+(?:вэ|бэ))?"
    r"|(?:дэлгэрэнгүй\s+)?мэдээлэл(?:\s+(?:өгөөч|өгнө\s+үү|хэрэгтэй))?"
    r"|тайлбарла\w*(?:\s+(?:өгөөч|өгнө\s+үү))?"
    r"|(?:хэлж|зааж)\s+(?:өгөөч|өгнө\s+үү)"
    r"|өгөөч|өгнө\s+үү"
    r")\s*$",
    re.IGNORECASE,
)
_PUNCT_END = re.compile(r"[\s?!.,;:]+$")

# Question / value words: their presence means "not a bare topic".
_BLOCK_WORDS = {
    "хэд", "хэдэн", "хэдий", "ямар", "яаж", "яагаад", "хаана", "хэзээ", "аль", "юу", "юуны",
    "вэ", "бэ", "уу", "үү", "юм", "бол", "байх", "байна", "ёстой", "тоо", "хэмжээ", "хамгийн",
    # measurements: "хөвөөний өргөн" is a value question ("хурд" left out: "хурдны зам" is a topic)
    "өргөн", "өргөний", "урт", "өндөр", "гүн", "зузаан",
}
MAX_TOPIC_WORDS = 4


def topic_of(message: str) -> Optional[str]:
    """Return the topic phrase (lowercase) if the message is a bare topic question, else None."""
    text = (message or "").strip()
    text = _CUT_AFTER.sub("", text)
    text = _LEAD.sub("", text)
    while True:
        new = _TAIL.sub("", _PUNCT_END.sub("", text))
        if new == text:
            break
        text = new
    words = re.findall(r"\w+", text.lower())
    if not 1 <= len(words) <= MAX_TOPIC_WORDS:
        return None
    if any(ch.isdigit() for w in words for ch in w):
        return None
    if _BLOCK_WORDS.intersection(words):
        return None
    topic = " ".join(words)
    if topic in _GENERIC_SUBJECTS:
        return None
    return topic


# ---- Matching topic words to book titles ----------------------------------------------------

# Case endings removed before comparing ("хөвөөний" ~ "Хөвөө", "хүний" ~ "хүн"). Matching only.
_SUFFIXES = sorted(
    ["ийн", "ын", "ний", "ны", "ийг", "ыг", "ий", "аас", "ээс", "оос", "өөс",
     "тай", "тэй", "той", "аар", "ээр", "оор", "өөр", "г", "д", "т", "н"],
    key=len,
    reverse=True,
)
_MIN_STEM = 3
MAX_OTHERS = 6


def stem(word: str) -> str:
    w = word.lower()
    while True:
        for suf in _SUFFIXES:
            if w.endswith(suf) and len(w) - len(suf) >= _MIN_STEM:
                w = w[: -len(suf)]
                break
        else:
            return w


def stems(text: str) -> tuple:
    return tuple(stem(w) for w in re.findall(r"\w+", (text or "").lower()) if not w.isdigit())


def match_sections(sections: list[dict], topic_stems: tuple) -> tuple[Optional[dict], list[dict]]:
    """Main = exact title match plus its subsections; others = titles that contain the topic."""
    exact, related = [], []
    want = set(topic_stems)
    for s in sections:
        ts = stems(s.get("section_title") or "")
        if not ts:
            continue
        if ts == topic_stems:
            exact.append(s)
        elif want <= set(ts):
            related.append(s)
    families = []
    for s in exact:
        prefix = s["section"] + "."
        members = [
            m for m in sections
            if m["document_id"] == s["document_id"]
            and (m["section"] == s["section"] or m["section"].startswith(prefix))
        ]
        families.append({
            **s,
            "p_from": min(m["p_from"] for m in members),
            "p_to": max(m["p_to"] for m in members),
            "chunks": sum(m["n"] for m in members),
            "members": members,
        })
    families.sort(key=lambda f: (-f["chunks"], f["p_from"]))
    main = families[0] if families else None
    taken = {(m["document_id"], m["section"]) for m in main["members"]} if main else set()
    others = []
    for s in sorted(exact + related, key=lambda x: (x["document_id"], x["p_from"], x["section"])):
        key = (s["document_id"], s["section"])
        if key in taken:
            continue
        taken.add(key)
        others.append(s)
    return main, others[:MAX_OTHERS]


# ---- Scattered topics: where the text mentions the topic ----------------------------------

_MENTIONS_SQL = """
SELECT c.document_id, d.name AS filename, d.file_path, c.section, c.section_title,
       MIN(c.page_number) AS p_from, MAX(c.page_number) AS p_to, COUNT(*) AS n
FROM ai_document_chunks c JOIN ai_documents d ON d.id = c.document_id
WHERE c.content ~* %s AND COALESCE(c.section, '') <> ''
GROUP BY c.document_id, d.name, d.file_path, c.section, c.section_title
ORDER BY n DESC, p_from
LIMIT 12
"""


def mention_pattern(topic: str) -> str:
    """Postgres regex for the topic in any case form: each word stem + any Cyrillic letters."""
    parts = [re.escape(stem(w)) + "[а-яөүё]*" for w in re.findall(r"\w+", (topic or "").lower())]
    return r"\m" + r"\s+".join(parts)


def merge_scattered(title_matches: list[dict], mentions: list[dict], limit: int = MAX_OTHERS) -> list[dict]:
    """Title matches first (strongest), then sections by mention count; no duplicates."""
    out, seen = [], set()
    for s in list(title_matches) + list(mentions):
        key = (s["document_id"], s["section"])
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out[:limit]


# ---- Definitions ----------------------------------------------------------------------------

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_SECTION_NO = re.compile(r"^\d+(?:\.\d+)*\.?$")
GLOSSARY_TITLE = "Нэр томьёо"
_GLOSS_ENTRY = re.compile(
    r"(?:^|(?<=\s))([A-Z][A-Z0-9'(),/&\- ]*[A-Z0-9)])\s+[-–—]\s+([^.]{1,120}?)\.\s+"
)


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _word(token: str) -> str:
    return re.sub(r"[^\w-]", "", token.lower())


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(_flat(text)) if s.strip()]


def definition_in_sentence(sentence: str, topic_stems: tuple) -> Optional[str]:
    """The definition if the words before "гэдэг нь" are exactly the topic (a merged heading
    "3.3 Хөвөө Хөвөө гэдэг нь" is allowed). Narrower terms ("Тасралтгүй ... үзэгдэх зай
    гэдэг нь") are rejected."""
    tokens = sentence.split(" ")
    n = len(topic_stems)
    for i in range(len(tokens) - 1):
        if _word(tokens[i]) == "гэдэг" and _word(tokens[i + 1]) == "нь":
            prefix = tokens[:i]
            while prefix and _SECTION_NO.match(prefix[0]):
                prefix = prefix[1:]
            prefix_stems = tuple(stem(_word(t)) for t in prefix if _word(t))
            if n and prefix_stems in (topic_stems, topic_stems + topic_stems):
                return " ".join(tokens[i - n:])
            return None
    return None


def find_section_definition(rows: list[dict], topic_stems: tuple) -> Optional[dict]:
    for row in rows:
        for sent in sentences(row.get("content") or ""):
            found = definition_in_sentence(sent, topic_stems)
            if found:
                return {"text": found, "row": row}
    return None


def parse_glossary(rows: list[dict]) -> list[dict]:
    """Entries "ENGLISH TERM - Монгол нэр. Definition." from glossary chunks in reading order."""
    entries: list[dict] = []
    by_doc: dict[Any, list[dict]] = {}
    for r in rows:
        by_doc.setdefault(r.get("document_id"), []).append(r)
    for doc_rows in by_doc.values():
        parts, offsets, pos = [], [], 0
        for r in doc_rows:
            t = _flat(r.get("content"))
            offsets.append((pos, r))
            parts.append(t)
            pos += len(t) + 1
        text = " ".join(parts)
        matches = list(_GLOSS_ENTRY.finditer(text))
        for k, m in enumerate(matches):
            end = matches[k + 1].start() if k + 1 < len(matches) else len(text)
            row = next(r for start, r in reversed(offsets) if start <= m.start())
            entries.append({
                "en": m.group(1).strip(),
                "term": m.group(2).strip(),
                "definition": text[m.end():end].strip(),
                "row": row,
                "page": row.get("page_number"),
            })
    return entries


def glossary_definition(entries: list[dict], topic_stems: tuple) -> Optional[dict]:
    for e in entries:
        if stems(e["term"]) == topic_stems:
            text = " ".join(sentences(e["definition"])[:2])[:400].rstrip()
            if text:
                return {**e, "text": text}
    return None


# ---- Answer ---------------------------------------------------------------------------------

def _pages(p_from: Any, p_to: Any) -> str:
    return f"х. {p_from}" if p_from == p_to else f"х. {p_from}–{p_to}"


def compose_topic_answer(headline: str, definition: Optional[dict], main: Optional[dict],
                         others: list[dict]) -> str:
    lines = [headline]
    if definition:
        where = (f"Нэр томьёо, х. {definition['page']}" if definition.get("glossary")
                 else f"х. {definition['page']}")
        lines.append(f"Тодорхойлолт: {definition['text']} ({where})")
    if others:
        label = "Бусад хэсэг" if main else "Номд тусдаа бүлэг байхгүй. Дараах хэсгүүдэд дурдсан"
        lines.append(label + ": " + "; ".join(
            f"{o['section']} {o['section_title']} ({_pages(o['p_from'], o['p_to'])})" for o in others
        ))
    if main:
        lines.append(f"Дэлгэрэнгүй: хэсэг {main['section']}, {_pages(main['p_from'], main['p_to'])}")
    return "\n".join(lines)


_SECTIONS_SQL = """
SELECT c.document_id, d.name AS filename, d.file_path, c.section, c.section_title,
       MIN(c.page_number) AS p_from, MAX(c.page_number) AS p_to, COUNT(*) AS n
FROM ai_document_chunks c JOIN ai_documents d ON d.id = c.document_id
WHERE c.section IS NOT NULL AND c.section <> '' AND c.section_title IS NOT NULL
GROUP BY c.document_id, d.name, d.file_path, c.section, c.section_title
"""
_FAMILY_SQL = """
SELECT page_number, section, section_title, content
FROM ai_document_chunks
WHERE document_id = %s AND content_type = 'text' AND (section = %s OR section LIKE %s)
ORDER BY chunk_index
"""
_GLOSSARY_SQL = """
SELECT c.document_id, d.name AS filename, d.file_path, c.page_number, c.content
FROM ai_document_chunks c JOIN ai_documents d ON d.id = c.document_id
WHERE c.section_title = %s AND c.content_type = 'text'
ORDER BY c.document_id, c.chunk_index
"""


def _fetch(conn: Any, sql: str, params: tuple = ()) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [r if isinstance(r, dict) else dict(zip(cols, r)) for r in cur.fetchall()]


def _filename(src: dict) -> Optional[str]:
    fn = src.get("filename")
    if (not fn or not str(fn).lower().endswith(".pdf")) and src.get("file_path"):
        return os.path.basename(src["file_path"])
    return fn


def _doc_ok(row: dict, filenames: Optional[list[str]]) -> bool:
    if not filenames:
        return True
    return bool({row.get("filename"), _filename(row)} & set(filenames))


def _hit(src: dict, page: Any, section: Any, title: Any, content: str) -> dict:
    return {"filename": _filename(src), "file_path": src.get("file_path"), "page": page,
            "section": section, "title": title, "content": content}


def build_topic_answer(conn: Any, topic: str, filenames: Optional[list[str]] = None) -> Optional[dict]:
    topic_stems = stems(topic)
    if not topic_stems:
        return None
    sections = [s for s in _fetch(conn, _SECTIONS_SQL) if _doc_ok(s, filenames)]
    main, others = match_sections(sections, topic_stems)

    definition = None
    hits: list[dict] = []
    if main:
        rows = _fetch(conn, _FAMILY_SQL, (main["document_id"], main["section"], main["section"] + ".%"))
        found = find_section_definition(rows, topic_stems)
        if found:
            r = found["row"]
            definition = {"text": found["text"], "page": r["page_number"], "glossary": False}
            hits.append(_hit(main, r["page_number"], r["section"], r["section_title"], found["text"]))
    if definition is None:
        gl_rows = [r for r in _fetch(conn, _GLOSSARY_SQL, (GLOSSARY_TITLE,)) if _doc_ok(r, filenames)]
        entry = glossary_definition(parse_glossary(gl_rows), topic_stems)
        if entry:
            definition = {"text": entry["text"], "page": entry["page"], "glossary": True, "term": entry["term"]}
            hits.append(_hit(entry["row"], entry["page"], None, GLOSSARY_TITLE, entry["text"]))
    if main is None:
        mentions = [s for s in _fetch(conn, _MENTIONS_SQL, (mention_pattern(topic),))
                    if _doc_ok(s, filenames)]
        others = merge_scattered(others, mentions)
    if main is None and definition is None and not others:
        return None

    if main:
        hits.append(_hit(main, main["p_from"], main["section"], main["section_title"], ""))
    for o in others:
        hits.append(_hit(o, o["p_from"], o["section"], o["section_title"], ""))
    if main:
        headline = main["section_title"]
    elif definition and definition.get("term"):
        headline = definition["term"]
    else:
        headline = topic.capitalize()
    answer = compose_topic_answer(headline, definition, main, others)
    return {"answer": answer, "headline": headline, "hits": hits, "topic": topic}
