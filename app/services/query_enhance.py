"""Query normalization and retrieval relevance for norm RAG chat."""
from __future__ import annotations

import re

from app.services.answer_compose import primary_measurement

_TYPO_SIGNAL = re.compile(r"гэрлэн\s+дохио", re.IGNORECASE)
_NUMERIC_Q = re.compile(r"\b(хэд|хэдэн|аль)\b", re.IGNORECASE)
_SPEED_Q = re.compile(r"хурд|км\s*/?\s*ц|км/ц", re.IGNORECASE)
_SIGNAL_Q = re.compile(r"гэрэл|дохио|гэрлэн", re.IGNORECASE)


def enhance_search_query(query: str) -> str:
    """Expand common Mongolian phrasing so vector + keyword search hit the right sections."""
    q = query.strip()
    if not q:
        return q
    q = _TYPO_SIGNAL.sub("гэрэлэн дохио", q)
    extra: list[str] = []
    lower = q.lower()
    if _SIGNAL_Q.search(lower) and _SPEED_Q.search(lower):
        extra.extend(
            [
                "гэрэлэн дохио",
                "урьдах хурд",
                "хурдны хязгаар",
                "км/ц",
                "улаан гэрэл",
                "шар гэрэл",
            ]
        )
    elif _SIGNAL_Q.search(lower):
        extra.extend(["гэрэлэн дохио", "дохиолол", "гэрэлэн дохиолол"])
    if _SPEED_Q.search(lower) and _NUMERIC_Q.search(lower):
        extra.extend(["хурдны хязгаар", "км/ц", "урьдах хурд", "хамгийн их хурд"])
    if "геодез" in lower or "туслах ажилчин" in lower or "рейкчин" in lower:
        extra.extend([
            "лавлагааны гадас зоох",
            "гадас зоох",
            "17-01-04",
            "25-24-116",
            "хөдөлмөр зарцуулалт",
            "хүн цаг",
        ])
    if "эгнээ" in lower:
        # users say эгнээ, the book says хөдөлгөөний зурвас
        extra.extend(["хөдөлгөөний зурвас", "зурвасын тоо"])
    if not extra:
        return q
    seen = set(lower.split())
    add = [t for t in extra if t.lower() not in seen]
    if not add:
        return q
    return q + " " + " ".join(add)


def _asks_numeric_speed(query: str) -> bool:
    return bool(_NUMERIC_Q.search(query) and _SPEED_Q.search(query))


def _lead_has_speed_value(lead: str) -> bool:
    lower = lead.lower()
    if primary_measurement(lead) and any(k in lower for k in ("хурд", "км", "цаг", "м/с")):
        return True
    if re.search(r"км\s*/\s*ц|км/ц|км цаг", lower):
        return True
    if re.search(r"хурдны\s+хязгаар", lower) and re.search(r"\d", lead):
        return True
    return False


def is_misleading_excerpt(query: str, lead: str) -> bool:
    """True when extractive text matches keywords but not the user's intent (e.g. ramp metering vs speed)."""
    if not lead or not query.strip():
        return False
    lower = lead.lower()
    if _asks_numeric_speed(query) or (
        _SIGNAL_Q.search(query) and _NUMERIC_Q.search(query) and _SPEED_Q.search(query)
    ):
        if _lead_has_speed_value(lead):
            return False
        if ("гэрэл" in lower or "дохио" in lower) and re.search(
            r"тоог\s+.*хязгаар|нэвтрэх|орцын", lower
        ):
            return True
        if _SPEED_Q.search(query) and not _lead_has_speed_value(lead) and not re.search(
            r"хурдны\s+хязгаар", lower
        ):
            return True
    return False


def direct_answer_from_hits(
    query: str,
    hits: list[dict],
    sentence_fn,
) -> str | None:
    """When retrieval has an explicit norm sentence (e.g. 80 km/h + signals), use it if LLM is vague."""
    if not _asks_numeric_speed(query) and not (
        _SIGNAL_Q.search(query) and _NUMERIC_Q.search(query) and _SPEED_Q.search(query)
    ):
        return None
    for hit in hits[:6]:
        for sent in sentence_fn(hit, query, 4):
            if is_misleading_excerpt(query, sent):
                continue
            if not _lead_has_speed_value(sent):
                continue
            if _SIGNAL_Q.search(query) and not _SIGNAL_Q.search(sent):
                continue
            page = hit.get("page")
            return f"Баримтын дагуу: {sent.strip()} (хуудас {page})."
    return None


def retrieval_relevant(
    query: str,
    lead_pack: tuple[float, str, dict] | None,
    min_lead_score: float = 4.0,
) -> bool:
    if not query.strip() or lead_pack is None:
        return False
    score, lead, _hit = lead_pack
    if score < min_lead_score:
        return False
    if is_misleading_excerpt(query, lead):
        return False
    return True
