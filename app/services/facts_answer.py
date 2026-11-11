"""Facts mode: the LLM picks facts from the context as JSON; code checks them and writes the answer.

A 4B model reads and selects well but writes Mongolian poorly. So the model only fills a small
form (FACTS_SCHEMA). Every value must appear in the book text, the note must be copied word for
word, and the source line comes from chunk metadata, never from the model.
"""
from __future__ import annotations

import json
import re
from typing import Any

FACTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "chunk": {"type": "integer"},
        "subject": {"type": "string"},
        "value": {"type": "string"},
        "unit": {"type": "string"},
        "cases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "case": {"type": "string"},
                    "value": {"type": "string"},
                    "unit": {"type": "string"},
                },
                "required": ["case", "value", "unit"],
            },
        },
        "note": {"type": "string"},
    },
    "required": ["found", "chunk", "subject", "value", "unit", "cases", "note"],
}

FACTS_SYSTEM_PROMPT = """Та Монголын барилга, авто замын нормын баримтаас асуултын хариултыг олж, зөвхөн JSON буцаана. Өөрөө өгүүлбэр зохиохгүй, тоо зохиохгүй.

Талбарууд:
- found: контекстэд асуултын шууд хариулт байвал true, үгүй бол false.
- chunk: хариулт олдсон контекст блокийн id.
- subject: утга хамаарах тодорхой ангилал, нөхцөлийн нэр, контекстэд бичигдсэнээр. «замын ангилал» гэх мэт ерөнхий үг бичихгүй.
- value: зөвхөн богино утга (тоо эсвэл муж), нэгжгүйгээр. Өгүүлбэр бичихгүй. Хэд хэдэн мөрийн утгыг нэг муж болгож нийлүүлэхгүй.
- unit: нэгж (м, см, %, км/ц гэх мэт). Нэгжгүй бол "".
- cases: утга нь ангилал, нөхцөлөөс хамаарч өөр байвал бусад мөр бүрийг тусад нь бич. case талбарт зөвхөн богино нэр; өгүүлбэр хуулахгүй. Байхгүй бол [].
- note: утгыг тайлбарласан нэг өгүүлбэрийг контекстээс үгчлэн хуулна. Байхгүй бол "".

found=false бол subject, value, unit, note нь "", cases нь [], chunk нь 0."""

_MAX_VALUE = 40
_MAX_CASE = 60
_NUM = re.compile(r"\d+(?:[.,]\d+)?")
_SPACE = re.compile(r"\s+")
_TABLE = re.compile(r"Хүснэгт\s*\d+(?:\.\d+)*", re.IGNORECASE)
_Q_END = re.compile(r"\s+(?:хэд|ямар)(?:\s+(?:байх|байна))?\s+(?:вэ|бэ)\s*[?!.]*\s*$", re.IGNORECASE)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_GENERIC_SUBJECTS = {"замын ангилал", "ангилал", "зам", "нөхцөл", "утга"}


def facts_user_prompt(message: str, blocks: list[dict]) -> str:
    numbered = [{"id": i + 1, **b} for i, b in enumerate(blocks)]
    context = json.dumps(numbered, ensure_ascii=False, separators=(",", ":"))
    return f"Контекст:\n{context}\n\nАсуулт: {message}"


def _clean(s: Any) -> str:
    return _SPACE.sub(" ", str(s or "")).strip()


def _flat(s: Any) -> str:
    return _clean(s).lower()


def _numbers(text: str) -> set[str]:
    return {n.replace(",", ".") for n in _NUM.findall(text or "")}


def _block_text(block: dict) -> str:
    return f"{block.get('title') or ''} {block.get('content') or ''}"


def _copied(text: str, block: dict) -> bool:
    return bool(_flat(text)) and _flat(text) in _flat(block.get("content"))


def _supported(value: str, block: dict) -> bool:
    """True when the value's numbers (or, with no digits, its text) appear in the block."""
    nums = _numbers(value)
    text = _block_text(block)
    if nums:
        return nums <= _numbers(text)
    flat = _flat(value)
    return bool(flat) and flat in _flat(text)


