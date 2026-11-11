from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

# Norm-style headings: "3.2. Хөдөлгөөний зурвасын өргөн"
SECTION_HEADING_RE = re.compile(
    r"^(?P<num>\d+(?:\.\d+)+)\.\s+(?P<title>.+?)\s*$"
)
# Chapter-level: "3. Замын геометри" (single number before dot, title not only digits)
CHAPTER_HEADING_RE = re.compile(r"^(?P<num>\d+)\.\s+(?P<title>[^\d].+?)\s*$")
TABLE_TITLE_RE = re.compile(
    r"(?i)(хүснэгт|table)\s*[\d\.]+",
    re.UNICODE,
)
FORMULA_LINE_RE = re.compile(r"(=|\\frac|\^|\bsin\b|\bcos\b|\btan\b|\b√)")


@dataclass
class SectionContext:
    chapter: str | None = None
    section: str | None = None
    title: str | None = None
    page: int | None = None

    def as_metadata(self) -> dict:
        return {
            "chapter": self.chapter,
            "section": self.section,
            "title": self.title,
            "page": self.page,
        }


def _is_likely_heading_line(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 4 or len(stripped) > 200:
        return False
    if stripped.count(".") > 8:
        return False
    # Skip bare numeric lists like "1." or page footers
    if re.fullmatch(r"\d+\.?", stripped):
        return False
    return True


def parse_section_heading(line: str) -> SectionContext | None:
    if not _is_likely_heading_line(line):
        return None
    stripped = line.strip()
    m = SECTION_HEADING_RE.match(stripped)
    if m:
        num = m.group("num")
        title = m.group("title").strip()
        parts = num.split(".")
        chapter = parts[0]
        return SectionContext(chapter=chapter, section=num, title=title)
    m = CHAPTER_HEADING_RE.match(stripped)
    if m:
        chapter = m.group("num")
        title = m.group("title").strip()
        return SectionContext(chapter=chapter, section=f"{chapter}.0", title=title)
    return None


HEADING_MARK = "§ "


def parse_marked_heading(line: str) -> SectionContext | None:
    """Headings found by pdf_service (bold, numbered) are written as "§ 3.3. Хөвөө"."""
    stripped = line.strip()
    if not stripped.startswith(HEADING_MARK):
        return None
    return parse_section_heading(stripped[len(HEADING_MARK):])


def detect_content_type(text: str) -> str:
    if TABLE_TITLE_RE.search(text) or "|" in text and text.count("|") >= 2:
        return "table"
    if FORMULA_LINE_RE.search(text):
        return "formula"
    return "text"


def apply_section_to_lines(
    lines: Iterable[str], page_number: int, context: SectionContext
) -> tuple[list[tuple[str, SectionContext]], SectionContext]:
    """Return (line, context) pairs; updates context when headings found."""
    out: list[tuple[str, SectionContext]] = []
    for line in lines:
        heading = parse_section_heading(line)
        if heading:
            heading.page = page_number
            context = SectionContext(
                chapter=heading.chapter,
                section=heading.section,
                title=heading.title,
                page=page_number,
            )
        out.append((line, SectionContext(**context.as_metadata())))
    return out, context
