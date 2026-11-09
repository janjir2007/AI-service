import logging

from fastapi import FastAPI

from app.api.routes import chat, documents, health, rag, standards_pdf
from app.config import get_settings

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(title="RCOS NORM AI Service", version="0.1.0")
app.include_router(health.router)
app.include_router(rag.router)
app.include_router(chat.router)
app.include_router(standards_pdf.router)
app.include_router(documents.router)