def _strip_unit(value: str, unit: str) -> str:
    if unit and value.lower().endswith(unit.lower()):
        return value[: -len(unit)].rstrip()
    return value


def validate_facts(facts: Any, blocks: list[dict], message: str = "") -> dict | None:
    """Return checked facts, or None when nothing supported is left."""
    if not isinstance(facts, dict) or not facts.get("found") or not blocks:
        return None
    value = _clean(facts.get("value"))
    unit = _clean(facts.get("unit"))
    note = _clean(facts.get("note"))
    if not value:
        return None
    try:
        idx = int(facts.get("chunk") or 0) - 1
    except (TypeError, ValueError):
        idx = -1
    order = ([idx] if 0 <= idx < len(blocks) else []) + [i for i in range(len(blocks)) if i != idx]

    if len(value) > _MAX_VALUE:
        # The model put a book passage into "value": show it as the explanation, if really copied.
        home = next((i for i in order if _copied(value, blocks[i])), None)
        if home is None:
            return None
        note, value, unit = value, "", ""
    else:
        value = _strip_unit(value, unit)
        if not value:
            return None
        # Number conditions from the question (e.g. 80 км/ц) must sit in the same row/sentence.
        cond = _numbers(message) - _numbers(value)

        def _ok(i: int) -> bool:
            if not _supported(value, blocks[i]):
                return False
            return not cond or _row_with(blocks[i], _numbers(value) | cond) is not None

        home = next((i for i in order if _ok(i)), None)
        if home is None:
            return None
        if not unit:
            unit = _unit_near(value, _row_with(blocks[home], _numbers(value) | cond) or "")
    subject = _clean(facts.get("subject"))
    if _flat(subject) in _GENERIC_SUBJECTS:
        subject = ""

    cases: list[dict] = []
    seen = {(subject.lower(), value)}
    main_nums = _numbers(value)
    for c in facts.get("cases") or []:
        if not isinstance(c, dict):
            continue
        name = _clean(c.get("case"))
        cunit = _clean(c.get("unit"))
        cv = _strip_unit(_clean(c.get("value")), cunit)
        key = (name.lower(), cv)
        if not name or not cv or len(name) > _MAX_CASE or len(cv) > _MAX_VALUE or key in seen:
            continue
        if main_nums and _numbers(cv) == main_nums:
            continue
        if any(_supported(cv, b) for b in blocks):
            seen.add(key)
            cases.append({"case": name, "value": cv, "unit": cunit})

    if not (10 <= len(note) <= 800 and any(_copied(note, b) for b in blocks)):
        note = ""
    if note:
        note = _extend_note(note, blocks)
    if not value and not note:
        return None

    return {
        "subject": subject,
        "value": value,
        "unit": unit,
        "cases": cases,
        "note": note,
        "block": blocks[home],
    }


def _extend_note(note: str, blocks: list[dict], extra: int = 2, max_len: int = 700) -> str:
    """Add up to `extra` following full sentences from the same book chunk."""
    flat_note = _flat(note)
    for b in blocks:
        if not _copied(note, b):
            continue
        sents = [s.strip() for s in _SENT_SPLIT.split(b.get("content") or "") if s.strip()]
        last = max(
            (i for i, s in enumerate(sents) if len(_flat(s)) >= 15 and _flat(s) in flat_note),
            default=None,
        )
        if last is None:
            return note
        out = note
        for s in sents[last + 1 : last + 1 + extra]:
            s = _clean(s)
            if len(s) < 25 or not s.endswith(".") or len(out) + len(s) + 1 > max_len:
                break
            out += " " + s
        return out
    return note


def headline_from_question(message: str, val: str) -> str:
    """'Явган замын өргөн хэд вэ?' -> 'Явган замын өргөн **1.2 м** байна.'"""
    m = _Q_END.search(message or "")
    if not m:
        return ""
    stem = (message or "")[: m.start()].strip(" ,")
    if len(stem.split()) < 2:
        return ""
    return f"{stem[0].upper()}{stem[1:]} **{val}** байна."


