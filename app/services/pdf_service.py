from __future__ import annotations

import logging
from dataclasses import dataclass

try:
    import fitz  # PyMuPDF
except ImportError as exc:
    raise ImportError(
        "PyMuPDF is required for PDF ingest (import fitz). "
        "In ai-service venv run: pip install -r requirements.txt  "
        "or: pip install 'PyMuPDF>=1.24.0'"
    ) from exc

logger = logging.getLogger(__name__)


def _clean_text(text: str) -> str:
    # PostgreSQL text fields reject NUL; some PDFs embed them in extracted strings.
    return text.replace("\x00", "").replace("\u0000", "")


@dataclass
class PageExtract:
    page_number: int
    text: str
    tables: list[str]


def _table_to_text(table: fitz.Table) -> str:
    rows = table.extract()
    if not rows:
        return ""
    lines: list[str] = []
    for row in rows:
        cells = [(c or "").strip().replace("\n", " ") for c in row]
        if any(cells):
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def extract_pdf_pages(pdf_path: str, *, extract_tables: bool = True) -> list[PageExtract]:
    doc = fitz.open(pdf_path)
    total = len(doc)
    logger.info("PDF opened: %s pages", total)
    pages: list[PageExtract] = []
    try:
        for idx in range(total):
            page_num = idx + 1
            if page_num == 1 or page_num % 50 == 0 or page_num == total:
                logger.info("Extracting page %s/%s", page_num, total)
            page = doc[idx]
            try:
                text = _clean_text(page.get_text("text") or "")
                tables: list[str] = []
                if extract_tables:
                    try:
                        finder = page.find_tables()
                        for t_idx, table in enumerate(finder.tables, start=1):
                            rendered = _table_to_text(table)
                            if rendered.strip():
                                tables.append(
                                    _clean_text(f"TABLE {page_num}.{t_idx}\n{rendered}")
                                )
                    except Exception as exc:
                        logger.warning("Table extraction failed page %s: %s", page_num, exc)
                pages.append(PageExtract(page_number=page_num, text=text, tables=tables))
            except Exception as exc:
                logger.error("Page extraction failed page %s: %s", page_num, exc)
                pages.append(PageExtract(page_number=page_num, text="", tables=[]))
    finally:
        doc.close()
    return pages
