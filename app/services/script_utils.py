"""Mongolian script handling: detect Cyrillic / Latin / mixed input and convert between them.

Input side:  informal Latin ("sain bnu", "yavgan zamiin urgun") -> Cyrillic, so search and the
             LLM always work in Cyrillic.
Output side: Cyrillic answer -> informal Latin, when the user typed in Latin.

This is a rule-based first version (word dictionary + letter rules). A trained normalizer
(e.g. ByT5 mongolian-translit) can replace `latin_to_cyrillic` later without touching callers.
"""
from __future__ import annotations

import re

_CYR = re.compile(r"[\u0400-\u04FF]")
_LAT = re.compile(r"[A-Za-z]")
_ROMAN = re.compile(r"^(?:I{1,3}|IV|V|VI{0,3}|IX|X)$")
_TOKEN = re.compile(r"[A-Za-z\u0400-\u04FF]+|[^A-Za-z\u0400-\u04FF]+")

# Common informal Latin spellings -> Cyrillic. Checked before letter rules, so ambiguous
# vowels (u = у/ү/ө, o = о/ө) come out right for frequent words.
WORD_MAP: dict[str, str] = {
    # chat
    "sain": "сайн", "saina": "сайн", "baina": "байна", "bn": "байна", "bna": "байна",
    "bnu": "байна уу", "bainuu": "байна уу", "bnuu": "байна уу", "sainuu": "сайн уу",
    "uu": "уу", "u": "уу", "yu": "юу", "yuu": "юу", "ve": "вэ", "be": "бэ",
    "chi": "чи", "ta": "та", "bi": "би", "hen": "хэн", "hiij": "хийж", "hiih": "хийх",
    "chadah": "чадах", "chadna": "чадна", "tuslah": "туслах", "tuslaach": "туслаач",
    "yuugaar": "юугаар", "mend": "мэнд", "ugluunii": "өглөөний", "uglunii": "өглөөний",
    "udriin": "өдрийн", "oroin": "оройн", "amarsan": "амарсан", "saihan": "сайхан",
    "bayarlalaa": "баярлалаа", "bayrlalaa": "баярлалаа", "bayarlaa": "баярлаа",
    "bayartai": "баяртай", "bayrtai": "баяртай", "daraa": "дараа", "uulzii": "уулзъя",
    "uulzya": "уулзъя", "tegvel": "тэгвэл", "nadad": "надад", "goy": "гоё",
    "shuleg": "шүлэг", "bicheed": "бичээд", "ug": "өг", "uguuch": "өгөөч",
    "yamar": "ямар", "ymar": "ямар", "hed": "хэд", "hedn": "хэдэн", "heden": "хэдэн",
    "ali": "аль", "yaj": "яаж", "yagaad": "яагаад", "ve?": "вэ?", "sonin": "сонин",
    # road / norm vocabulary
    "zam": "зам", "zamiin": "замын", "zamin": "замын", "zamyn": "замын", "zamd": "замд",
    "avto": "авто", "yavgan": "явган", "hunii": "хүний", "hun": "хүн", "urgun": "өргөн",
    "urgen": "өргөн", "urgunii": "өргөний", "urt": "урт", "undur": "өндөр",
    "hurd": "хурд", "hurdnii": "хурдны", "hurdni": "хурдны", "hyazgaar": "хязгаар",
    "norm": "норм", "normiin": "нормын", "normin": "нормын", "barilga": "барилга",
    "barilgiin": "барилгын", "guur": "гүүр", "guuriin": "гүүрийн", "huchilt": "хучилт",
    "zurvas": "зурвас", "zurvasiin": "зурвасын", "hudulguun": "хөдөлгөөн",
    "hudulguunii": "хөдөлгөөний", "angilal": "ангилал", "angilliin": "ангиллын",
    "gerlen": "гэрлэн", "dohio": "дохио", "hevgii": "хэвгий", "uulzvar": "уулзвар",
    "temdeg": "тэмдэг", "tsag": "цаг", "ajilchin": "ажилчин", "ajilchnii": "ажилчны",
    "geodez": "геодез", "geodeziin": "геодезийн", "tusuv": "төсөв", "tusviin": "төсвийн",
    "jishig": "жишиг", "gudamj": "гудамж", "zogsool": "зогсоол", "us": "ус",
    "zogsoh": "зогсох", "uyiin": "үеийн", "uyin": "үеийн", "uzegdeh": "үзэгдэх", "zai": "зай",
    "zailuulah": "зайлуулах", "suuri": "суурь", "km": "км", "m": "м", "sm": "см",
}