def source_line(block: dict) -> str:
    parts = [block.get("code") or block.get("book") or ""]
    if block.get("page"):
        parts.append(f"х. {block['page']}")
    table = _TABLE.search(_clean(block.get("title")))
    section = _clean(block.get("section"))
    if table:
        parts.append(table.group(0))
    elif section:
        parts.append(f"хэсэг {section}" if section[:1].isdigit() else section)
    return "Эх сурвалж: " + ", ".join(p for p in parts if p)


def compose_answer(f: dict, message: str = "") -> str:
    if f["value"]:
        val = f"{f['value']} {f['unit']}".strip()
        head = headline_from_question(message, val) or (
            f"{f['subject']}: **{val}**" if f["subject"] else f"**{val}**"
        )
    else:
        head = f"**{f['subject']}**" if f["subject"] else ""
    lines = [head] if head else []
    if f["cases"]:
        lines += ["", "Нөхцөлөөс хамаарч:"]
        lines += [f"• {c['case']} — {c['value']} {c['unit']}".rstrip() for c in f["cases"]]
    if f["note"]:
        lines += ["", f"Тайлбар: {f['note']}"]
    lines += ["", source_line(f["block"])]
    return "\n".join(lines).strip()


def measure_from_facts(f: dict) -> tuple[str, str] | None:
    return (f["value"], f["unit"]) if f["value"] else None


# ---- Overview questions ("... талаар мэдээлэл өг") --------------------------------------------

OVERVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "points": {
            "type": "array",
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {"chunk": {"type": "integer"}, "text": {"type": "string"}},
                "required": ["chunk", "text"],
            },
        },
    },
    "required": ["found", "points"],
}

OVERVIEW_SYSTEM_PROMPT = """Та Монголын барилга, авто замын нормын баримтаас асуултын сэдвээр хамгийн чухал мэдээллийг сонгож, зөвхөн JSON буцаана. Өөрөө өгүүлбэр зохиохгүй.

Талбарууд:
- found: контекстэд энэ сэдвийн мэдээлэл байвал true, үгүй бол false.
- points: сэдвийн тухай хамгийн чухал 3-5 өгүүлбэр. Өгүүлбэр бүрийг контекстээс үгчлэн хуулна (өөрчлөхгүй, богиносгохгүй). chunk нь тухайн өгүүлбэр байгаа блокийн id.
Тоо, хэмжээ, шаардлага агуулсан өгүүлбэрийг илүүд үз. Нэг өгүүлбэрийг давтахгүй.

found=false бол points нь []."""

_OVERVIEW_Q = re.compile(
    r"(?:^|\s)(?:талаар|тухай)(?=\s|$|[?!.,])|мэдээлэл|тайлбарла|гэж\s+юу"
    r"|юу\s+гэсэн\s+үг|гэдэг\s+нь\s+юу"  # what does it mean
    r"|болох\s+уу|болно\s+уу|болох\s+юм\s+уу|ёстой\s+(?:юу|уу)",  # yes / no
    re.IGNORECASE,
)
_TOPIC = re.compile(r"^(.*?\S)\s+(талаар|тухай)(?=\s|$|[?!.,])", re.IGNORECASE)
_WHAT_IS = re.compile(r"^(.*?\S)\s+(?:гэж|гэдэг\s+нь)\s+юу", re.IGNORECASE)


def is_overview_question(message: str) -> bool:
    m = message or ""
    return bool(_OVERVIEW_Q.search(m)) and not _Q_END.search(m) and not re.search(r"(?:^|\s)хэд", m, re.IGNORECASE)


