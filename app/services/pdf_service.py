from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

try:
    import fitz  # PyMuPDF
except ImportError as exc:
    raise ImportError(
        "PyMuPDF is required for PDF ingest (import fitz). "
        "In ai-service venv run: pip install -r requirements.txt  "
        "or: pip install 'PyMuPDF>=1.24.0'"
    ) from exc

logger = logging.getLogger(__name__)

# Running header / footer zones as a share of page height (A4: 55 pt and 785 pt of 842).
HEADER_MAX_FRAC = 0.065
FOOTER_MIN_FRAC = 0.932

# Footer: "Бүлэг 3-4" (chapter 3, page 4) or "Х.2-23" (appendix 2, page 23).
FOOTER_CHAPTER_RE = re.compile(r"^Бүлэг\s+(\d+)\s*-\s*\d+$")
FOOTER_APPENDIX_RE = re.compile(r"^Х\.?\s*(\d+)\s*-\s*\d+$")

# Section headings are bold: "3.3 Хөвөө", "3.2. Хөдөлгөөний ..." or title first: "Хөвөө 3.3".
_NUM = r"(?P<num>\d{1,2}(?:\.\d{1,2}){1,3})"
HEADING_NUM_FIRST_RE = re.compile(rf"^{_NUM}\.?\s+(?P<title>\S.{{1,150}})$")
HEADING_TITLE_FIRST_RE = re.compile(rf"^(?P<title>\S.{{1,150}}?)\s+{_NUM}\.?$")
CHAPTER_HEADING_RE = re.compile(r"^БҮЛЭГ\s+(?P<num>\d+)\.?\s*(?P<title>.*)$")
TABLE_TITLE_RE = re.compile(r"^Хүснэгт\s+\S+")
NOT_A_HEADING_RE = re.compile(r"^(Хүснэгт|Зураг|Жишээ|Тайлбар)\b")

# Markers in page text: detected headings, and where each table sits (index into tables).
# section_parser.parse_marked_heading and chunking_service read them; plain_text() removes them.
HEADING_MARK = "§ "
TABLE_MARK = "¤ TABLE "

# Long tables are split so one chunk stays a reasonable size for the LLM.
TABLE_CHUNK_MAX_CHARS = 2400


def _clean_text(text: str) -> str:
    # PostgreSQL text fields reject NUL; some PDFs embed them in extracted strings.
    return text.replace("\x00", "").replace("\u0000", "")


@dataclass
class PageExtract:
    page_number: int
    text: str
    tables: list[str]
    chapter: str | None = None  # from the page footer
    chapter_title: str | None = None
    headings: list[str] = field(default_factory=list)  # "3.3. Хөвөө", for reports


@dataclass
class _Line:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    bold: bool


def _page_lines(page: "fitz.Page") -> list[_Line]:
    lines: list[_Line] = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            text = " ".join("".join(s["text"] for s in line["spans"]).split())
            bold = all(s["flags"] & 16 or "Bold" in s["font"] for s in spans)
            x0, y0, x1, y1 = line["bbox"]
            lines.append(_Line(x0, y0, x1, y1, _clean_text(text), bold))
    return lines


def _group_rows(lines: list[_Line], tolerance: float = 3.0) -> list[list[_Line]]:
    """Group lines that sit on the same visual row (same y), ordered left to right."""
    rows: list[list[_Line]] = []
    for line in sorted(lines, key=lambda l: (l.y0, l.x0)):
        if rows and abs(rows[-1][0].y0 - line.y0) <= tolerance:
            rows[-1].append(line)
        else:
            rows.append([line])
    return [sorted(r, key=lambda l: l.x0) for r in rows]


def _row_text(row: list[_Line]) -> str:
    return " ".join(l.text for l in row).strip()


