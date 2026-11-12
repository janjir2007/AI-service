from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.db import get_connection
from app.db_schema import missing_tables, schema_status
from app.models.schemas import ChatBook, ChatRequest, ChatResponse, ChatSource
from app.services.rag_service import _NO_DIRECT_ANSWER
from app.services.intent_router import (
    SMALL_TALK,
    RouteResult,
    classify_message,
    off_topic_reply,
    small_talk_reply,
    to_reply_script,
)
from app.services.rag_service import RagService

router = APIRouter(prefix="/api/v1", tags=["chat"])


def _reply(route: RouteResult, answer_cyrillic: str, **extra) -> ChatResponse:
    """Build the response: answer in the user's script, Cyrillic copy always included."""
    settings = get_settings()
    return ChatResponse(
        answer=to_reply_script(answer_cyrillic, route, settings.reply_in_user_script),
        answer_cyrillic=answer_cyrillic,
        intent=route.intent,
        input_script=route.input_script,
        reply_script=route.reply_script if settings.reply_in_user_script else "cyrillic",
        normalized_message=route.normalized,
        sources=extra.pop("sources", []),
        **extra,
    )


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    route = classify_message(body.message)

    # 1) Small talk: template reply, no database, no LLM.
    if route.intent in SMALL_TALK:
        return _reply(route, small_talk_reply(route))

    # 2) Road (or unknown) question: RAG over the norm books, searched in Cyrillic.
    try:
        with get_connection() as conn:
            missing = missing_tables(conn)
            if missing:
                st = schema_status(conn)
                raise HTTPException(
                    status_code=503,
                    detail=(
                        f"AI schema not ready (missing: {', '.join(missing)}). "
                        f"{st.get('hint') or 'Run python scripts/run_migrations.py'}"
                    ),
                )
            result = RagService().chat(
                conn,
                route.query,
                top_k=body.top_k,
                filenames=body.filenames,
            )
    except HTTPException:
        raise
    except Exception as exc:
        msg = str(exc)
        if "ai_document_chunks" in msg and "does not exist" in msg:
            msg = (
                "Table ai_document_chunks does not exist. Run: "
                "python scripts/run_migrations.py && python -m app.ingest --all"
            )
        raise HTTPException(status_code=503, detail=msg) from exc

    # 3) Nothing relevant found for a non-road question: polite off-topic reply.
    # Not a road question and RAG found no direct answer: polite roads-only reply.
    if route.intent == "unknown" and (not result["sources"] or result.get("answer") == _NO_DIRECT_ANSWER):
        route.intent = "off_topic"
        return _reply(route, off_topic_reply())

    answer = result["answer"]
    if route.greeted:
        answer = f"{route.salute} {answer}"

    return _reply(
        route,
        answer,
        sources=[ChatSource(**s) for s in result["sources"]],
        books=[ChatBook(**b) for b in result.get("books") or []],
        primary_value=result.get("primary_value"),
        primary_unit=result.get("primary_unit"),
        headline=result.get("headline"),
    )
