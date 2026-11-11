"""Check an LLM answer against the context it was given.

A small model sometimes writes numbers that are not in the book ("185 м" when the table says
200 м), or takes a real number from an unrelated passage (a curve radius of 185 м, a bus-stop
spacing of 3.5 км). So a number in the answer counts as supported only if it appears in the
context on a line (or the line next to it) that also shares at least MIN_SHARED_WORDS words
with the question. Citation numbers (page, section, table, figure), list markers ("1.", "2)")
and numbers from the question itself are ignored.
"""
from __future__ import annotations

import re

MIN_SHARED_WORDS = 2
STEM_LEN = 5  # Mongolian words share a stem and differ in suffixes: "зогсох" / "зогсолтын"

_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")
# "хуудас 139", "х. 139", "хэсэг 3.2", "Хүснэгт 3.2", "Зураг 3.1", "Бүлэг 11"
_CITATION_RE = re.compile(
    r"(?:хуудас|х\.|хэсэг|бүлэг|хүснэгт|зураг|page|section)\s*[:№]?\s*\d+(?:[.,]\d+)*",
    re.IGNORECASE,
)
_LIST_MARKER_RE = re.compile(r"(?m)^\s*\d{1,2}[.)]\s")
_WORD_RE = re.compile(r"[а-яёөүa-z]+", re.IGNORECASE)
# Words too common in this domain to show that a line is about the question.
_STOP = {
    "хэд", "вэ", "бэ", "уу", "үү", "юу", "ямар", "аль", "байх", "байна", "ёстой", "болох",
    "гэж", "гэсэн", "болон", "ба", "нь", "энэ", "тэр", "зам", "замын", "замд", "замаас",
    "замууд", "замуудын", "авто", "хамгийн", "бага", "их",
}


def _canonical(number: str) -> str:
    """"3,50" and "3.5" and "3.50" are the same number; "3.0" equals "3"."""
    value = float(number.replace(",", "."))
    return f"{value:g}"


def numbers_in(text: str) -> set[str]:
    return {_canonical(n) for n in _NUM_RE.findall(text or "")}


# Latin input is converted to Cyrillic by rules, so "uzegdeh" becomes "узэгдэх" (not "үзэгдэх").
# Comparing with ү/у, ө/о and similar letters folded keeps such questions from being misjudged.
_FOLD = str.maketrans({"ү": "у", "ө": "о", "ё": "е", "й": "и", "ы": "и"})


def _stems(text: str) -> set[str]:
    return {
        w.lower().translate(_FOLD)[:STEM_LEN]
        for w in _WORD_RE.findall(text or "")
        if len(w) >= 4 and w.lower() not in _STOP
    }


def _shared(q_stems: set[str], line_stems: set[str]) -> int:
    """How many question stems appear in the line; "хурд" matches "хурдт" (one is a prefix)."""
    return sum(
        1 for q in q_stems if any(c.startswith(q) or q.startswith(c) for c in line_stems)
    )


def _context_windows(context_texts: list[str]) -> list[tuple[set[str], set[str]]]:
    """(numbers, word stems) for each line together with its neighbours (wrapped sentences)."""
    windows = []
    for text in context_texts:
        lines = [l for l in (text or "").splitlines() if l.strip()] or [text or ""]
        for i in range(len(lines)):
            chunk = " ".join(lines[max(0, i - 1) : i + 2])
            windows.append((numbers_in(lines[i]), _stems(chunk)))
    return windows


def unsupported_numbers(answer: str, context_texts: list[str], question: str = "") -> list[str]:
    """Numbers in the answer that the context does not support for this question."""
    cleaned = _LIST_MARKER_RE.sub(" ", _CITATION_RE.sub(" ", answer or ""))
    wanted = numbers_in(cleaned) - numbers_in(question)
    if not wanted:
        return []
    q_stems = _stems(question)
    windows = _context_windows(context_texts)
    if len(q_stems) < MIN_SHARED_WORDS:
        # Too little to compare with: fall back to "appears somewhere in the context".
        everywhere = set().union(*(nums for nums, _ in windows)) if windows else set()
        return sorted(wanted - everywhere)
    supported = set()
    for nums, stems in windows:
        if _shared(q_stems, stems) >= MIN_SHARED_WORDS:
            supported |= nums
    return sorted(wanted - supported)