def validate_overview(raw: Any, blocks: list[dict], max_points: int = 5) -> list[dict]:
    """Keep only sentences really copied from the context, without duplicates."""
    if not isinstance(raw, dict) or not raw.get("found") or not blocks:
        return []
    out: list[dict] = []
    seen: list[str] = []
    for pt in raw.get("points") or []:
        if not isinstance(pt, dict):
            continue
        text = _clean(pt.get("text"))
        if not 20 <= len(text) <= 600:
            continue
        if not (text[:1].isupper() or text[:1].isdigit()):
            continue  # a fragment starting mid-sentence
        try:
            idx = int(pt.get("chunk") or 0) - 1
        except (TypeError, ValueError):
            idx = -1
        order = ([idx] if 0 <= idx < len(blocks) else []) + [i for i in range(len(blocks)) if i != idx]
        home = next((i for i in order if _copied(text, blocks[i])), None)
        if home is None:
            continue
        key = _flat(text)
        if any(key in s or s in key for s in seen):
            continue
        seen.append(key)
        out.append({"text": text, "block": blocks[home]})
        if len(out) >= max_points:
            break
    return out


def _ref(block: dict) -> str:
    table = _TABLE.search(_clean(block.get("title")))
    section = _clean(block.get("section"))
    if table:
        return table.group(0)
    if section:
        return f"хэсэг {section}" if section[:1].isdigit() else section
    return ""


def sources_line(blocks: list[dict]) -> str:
    items: list[str] = []
    seen: set = set()
    last_code = None
    for b in blocks:
        code = b.get("code") or b.get("book") or ""
        key = (code, b.get("page"), _ref(b))
        if key in seen:
            continue
        seen.add(key)
        parts = [] if code == last_code else [code]
        if b.get("page"):
            parts.append(f"х. {b['page']}")
        if _ref(b):
            parts.append(_ref(b))
        items.append(", ".join(x for x in parts if x))
        last_code = code
    return "Эх сурвалж: " + "; ".join(items)


def overview_heading(message: str) -> str:
    m = _TOPIC.search(message or "")
    if m:
        head = f"{m.group(1)} {m.group(2).lower()}:"
    else:
        m = _WHAT_IS.search(message or "")
        if not m:
            return ""
        head = f"{m.group(1)}:"
    return head[0].upper() + head[1:]


def compose_overview(points: list[dict], message: str = "") -> str:
    head = overview_heading(message)
    lines = [f"**{head}**"] if head else []
    lines += [f"• {p['text']}" for p in points]
    lines += ["", sources_line([p["block"] for p in points])]
    return "\n".join(lines).strip()


# ---- Row check, unit fill, exact-match priority -----------------------------------------------

_CODE = re.compile(r"[0-9A-Za-zА-Яа-яЁёӨөҮү]+(?:[-/][0-9A-Za-zА-Яа-яЁёӨөҮү]+)+")


def _units(block: dict) -> list[str]:
    """Table chunks: one row per line. Text chunks: sentences."""
    content = block.get("content") or ""
    if "table" in str(block.get("content_type") or "").lower():
        return [line for line in content.splitlines() if line.strip()]
    return [s for s in re.split(r"(?<=[.!?])\s+", _clean(content)) if s]


def _row_with(block: dict, nums: set[str]) -> str | None:
    for unit_text in _units(block):
        if nums <= _numbers(unit_text):
            return unit_text
    return None


def _unit_near(value: str, row: str) -> str:
    nums = _NUM.findall(value)
    if not nums or not row:
        return ""
    n = re.escape(nums[-1])
    m = re.search(r"\(([^()]{1,6})\)\s*:\s*" + n, row)
    if m:
        return m.group(1).strip()
    m = re.search(n + r"\s*(км/ц|км|мм|см|м|%)(?![А-Яа-яЁёӨөҮү])", row)
    return m.group(1) if m else ""


def exact_match_order(message: str, blocks: list[dict]) -> list[int]:
    """Blocks that contain a code from the question word for word (e.g. 2А-ХрЗ-ЗХГ-2-70) go first."""
    tokens = [
        tok.lower()
        for tok in _CODE.findall(message or "")
        if len(tok) >= 6 and any(ch.isdigit() for ch in tok)
    ]
    if not tokens:
        return list(range(len(blocks)))
    hit = [i for i, b in enumerate(blocks) if any(tok in _block_text(b).lower() for tok in tokens)]
    return hit + [i for i in range(len(blocks)) if i not in hit]
