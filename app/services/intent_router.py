"""Decide what a chat message is before any search runs.

Small talk (greeting, thanks, bye, who are you, what can you do) is answered from templates:
instant, no database, no LLM, no risk of a random norm paragraph answering "Hi".
Road questions go to RAG. Anything else goes to RAG too, and if RAG finds nothing relevant
the caller answers with the polite off-topic reply.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.script_utils import cyrillic_to_latin, detect_script, latin_to_cyrillic, reply_script

SMALL_TALK = ("greeting", "thanks", "bye", "identity", "capabilities")

# Patterns run on the Cyrillic-normalized, lowercased message.
_CYR_PATTERNS: dict[str, list[str]] = {
    "greeting": [
        r"сайн\s+(?:байна\s+)?уу",
        r"сайн\s+байцгаана\s+уу",
        r"сайхан\s+амарсан\s+уу",
        r"(?:өглөөний|өдрийн|оройн)\s+мэнд",
        r"мэнд\s+хүргэе",
        r"(?:сонин\s+)?юу\s+байна",
    ],
    "thanks": [r"баярлалаа", r"баярлаа", r"их\s+баярлалаа"],
    "bye": [r"баяртай", r"дараа\s+уулзъя", r"дараа\s+уулзая"],
    "identity": [r"(?:чи|та)\s+хэн\s+(?:бэ|вэ)", r"хэн\s+бэ", r"чи\s+юу\s+вэ"],
    "capabilities": [
        r"юу\s+(?:хийж|хийх)\s+чадах",
        r"юугаар\s+туслах",
        r"яаж\s+ашиглах",
        r"тусламж",
    ],
}

# Patterns run on the original lowercased message (English chat words).
_EN_PATTERNS: dict[str, list[str]] = {
    "greeting": [r"\b(?:hi+|hello|helo|hey)\b", r"\bgood\s+(?:morning|afternoon|evening)\b"],
    "thanks": [r"\bthanks?\b", r"\bthank\s+you\b", r"\bthx\b", r"\bty\b"],
    "bye": [r"\bbye\b", r"\bgoodbye\b", r"\bsee\s+you\b"],
    "identity": [r"\bwho\s+are\s+you\b"],
    "capabilities": [r"\bwhat\s+can\s+you\s+do\b", r"^\s*help\s*[?!.]*\s*$"],
}

# Word stems that mark a road / norm question.
_ROAD_STEMS = (
    "зам", "явган", "өргөн", "урт", "өндөр", "хурд", "норм", "барилга", "гүүр", "хучилт",
    "зурвас", "хөдөлгөөн", "ангилал", "ангилл", "гэрлэн", "дохио", "хэвгий", "уулзвар",
    "тэмдэг", "асфальт", "бетон", "суурь", "ус зайлуулах", "гарц", "тээвр", "ачаалал",
    "радиус", "налуу", "төсөв", "төсв", "хүн цаг", "машин цаг", "ажилчин", "ажилчн",
    "геодез", "бнбд", "8325", "8326", "гудамж", "зогсоол", "хашлага", "шуудуу",
    "машин", "цэнэгл", "станц", "жолооч", "дугуй", "автобус", "ачаа", "буудал",
)

# Words that carry no question content once a greeting is removed.
_FILLER = {
    "чи", "та", "би", "надад", "уу", "вэ", "бэ", "ок", "ok", "за", "тэгээд", "тэгвэл",
    "аа", "ээ", "оо", "өө", "байна", "сайн",
}


@dataclass
class RouteResult:
    intent: str  # greeting | thanks | bye | identity | capabilities | road | unknown
    input_script: str  # cyrillic | latin | mixed | none
    reply_script: str  # cyrillic | latin
    normalized: str  # whole message in Cyrillic
    query: str  # what to search for (greeting words removed)
    greeted: bool = False  # message opened with a greeting before the question
    salute: str = "Сайн байна уу!"


def _salute(cyr_lower: str, raw_lower: str) -> str:
    if "өглөө" in cyr_lower or "good morning" in raw_lower:
        return "Өглөөний мэнд!"
    if "өдрийн" in cyr_lower or "good afternoon" in raw_lower:
        return "Өдрийн мэнд!"
    if "орой" in cyr_lower or "good evening" in raw_lower:
        return "Оройн мэнд!"
    return "Сайн байна уу!"


def _strip(text: str, patterns: list[str]) -> str:
    for pat in patterns:
        text = re.sub(pat, " ", text, flags=re.IGNORECASE)
    return text


def _content_words(text: str) -> list[str]:
    words = re.findall(r"[\w\u0400-\u04FF]+", text.lower())
    return [w for w in words if w not in _FILLER and len(w) > 1]


def is_road_question(cyr_lower: str) -> bool:
    return any(stem in cyr_lower for stem in _ROAD_STEMS)


def classify_message(message: str) -> RouteResult:
    raw = message.strip()
    raw_lower = raw.lower()
    normalized = latin_to_cyrillic(raw)
    cyr_lower = normalized.lower()
    base = dict(
        input_script=detect_script(raw),
        reply_script=reply_script(raw),
        normalized=normalized,
        salute=_salute(cyr_lower, raw_lower),
    )

    matched: list[str] = []
    for intent in SMALL_TALK:
        cyr_hit = any(re.search(p, cyr_lower) for p in _CYR_PATTERNS[intent])
        en_hit = any(re.search(p, raw_lower) for p in _EN_PATTERNS[intent])
        if cyr_hit or en_hit:
            matched.append(intent)

    if matched:
        # Remove every small-talk phrase; if a real question is left, treat it as a road question.
        # Strip English phrases on the raw text, convert to Cyrillic, then strip Cyrillic phrases.
        rest = raw
        for intent in matched:
            rest = _strip(rest, _EN_PATTERNS[intent])
        rest = latin_to_cyrillic(rest)
        for intent in matched:
            rest = _strip(rest, _CYR_PATTERNS[intent])
        rest_lower = rest.lower()
        if len(_content_words(rest_lower)) >= 2 and is_road_question(rest_lower):
            query = re.sub(r"^[\s,.!?;:-]+", "", rest).strip() or normalized
            return RouteResult(intent="road", query=query, greeted="greeting" in matched, **base)
        # Pick the most specific small-talk intent (identity/capabilities beat a plain "hi").
        for intent in ("capabilities", "identity", "thanks", "bye", "greeting"):
            if intent in matched:
                return RouteResult(intent=intent, query="", **base)

    intent = "road" if is_road_question(cyr_lower) else "unknown"
    return RouteResult(intent=intent, query=normalized, **base)


# ---- Replies --------------------------------------------------------------------------------

_INTRO = "Би RCOS Norm AI — авто зам, барилгын нормын туслах."

TEMPLATES: dict[str, str] = {
    "greeting": "{salute} " + _INTRO + " Танд юугаар туслах вэ?",
    "thanks": "Зүгээр ээ! Өөр асуух зүйл байвал хэлээрэй.",
    "bye": "Баяртай! Замын нормтой холбоотой асуулт гарвал хэзээ ч асуугаарай.",
    "identity": (
        "Би RCOS Norm AI. Монголын авто замын болон барилгын норм, төсвийн жишиг нормын "
        "баримтаас хариулт олж, эх сурвалжийг нь хуудастай нь заадаг."
    ),
    "capabilities": (
        "Би замын нормын асуултад хариулна. Жишээ нь: «Явган хүний замын өргөн хэд вэ?», "
        "«II ангиллын замын хөдөлгөөний зурвасын өргөн хэд вэ?», «Геодезийн туслах ажилчны "
        "хүн цаг хэд вэ?» Кирилл, латин эсвэл холимог үсгээр бичиж болно."
    ),
    "off_topic": (
        "Уучлаарай, би зөвхөн авто зам, барилгын нормын талаар хариулдаг. "
        "Замын талаар асуух зүйл байна уу?"
    ),
}


def small_talk_reply(route: RouteResult) -> str:
    return TEMPLATES[route.intent].format(salute=route.salute)


def off_topic_reply() -> str:
    return TEMPLATES["off_topic"]


def to_reply_script(cyrillic_answer: str, route: RouteResult, enabled: bool = True) -> str:
    """Return the answer in the user's script (Latin if they typed Latin)."""
    if enabled and route.reply_script == "latin":
        return cyrillic_to_latin(cyrillic_answer)
    return cyrillic_answer