def _detect_heading(row: list[_Line]) -> str | None:
    """Return "3.3. Хөвөө" for a bold numbered heading row, else None."""
    if not all(l.bold for l in row):
        return None
    text = _row_text(row)
    m = CHAPTER_HEADING_RE.match(text)
    if m:
        title = m.group("title").strip(" .") or f"Бүлэг {m.group('num')}"
        return f"{m.group('num')}. {title}"
    m = HEADING_NUM_FIRST_RE.match(text) or HEADING_TITLE_FIRST_RE.match(text)
    if not m:
        return None
    title = m.group("title").strip(" .")
    if NOT_A_HEADING_RE.match(title) or not re.search(r"[А-Яа-яӨөҮүЁё]{2}", title):
        return None
    return f"{m.group('num')}. {title}"


def _is_toc_page(rows: list[list[_Line]]) -> bool:
    return sum(1 for r in rows if "....." in _row_text(r)) >= 5


def _in_rects(line: _Line, rects: list["fitz.Rect"]) -> bool:
    cx, cy = (line.x0 + line.x1) / 2, (line.y0 + line.y1) / 2
    return any(r.x0 - 2 <= cx <= r.x1 + 2 and r.y0 - 2 <= cy <= r.y1 + 2 for r in rects)


def _cell_text(words: list[tuple], rect: tuple | None) -> str:
    """Text of one table cell, read from the page's word layer (keeps "3.75" intact)."""
    if not rect:
        return ""
    x0, y0, x1, y1 = rect
    inside = [
        w for w in words
        if x0 <= (w[0] + w[2]) / 2 <= x1 and y0 <= (w[1] + w[3]) / 2 <= y1
    ]
    inside.sort(key=lambda w: (round(w[1] / 3), w[0]))
    return " ".join(w[4] for w in inside).strip()


def _merge_header(parts: list[str]) -> str:
    """Join header pieces from stacked rows, skipping repeats of merged cells."""
    merged = ""
    for part in parts:
        part = part.strip()
        if not part or part in merged:
            continue
        merged = part if merged and merged in part else f"{merged} {part}".strip()
    return merged


def _has_number(text: str) -> bool:
    return bool(re.search(r"\d", text))


def _table_title(table_rect: "fitz.Rect", rows: list[list[_Line]], page_number: int) -> str:
    """Find "Хүснэгт 3.2. ..." just above the table (or just below it)."""
    above = [
        r for r in rows
        if TABLE_TITLE_RE.match(_row_text(r)) and table_rect.y0 - 90 <= r[0].y1 <= table_rect.y0 + 3
    ]
    if above:
        return _row_text(max(above, key=lambda r: r[0].y1))
    below = [
        r for r in rows
        if TABLE_TITLE_RE.match(_row_text(r)) and table_rect.y1 - 3 <= r[0].y0 <= table_rect.y1 + 40
    ]
    if below:
        return _row_text(min(below, key=lambda r: r[0].y0))
    return f"Хүснэгт (х. {page_number})"


