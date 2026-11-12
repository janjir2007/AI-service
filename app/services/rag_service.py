from __future__ import annotations

import logging
import re

from psycopg2.extensions import connection as PgConnection

from app.config import get_settings
from app.services.facts_answer import (
    compose_answer,
    compose_overview,
    exact_match_order,
    is_overview_question,
    answer_type_ok,
    measure_from_facts,
    table_lookup,
    validate_facts,
    validate_overview,
)
from app.services.book_catalog import book_info, citation_label, preferred_filenames
from app.services.answer_compose import (
    answer_headline,
    best_lead_for_query,
    best_sentences_for_hit,
    extractive_answer,
    format_labor_answer,
    is_degenerate,
    is_why_question,
    labor_rows_for_query,
    primary_measurement,
    rationale_after_lead,
    rerank_hits_for_query,
    sanitize_answer,
)
from app.services.llm_service import get_llm_provider
from app.services.query_enhance import direct_answer_from_hits, retrieval_relevant
from app.services.answer_guard import unsupported_numbers
from app.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)

_NO_DIRECT_ANSWER = (
    "Энэ баримтад асуултад шууд хариулсан хэсэг олдсонгүй. "
    "Асуултаа илүү тодорхой бичээрэй (жишээ нь: замын ангилал, «урьдах хурд», хуудас)."
)

_SECTION_IN_TEXT = re.compile(
    r"(?<![\d.])(\d+(?:\.\d+)+)\.\s+([^\n\d]{3,160})"
)


def _source_from_hit(hit: dict) -> dict:
    content = hit.get("content") or ""
    m = _SECTION_IN_TEXT.search(content)
    section = m.group(1) if m else hit.get("section")
    title = m.group(2).strip() if m else hit.get("title")
    meta = book_info(hit.get("filename"), hit.get("file_path"))
    return {
        "page": hit["page"],
        "section": section,
        "title": title,
        "filename": meta["filename"],
        "book": meta["book"],
        "code": meta["code"],
        "book_id": meta["book_id"],
    }


def _llm_chat_enabled(provider: str, chat_use_llm: bool) -> bool:
    if not chat_use_llm:
        return False
    return provider in ("openai", "ollama", "mock")


