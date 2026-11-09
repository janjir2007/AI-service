import httpx
from fastapi import APIRouter

from app.config import get_settings
from app.db import get_connection
from app.db_schema import schema_status

router = APIRouter()


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    body: dict = {
        "status": "ok",
        "service": "rcos-norm-ai",
        "llm_provider": settings.llm_provider,
        "embedding_provider": settings.embedding_provider,
        "chat_use_llm": settings.chat_use_llm,
        "chat_mode": (
            "llm"
            if settings.chat_use_llm
            and settings.llm_provider.lower() in ("openai", "ollama", "mock")
            else "extractive"
        ),
    }
    if settings.llm_provider.lower() == "ollama" or settings.embedding_provider.lower() == "ollama":
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
                resp.raise_for_status()
                names = [m.get("name", "") for m in resp.json().get("models", [])]
                body["ollama"] = {"reachable": True, "models": names[:20]}
        except httpx.HTTPError:
            body["status"] = "degraded"
            body["ollama"] = {
                "reachable": False,
                "hint": "Start Ollama (ollama serve) and run scripts/pull_ollama_models.sh",
            }
    try:
        with get_connection() as conn:
            db = schema_status(conn)
        body["database"] = db
        if not db["schema_ok"]:
            body["status"] = "degraded"
    except Exception as exc:
        body["status"] = "degraded"
        body["database"] = {"schema_ok": False, "error": str(exc)[:300]}
    return body