def _table_to_chunks(table, words: list[tuple], title: str, page_number: int) -> list[str]:
    """Render a table as one sentence per row, with column names, split into chunk-sized parts."""
    grid = [[_cell_text(words, c) for c in row.cells] for row in table.rows]
    grid = [r for r in grid if any(r)]
    if not grid:
        return []
    ncols = max(len(r) for r in grid)
    grid = [r + [""] * (ncols - len(r)) for r in grid]

    # Header = stacked rows before the first row that has a number outside the first column.
    first_data = next(
        (i for i, r in enumerate(grid) if i > 0 and any(_has_number(c) for c in r[1:])),
        1,
    )
    # A row of numbers under the header with an empty first cell is a sub-header ("40 50 60" km/h).
    while first_data < len(grid) - 1 and not grid[first_data][0] and any(_has_number(c) for c in grid[first_data][1:]):
        first_data += 1
    header_rows = [list(r) for r in grid[:first_data]]
    for r in header_rows:
        # One title spanning several columns ("Тооцоот хурд (км/ц)") applies to each of them.
        filled = [j for j in range(1, ncols) if r[j]]
        if len(filled) == 1:
            for j in range(filled[0] + 1, ncols):
                r[j] = r[filled[0]]
    headers = [_merge_header([r[j] for r in header_rows]) or f"Багана {j + 1}" for j in range(ncols)]

    # Not a real data table (paragraph in a box, table of contents, unreadable header):
    # return nothing, so its text stays in the normal page text instead.
    cells = [c for r in grid for c in r if c]
    if ncols < 2 or len(grid) - first_data < 1:
        return []
    if max(len(c) for c in cells) > 400 or sum("....." in c for c in cells) >= 2:
        return []
    if sum(h.startswith("Багана ") for h in headers) > ncols // 2:
        return []

    lines: list[str] = []
    label = ""
    for r in grid[first_data:]:
        label = r[0] or label
        # A numeric first column ("80") needs its column name to make sense: "Тооцоот хурд (км/ц) 80".
        shown = f"{headers[0]} {label}" if _has_number(label) and not headers[0].startswith("Багана") else label
        if ncols == 1:
            lines.append(r[0])
            continue
        parts = [f"{headers[j]}: {r[j]}" for j in range(1, ncols) if r[j]]
        if parts:
            lines.append(f"{shown} — " + "; ".join(parts) if shown else "; ".join(parts))
    if not lines:
        return []

    head = f"{title} (х. {page_number})"
    if headers and ncols > 1:
        head += "\nБаганууд: " + " | ".join(headers)
    chunks: list[str] = []
    current: list[str] = []
    for line in lines:
        if current and len(head) + sum(len(x) + 1 for x in current) + len(line) > TABLE_CHUNK_MAX_CHARS:
            chunks.append(head + "\n" + "\n".join(current))
            current = []
        current.append(line)
    chunks.append(head + "\n" + "\n".join(current))
    return [_clean_text(c) for c in chunks]


def _extract_page(page: "fitz.Page", page_number: int, extract_tables: bool) -> PageExtract:
    lines = _page_lines(page)
    header_max_y = page.rect.height * HEADER_MAX_FRAC
    footer_min_y = page.rect.height * FOOTER_MIN_FRAC

    chapter = chapter_title = None
    footer = [l for l in lines if l.y0 >= footer_min_y]
    for l in footer:
        m = FOOTER_CHAPTER_RE.match(l.text) or FOOTER_APPENDIX_RE.match(l.text)
        if m:
            chapter = m.group(1) if FOOTER_CHAPTER_RE.match(l.text) else f"Х{m.group(1)}"
    titles = [l.text for l in footer if not (FOOTER_CHAPTER_RE.match(l.text) or FOOTER_APPENDIX_RE.match(l.text))]
    if titles:
        chapter_title = " ".join(titles)

    body = [l for l in lines if header_max_y < l.y0 < footer_min_y]
    all_rows = _group_rows(body)

    tables: list[str] = []
    table_rects: list["fitz.Rect"] = []
    table_parts: list[list[int]] = []  # per table rect: indexes of its chunk strings in `tables`
    if extract_tables:
        try:
            found = page.find_tables().tables
            words = page.get_text("words")
            for table in found:
                rect = fitz.Rect(table.bbox)
                title = _table_title(rect, all_rows, page_number)
                rendered = [c for c in _table_to_chunks(table, words, title, page_number) if c not in tables]
                if rendered:
                    table_rects.append(rect)
                    table_parts.append(list(range(len(tables), len(tables) + len(rendered))))
                    tables.extend(rendered)
        except Exception as exc:
            logger.warning("Table extraction failed page %s: %s", page_number, exc)

    # Body text without the table areas (tables are stored separately, row by row).
    rows = _group_rows([l for l in body if not _in_rects(l, table_rects)])
    # Remember where each table sits so chunking can label it with the right section.
    table_positions = [(rect.y0, i) for i, rect in enumerate(table_rects)]
    detected = [_detect_heading(row) for row in rows]
    n_headings = sum(1 for h in detected if h)
    toc = _is_toc_page(rows) or (n_headings >= 8 and n_headings >= 0.4 * len(rows))
    out: list[str] = []
    headings: list[str] = []
    pending = sorted(table_positions)
    for row, heading in zip(rows, detected):
        while pending and pending[0][0] <= row[0].y0:
            out.extend(f"{TABLE_MARK}{k}" for k in table_parts[pending.pop(0)[1]])
        heading = None if toc else heading
        if heading:
            headings.append(heading)
            out.append(HEADING_MARK + heading)
        else:
            out.append(_row_text(row))
    for _, idx in pending:
        out.extend(f"{TABLE_MARK}{k}" for k in table_parts[idx])
    return PageExtract(
        page_number=page_number,
        text=_clean_text("\n".join(out)),
        tables=tables,
        chapter=chapter,
        chapter_title=chapter_title,
        headings=headings,
    )


