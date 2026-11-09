"""Official titles for ingested PDFs (filename → Flutter library document)."""

from __future__ import annotations

import os
from pathlib import Path

BOOKS: dict[str, dict[str, str]] = {
    "mybook.pdf": {
        "id": "bnbd-auto-road",
        "code": "БНбД",
        "title": "МОНГОЛ УЛСЫН БАРИЛГЫН НОРМ БА ДУРЭМ",
    },
    "8325.pdf": {
        "id": "azbn-8325",
        "code": "8325",
        "title": "АВТО ЗАМЫН БАРИЛГЫН АЖЛЫН ТӨСВИЙН ЖИШИГ НОРМ",
    },
    "8326.pdf": {
        "id": "azbn-8326",
        "code": "8326",
        "title": "АВТО ЗАМЫН БАРИЛГЫН АЖЛЫН ТӨСВИЙН ЖИШИГ НОРМ",
    },
}

ALLOWED_PDFS = frozenset(BOOKS.keys())
ESTIMATE_PDFS = ("8326.pdf", "8325.pdf")
DESIGN_PDFS = ("mybook.pdf",)

_ESTIMATE_MARKERS = (
    "ажилчин",
    "туслах ажилчин",
    "төсөв",
    "төсвийн",
    "жишиг норм",
    "норм цаг",
    "хүн-цаг",
    "хүн цаг",
    "машин-цаг",
    "машин цаг",
    "тариф",
    "цалин",
    "хөдөлмөрийн норм",
    "ажиллах хүч",
    "нэгж үнэ",
    "материалын норм",
    "геодезийн туслах",
    "геодез",
    "рейкчин",
    "машинист",
    "бетончин",
    "арматурчин",
    "засалчин",
    "мужаан",
    "будагчин",
    "цахилгаанчин",
    "гагнуурчин",
    "8325",
    "8326",
)

_DESIGN_MARKERS = (
    "бнбд",
    "барилгын норм ба дүрэм",
    "тооцоот хурд",
    "хөндлөн хэвгий",
    "зааглах зурвас",
    "зорчих хэсэг",
)


def filename_from_path(path: str | None) -> str:
    if not path:
        return ""
    return os.path.basename(str(path)).strip()


def book_info(filename: str | None, file_path: str | None = None) -> dict[str, str]:
    name = filename_from_path(filename) or filename_from_path(file_path)
    key = name.lower() if name else ""
    meta = BOOKS.get(name) or BOOKS.get(key)
    if meta:
        return {
            "filename": name or meta["id"],
            "book_id": meta["id"],
            "code": meta["code"],
            "book": meta["title"],
        }
    stem = Path(name).stem if name else "баримт"
    return {
        "filename": name or stem,
        "book_id": stem.lower().replace(" ", "-"),
        "code": stem.upper()[:16] or "НОРМ",
        "book": stem,
    }


def preferred_filenames(query: str, explicit: list[str] | None = None) -> list[str] | None:
    """Which ingested PDFs should be searched first for this question."""
    names = [filename_from_path(n) for n in (explicit or []) if n]
    names = [n for n in names if n in ALLOWED_PDFS]
    if names:
        if "8325.pdf" in names and "8326.pdf" in names and "8325" not in (query or "").lower():
            # 8326.pdf is the main road construction norm (ЗЗБНбД 83-25-2023)
            names = ["8326.pdf", "8325.pdf"] + [n for n in names if n not in ("8325.pdf", "8326.pdf")]
        return names

    q = (query or "").strip().lower()
    if not q:
        return None
    if "8325" in q and "8326" not in q:
        return ["8325.pdf", "8326.pdf"]
    if any(n in q for n in ("8326", "8325", "төсвийн жишиг", "жишиг норм", "геодез", "рейкчин")):
        return list(ESTIMATE_PDFS)
    if any(n in q for n in ("mybook", "бнбд", "барилгын норм ба дүрэм")):
        return list(DESIGN_PDFS)

    estimate = sum(1 for m in _ESTIMATE_MARKERS if m in q)
    design = sum(1 for m in _DESIGN_MARKERS if m in q)
    if estimate and estimate >= design:
        return list(ESTIMATE_PDFS)
    return None


def citation_label(info: dict[str, str] | None) -> str:
    if not info:
        return ""
    book = (info.get("book") or "").strip()
    code = (info.get("code") or "").strip()
    if book and code and code not in book:
        return f"{book} · {code}"
    return book or code