class RagService:
    def __init__(self) -> None:
        self.retrieval = RetrievalService()
        self.settings = get_settings()
        self.llm = get_llm_provider()

    def search(
        self,
        conn: PgConnection,
        query: str,
        top_k: int,
        filenames: list[str] | None = None,
    ) -> list[dict]:
        results = self.retrieval.search(conn, query, top_k=top_k, filenames=filenames)
        return [
            {
                "content": r["content"],
                "page": r["page"],
                "chapter": r["chapter"],
                "section": r["section"],
                "title": r["title"],
                "filename": r.get("filename") or "",
                "score": round(r["score"], 4),
            }
            for r in results
        ]

    def chat(
        self,
        conn: PgConnection,
        message: str,
        top_k: int = 8,
        filenames: list[str] | None = None,
    ) -> dict:
        hits = self.retrieval.search(conn, message, top_k=top_k, filenames=filenames)
        if not hits:
            return {
                "answer": "Баримтад энэ асуулттай холбоотой хангалттай мэдээлэл олдсонгүй.",
                "sources": [],
                "books": [],
                "primary_value": None,
                "primary_unit": None,
                "headline": None,
            }

        hits = rerank_hits_for_query(hits, message)
        lead_pack = best_lead_for_query(hits, message)
        relevant = retrieval_relevant(message, lead_pack)
        search_hits = list(hits)  # before same-page removal; the table lookup needs every table
        if lead_pack:
            lead_hit = lead_pack[2]
            lead_key = (lead_hit.get("filename"), lead_hit.get("page"))
            hits = [lead_hit] + [
                h
                for h in hits
                if (h.get("filename"), h.get("page")) != lead_key
            ]
        extractive = sanitize_answer(extractive_answer(hits, _source_from_hit, message))
        lead_sentence = lead_pack[1] if lead_pack else ""
        labor_rows = labor_rows_for_query(hits, message) if preferred_filenames(message) else []
        labor_text = sanitize_answer(format_labor_answer(labor_rows, _source_from_hit)) if labor_rows else ""
        measure = primary_measurement(lead_sentence) if lead_sentence else primary_measurement(extractive)
        if labor_rows:
            measure = (labor_rows[0]["value"], labor_rows[0]["unit"])
            headline = labor_rows[0]["name"]
        else:
            headline = answer_headline(message, lead_sentence) if lead_sentence else None
        provider = self.settings.llm_provider.lower()
        use_llm = _llm_chat_enabled(provider, self.settings.chat_use_llm)

        answer = ""
        if use_llm:
            context_blocks = []
            # Only the top chunks go to the LLM; the first (lead) chunk gets a bigger budget.
            llm_hits = hits[: self.settings.llm_context_chunks]
            for i, h in enumerate(llm_hits):
                limit = self.settings.llm_lead_chunk_chars if i == 0 else self.settings.llm_chunk_chars
                meta = book_info(h.get("filename"))
                context_blocks.append(
                    {
                        "book": meta["book"],
                        "code": meta["code"],
                        "filename": meta["filename"],
                        "page": h["page"],
                        "chapter": h["chapter"],
                        "section": h["section"],
                        "title": h["title"],
                        "content_type": h["content_type"],
                        "content": h["content"][:limit],
                    }
                )
            try:
                if self.settings.answer_mode == "facts":
                    order = exact_match_order(message, context_blocks)
                    context_blocks = [context_blocks[i] for i in order]
                    llm_hits = [llm_hits[i] for i in order]
                if self.settings.answer_mode == "facts" and is_overview_question(message):
                    raw_points = self.llm.chat_overview(message, context_blocks)
                    logger.info("LLM overview: %s", raw_points)
                    points = validate_overview(raw_points, context_blocks)
                    if not points and context_blocks:
                        points = [
                            {"text": s, "block": context_blocks[0]}
                            for s in best_sentences_for_hit(llm_hits[0], message, limit=3)
                            if s
                        ]
                    if points:
                        answer = compose_overview(points, message)
                        relevant = True
                    else:
                        answer = _NO_DIRECT_ANSWER
                    llm_out = ""
                elif self.settings.answer_mode == "facts":
                    try:
                        table_hits = self.retrieval.search(
                            conn, message, top_k=5, filenames=filenames, tables_only=True
                        )
                    except Exception as exc:
                        logger.warning("Table search failed: %s", exc)
                        table_hits = []
                    seen_tables = set()
                    table_source = []
                    for h in search_hits + table_hits:
                        key = (h.get("filename"), h.get("page"), (h.get("content") or "")[:80])
                        if key not in seen_tables:
                            seen_tables.add(key)
                            table_source.append(h)
                    table_blocks = [
                        {
                            **book_info(h.get("filename")),
                            "page": h["page"],
                            "section": h["section"],
                            "title": h["title"],
                            "content_type": h["content_type"],
                            "content": h["content"],
                        }
                        for h in table_source
                        if h.get("content_type") == "table"
                    ]
                    facts = table_lookup(message, table_blocks)
                    if facts and not answer_type_ok(message, facts["value"], facts["unit"]):
                        facts = None
                    if facts:
                        logger.info("Table lookup: %s | %s %s", facts["subject"] or "(whole column)", facts["value"], facts["unit"])
                    else:
                        raw_facts = self.llm.chat_facts(message, context_blocks)
                        logger.info("LLM facts: %s", raw_facts)
                        facts = validate_facts(raw_facts, context_blocks, message)
                    if facts:
                        answer = compose_answer(facts, message)
                        measure = measure_from_facts(facts)
                        relevant = True
                    else:
                        answer = _NO_DIRECT_ANSWER
                    llm_out = ""
                else:
                    llm_out = sanitize_answer(self.llm.chat(message, context_blocks))
                if llm_out and not is_degenerate(llm_out):
                    answer = llm_out
                    if self.settings.answer_number_check:
                        context_texts = [
                            " ".join(str(v) for v in block.values() if v is not None)
                            for block in context_blocks
                        ]
                        bad = unsupported_numbers(answer, context_texts, message)
                        if bad:
                            # A number the book chunks don't contain: don't show a guessed answer.
                            logger.warning("LLM answer blocked, numbers not in context: %s", bad)
                            answer = _NO_DIRECT_ANSWER
            except Exception as exc:
                logger.warning("LLM chat failed, falling back to extractive: %s", exc)

        if labor_text and (not answer or answer == _NO_DIRECT_ANSWER or not re.search(r"хүн\s*цаг", answer, re.I)):
            answer = labor_text
            relevant = True

        if not answer:
            if relevant and extractive:
                answer = extractive
            elif extractive and not self.settings.answer_number_check:
                # Even low-relevance extractive is better than nothing
                answer = extractive
            else:
                answer = _NO_DIRECT_ANSWER

        direct = direct_answer_from_hits(message, hits, best_sentences_for_hit)
        if self.settings.answer_number_check:
            # Only fill an empty answer, and only when search found relevant pages. The old rule
            # also fired on "хурдны зам" (expressway) and swapped in unrelated speed sentences.
            use_direct = bool(direct) and relevant and not answer
        else:
            use_direct = bool(direct) and (
                not answer or answer == _NO_DIRECT_ANSWER or not re.search(r"\d", answer)
            )
        if use_direct:
            answer = direct
            relevant = True
            measure = primary_measurement(direct) or measure

        # If LLM answered but missed key measurements, append extractive supplement
        if answer and answer != _NO_DIRECT_ANSWER and answer != extractive:
            ext_measure = primary_measurement(extractive) if extractive else None
            if ext_measure and not measure:
                measure = ext_measure
            if (
                ext_measure
                and not self.settings.answer_number_check
                and not re.search(r"\d+[.,]\d+", answer)
                and extractive
            ):
                # LLM gave text but no numbers; blend in extractive data
                answer = answer.rstrip() + "\n\n" + extractive

        sources = []
        if relevant:
            seen = set()
            for h in hits:
                src = _source_from_hit(h)
                key = (src.get("filename"), src["page"], src.get("section"))
                if key in seen:
                    continue
                seen.add(key)
                sents = best_sentences_for_hit(h, message, limit=2)
                if is_why_question(message) and sents:
                    sents = sents[:1] + rationale_after_lead(h, sents[0], message)
                excerpt = sanitize_answer(
                    "\n".join(sents) if sents else (h.get("content") or "")[:600],
                    max_len=600,
                )
                src_measure = primary_measurement(excerpt) if excerpt else None
                row = {**src, "excerpt": excerpt}
                matching_labor = [
                    lr for lr in labor_rows
                    if lr.get("filename") == src.get("filename") and lr.get("page") == src.get("page")
                ]
                if matching_labor:
                    row["value"] = matching_labor[0]["value"]
                    row["unit"] = matching_labor[0]["unit"]
                elif src_measure and not labor_rows:
                    row["value"], row["unit"] = src_measure
                sources.append(row)

        if labor_rows and sources:
            top_fn = labor_rows[0].get("filename")
            top_pg = labor_rows[0].get("page")
            sources.sort(
                key=lambda s: (
                    2 if s.get("filename") == top_fn and s.get("page") == top_pg else 0,
                    1 if s.get("filename") == top_fn else 0,
                ),
                reverse=True,
            )

        pv, pu = (measure if measure and relevant else (None, None))
        books = []
        seen_books = set()
        for src in sources:
            bid = src.get("book_id") or src.get("filename")
            if not bid or bid in seen_books:
                continue
            seen_books.add(bid)
            books.append(
                {
                    "book_id": src.get("book_id"),
                    "filename": src.get("filename"),
                    "code": src.get("code"),
                    "title": src.get("book"),
                    "label": citation_label(src),
                }
            )
        return {
            "answer": answer,
            "sources": sources[:top_k],
            "books": books,
            "primary_value": pv,
            "primary_unit": pu,
            "headline": headline if relevant else None,
        }