def plain_text(text: str) -> str:
    """Page text without table markers and heading marks (for storing / display)."""
    lines = [l for l in text.splitlines() if not l.startswith(TABLE_MARK)]
    return "\n".join(l[len(HEADING_MARK):] if l.startswith(HEADING_MARK) else l for l in lines)


BOOKMARK_CHAPTER_RE = re.compile(r"^Б-(\d+)\.?\s*(.*?)\s*(?:\bR)?\s*$")
BOOKMARK_APPENDIX_RE = re.compile(r"^(\d+)-р хавсралт\.?\s*(.*?)\s*(?:\bR)?\s*$")


def _chapters_from_bookmarks(doc: "fitz.Document") -> dict[int, tuple[str, str]]:
    """Map page -> (chapter, title) from top-level chapter bookmarks ("Б-3. ...", "2-р хавсралт. ...")."""
    starts: list[tuple[int, str, str]] = []
    for level, title, page in doc.get_toc():
        m = BOOKMARK_CHAPTER_RE.match(title.strip())
        if m:
            starts.append((page, m.group(1), m.group(2).strip()))
            continue
        m = BOOKMARK_APPENDIX_RE.match(title.strip())
        if m:
            starts.append((page, f"Х{m.group(1)}", m.group(2).strip()))
    starts.sort()
    mapping: dict[int, tuple[str, str]] = {}
    for i, (start, chapter, title) in enumerate(starts):
        end = starts[i + 1][0] - 1 if i + 1 < len(starts) else len(doc)
        for page in range(start, end + 1):
            mapping[page] = (chapter, title)
    return mapping


def extract_pdf_pages(pdf_path: str, *, extract_tables: bool = True) -> list[PageExtract]:
    doc = fitz.open(pdf_path)
    total = len(doc)
    logger.info("PDF opened: %s pages", total)
    pages: list[PageExtract] = []
    try:
        bookmarks = _chapters_from_bookmarks(doc)
        last_chapter: tuple[str | None, str | None] = (None, None)
        for idx in range(total):
            page_num = idx + 1
            if page_num == 1 or page_num % 50 == 0 or page_num == total:
                logger.info("Extracting page %s/%s", page_num, total)
            try:
                extract = _extract_page(doc[idx], page_num, extract_tables)
            except Exception as exc:
                logger.error("Page extraction failed page %s: %s", page_num, exc)
                extract = PageExtract(page_number=page_num, text="", tables=[])
            if bookmarks:
                if page_num in bookmarks:
                    chapter, title = bookmarks[page_num]
                    extract.chapter = chapter
                    extract.chapter_title = title or extract.chapter_title
                else:
                    extract.chapter = extract.chapter_title = None
            elif extract.chapter:
                last_chapter = (extract.chapter, extract.chapter_title)
            else:
                extract.chapter, extract.chapter_title = last_chapter
            pages.append(extract)
    finally:
        doc.close()
    return pages