# Multi-letter rules first, then single letters.
_DIGRAPHS = [("sh", "ш"), ("ch", "ч"), ("ts", "ц"), ("kh", "х"), ("ya", "я"),
             ("yo", "ё"), ("yu", "ю"), ("ye", "е")]
_LETTERS = {
    "a": "а", "b": "б", "v": "в", "w": "в", "g": "г", "d": "д", "e": "э", "j": "ж",
    "z": "з", "i": "и", "k": "к", "q": "к", "l": "л", "m": "м", "n": "н", "o": "о",
    "p": "п", "r": "р", "s": "с", "t": "т", "u": "у", "f": "ф", "h": "х", "x": "х",
    "c": "ц",
}

_TO_LATIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "ye", "ё": "yo", "ж": "j",
    "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "ө": "u", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ү": "u", "ф": "f",
    "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "ii", "ь": "i",
    "э": "e", "ю": "yu", "я": "ya",
}


def detect_script(text: str) -> str:
    """Return 'cyrillic', 'latin', 'mixed' or 'none'. Roman numerals (II, IV) don't count as Latin."""
    lat = 0
    cyr = len(_CYR.findall(text))
    for word in re.findall(r"[A-Za-z]+", text):
        if not _ROMAN.match(word):
            lat += len(word)
    if lat and cyr:
        return "mixed"
    if lat:
        return "latin"
    if cyr:
        return "cyrillic"
    return "none"


def reply_script(text: str) -> str:
    """Script to answer in: Latin when most letters the user typed are Latin, else Cyrillic."""
    lat = sum(len(w) for w in re.findall(r"[A-Za-z]+", text) if not _ROMAN.match(w))
    cyr = len(_CYR.findall(text))
    return "latin" if lat > cyr else "cyrillic"


def _letters_to_cyrillic(word: str) -> str:
    out: list[str] = []
    i = 0
    low = word.lower()
    while i < len(low):
        pair = low[i : i + 2]
        hit = next((cyr for lat, cyr in _DIGRAPHS if pair == lat), None)
        if hit:
            out.append(hit)
            i += 2
            continue
        ch = low[i]
        if ch == "y":
            # word-final y after a vowel is й ("sain" style), otherwise ы ("zamyn")
            prev = low[i - 1] if i else ""
            out.append("й" if prev in "aeiou" and i == len(low) - 1 else "ы")
        elif ch in _LETTERS:
            out.append(_LETTERS[ch])
        else:
            out.append(word[i])
        i += 1
    return "".join(out)


def _word_to_cyrillic(token: str) -> str:
    if not _LAT.search(token) or _ROMAN.match(token):
        return token
    mapped = WORD_MAP.get(token.lower())
    if mapped is not None:
        return mapped
    if _CYR.search(token):
        # mixed inside one word, e.g. "zamын": convert only the Latin letters
        return "".join(
            _letters_to_cyrillic(part) if _LAT.search(part) else part
            for part in re.findall(r"[A-Za-z]+|[^A-Za-z]+", token)
        )
    return _letters_to_cyrillic(token)


def latin_to_cyrillic(text: str) -> str:
    """Convert informal Latin / mixed Mongolian to Cyrillic. Cyrillic, digits and units pass through."""
    return "".join(_word_to_cyrillic(tok) for tok in _TOKEN.findall(text))


def cyrillic_to_latin(text: str) -> str:
    """Convert Cyrillic Mongolian to the informal Latin people type ("Сайн байна уу" -> "Sain baina uu")."""
    text = text.replace("ый", "ii").replace("ЫЙ", "II").replace("ий", "ii").replace("ИЙ", "II")
    out: list[str] = []
    for ch in text:
        low = ch.lower()
        if low in _TO_LATIN:
            lat = _TO_LATIN[low]
            out.append(lat[:1].upper() + lat[1:] if ch != low and lat else lat)
        else:
            out.append(ch)
    return "".join(out)
