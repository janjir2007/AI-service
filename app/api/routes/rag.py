from fastapi import APIRouter, HTTPException

from app.db import get_connection
from app.models.schemas import RagSearchRequest, RagSearchResponse, RagSearchResult
from app.services.rag_service import RagService

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


@router.post("/search", response_model=RagSearchResponse)
def rag_search(body: RagSearchRequest) -> RagSearchResponse:
    try:
        with get_connection() as conn:
            results = RagService().search(conn, body.query, body.top_k)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return RagSearchResponse(
        results=[RagSearchResult(**r) for r in results],
    )
