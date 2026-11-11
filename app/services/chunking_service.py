from __future__ import annotations

from dataclasses import dataclass

from app.services.section_parser import (
    SectionContext,
    parse_marked_heading,
    parse_section_heading,
)

MIN_CHUNK_TOKENS = 120
TARGET_MAX_TOKENS = 1000
OVERLAP_TOKENS = 80


def _clean(text: str) -> str:
    return text.replace("\x00", "")


def estimate_tokens(text: str) -> int:
    # Rough heuristic for Mongolian/Latin mixed text (~4 chars per token).
    return max(1, len(text) // 4)


@dataclass
class ChunkDraft:
    document_id: int | None
    page_number: int
    chapter: str | None
    section: str | None
    section_title: str | None
    chunk_index: int
    content: str
    content_type: str
    token_estimate: int


def _split_paragraphs(text: str) -> list[str]:
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    if parts:
        return parts
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _flush_buffer(
    buffer: list[str],
    page_number: int,
    ctx: SectionContext,
    chunk_index: int,
    content_type: str,
    *,
    allow_small: bool = False,
) -> tuple[ChunkDraft | None, int]:
    if not buffer:
        return None, chunk_index
    content = _clean("\n\n".join(buffer).strip())
    if not content:
        return None, chunk_index
    tokens = estimate_tokens(content)
    if tokens < MIN_CHUNK_TOKENS and content_type == "text" and not allow_small:
        return None, chunk_index
    draft = ChunkDraft(
        document_id=None,
        page_number=page_number,
        chapter=ctx.chapter,
        section=ctx.section,
        section_title=ctx.title,
        chunk_index=chunk_index,
        content=content,
        content_type=content_type,
        token_estimate=tokens,
    )
    return draft, chunk_index + 1


TABLE_MARK = "¤ TABLE "


def build_chunks_from_pages(
    pages: list[tuple],
    start_index: int = 0,
    *,
    strict_headings: bool = False,
) -> tuple[list[ChunkDraft], int, SectionContext]:
    """pages: (page_number, text, table_texts) or (page_number, text, table_texts, chapter, chapter_title).

    Text is chunked in reading order, so each chunk carries the section it actually belongs to
    (not the last heading on its page). Tables are placed where their marker sits in the text.
    strict_headings=True only accepts headings marked by pdf_service ("§ 3.3. Хөвөө"); plain
    lines like "4. Босоо хоёр муруй" in a numbered list are then never treated as headings.
    """
    parse = parse_marked_heading if strict_headings else parse_section_heading
    chunks: list[ChunkDraft] = []
    chunk_index = start_index
    context = SectionContext()
    last_page_chapter: str | None = None

    for page in pages:
        page_number, text, table_texts = page[0], page[1], page[2]
        page_chapter = page[3] if len(page) > 3 else None
        page_chapter_title = page[4] if len(page) > 4 else None
        if page_chapter and page_chapter != last_page_chapter:
            # New chapter: drop the old section until this chapter's first heading appears.
            context = SectionContext(chapter=page_chapter, title=page_chapter_title, page=page_number)
        last_page_chapter = page_chapter or last_page_chapter
        used_tables: set[int] = set()
        buffer: list[str] = []
        buffer_tokens = 0

        def chapter_of(ctx: SectionContext) -> str | None:
            return page_chapter or ctx.chapter

        def flush(allow_small: bool) -> None:
            nonlocal buffer, buffer_tokens, chunk_index
            draft, chunk_index = _flush_buffer(
                buffer, page_number, context, chunk_index, "text", allow_small=allow_small
            )
            if draft:
                draft.chapter = chapter_of(context)
                chunks.append(draft)
            buffer, buffer_tokens = [], 0

        def add_table(k: int) -> None:
            nonlocal chunk_index
            if k >= len(table_texts) or k in used_tables:
                return
            used_tables.add(k)
            table_text = table_texts[k]
            chunks.append(
                ChunkDraft(
                    document_id=None,
                    page_number=page_number,
                    chapter=chapter_of(context),
                    section=context.section,
                    section_title=context.title,
                    chunk_index=chunk_index,
                    content=table_text,
                    content_type="table",
                    token_estimate=estimate_tokens(table_text),
                )
            )
            chunk_index += 1

        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith(TABLE_MARK):
                try:
                    add_table(int(line[len(TABLE_MARK):]))
                except ValueError:
                    pass
                continue
            heading = parse(line)
            if heading:
                if buffer:
                    flush(allow_small=True)  # text before the heading keeps the previous section
                context = SectionContext(
                    chapter=heading.chapter,
                    section=heading.section,
                    title=heading.title,
                    page=page_number,
                )
                header = f"{heading.section}. {heading.title}"
                chunks.append(
                    ChunkDraft(
                        document_id=None,
                        page_number=page_number,
                        chapter=chapter_of(context),
                        section=heading.section,
                        section_title=heading.title,
                        chunk_index=chunk_index,
                        content=header,
                        content_type="text",
                        token_estimate=estimate_tokens(header),
                    )
                )
                chunk_index += 1
                continue
            tokens = estimate_tokens(line)
            if buffer and buffer_tokens + tokens > TARGET_MAX_TOKENS:
                overlap = buffer[-1:]
                flush(allow_small=False)
                buffer = overlap[:]
                buffer_tokens = sum(estimate_tokens(x) for x in buffer)
            buffer.append(line)
            buffer_tokens += tokens

        if buffer:
            flush(allow_small=True)
        for k in range(len(table_texts)):  # tables without a marker (older callers)
            add_table(k)

    return chunks, chunk_index, context
