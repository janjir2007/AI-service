"""Topic questions: a student types just a topic ("хөвөө", "явган хүний зам").

topic_of() decides whether a (Cyrillic-normalized) message is a bare topic and returns the
topic phrase. Value questions ("хөвөөний өргөн хэд вэ") and "why" questions return None
and keep using the existing paths.
"""
from __future__ import annotations

import re
from typing import Optional

from app.services.facts_answer import _GENERIC_SUBJECTS

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
