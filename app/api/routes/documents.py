from fastapi import APIRouter, HTTPException

from app.db import get_connection
from app.db_schema import document_inventory, missing_tables

router = APIRouter(prefix="/api/v1", tags=["documents"])


@router.get("/documents")
def list_documents() -> dict:
    try:
        with get_connection() as conn:
            if missing_tables(conn):
                raise HTTPException(status_code=503, detail="AI schema not ready")
            docs = document_inventory(conn)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)[:300]) from exc
    return {"count": len(docs), "documents": docs}
