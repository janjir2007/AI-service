from __future__ import annotations

from dataclasses import dataclass

from app.services.section_parser import (
    SectionContext,
    apply_section_to_lines,
    detect_content_type,
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


def build_chunks_from_pages(
    pages: list[tuple[int, str, list[str]]],
    start_index: int = 0,
) -> tuple[list[ChunkDraft], int, SectionContext]:
    """pages: (page_number, text, table_texts)."""
    chunks: list[ChunkDraft] = []
    chunk_index = start_index
    context = SectionContext()

    for page_number, text, table_texts in pages:
        lines = text.splitlines()
        line_pairs, context = apply_section_to_lines(lines, page_number, context)
        paragraphs: list[str] = []
        buffer: list[str] = []
        buffer_tokens = 0

        def emit_paragraph(para: str) -> None:
            nonlocal buffer, buffer_tokens, chunk_index, chunks
            ctype = detect_content_type(para)
            tokens = estimate_tokens(para)
            if buffer_tokens + tokens > TARGET_MAX_TOKENS and buffer:
                draft, chunk_index = _flush_buffer(
                    buffer, page_number, context, chunk_index, "text"
                )
                if draft:
                    chunks.append(draft)
                overlap = buffer[-1:] if buffer else []
                buffer = overlap + [para]
                buffer_tokens = sum(estimate_tokens(x) for x in buffer)
            else:
                buffer.append(para)
                buffer_tokens += tokens

        for line, line_ctx in line_pairs:
            context = line_ctx
            heading = parse_section_heading(line)
            if heading:
                if buffer:
                    draft, chunk_index = _flush_buffer(
                        buffer, page_number, context, chunk_index, "text"
                    )
                    if draft:
                        chunks.append(draft)
                    buffer, buffer_tokens = [], 0
                header = f"{heading.section}. {heading.title}"
                chunks.append(
                    ChunkDraft(
                        document_id=None,
                        page_number=page_number,
                        chapter=heading.chapter,
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
            if line.strip():
                paragraphs.append(line.strip())

        for para in _split_paragraphs("\n".join(paragraphs)):
            emit_paragraph(para)

        if buffer:
            draft, chunk_index = _flush_buffer(
                buffer, page_number, context, chunk_index, "text", allow_small=True
            )
            if draft:
                chunks.append(draft)
            buffer, buffer_tokens = [], 0

        for table_text in table_texts:
            title_line = table_text.split("\n", 1)[0]
            chunks.append(
                ChunkDraft(
                    document_id=None,
                    page_number=page_number,
                    chapter=context.chapter,
                    section=context.section,
                    section_title=context.title,
                    chunk_index=chunk_index,
                    content=table_text,
                    content_type="table",
                    token_estimate=estimate_tokens(table_text),
                )
            )
            chunk_index += 1

    return chunks, chunk_index, context
