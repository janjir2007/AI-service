from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.config import get_settings
from app.services.book_catalog import ALLOWED_PDFS, filename_from_path

router = APIRouter(prefix="/api/v1", tags=["standards"])


def _data_candidates(name: str) -> list[str]:
    settings = get_settings()
    here = Path(__file__).resolve().parents[3]  # ai-service/
    out: list[str] = []
    if settings.pdf_path.strip():
        parent = os.path.dirname(settings.pdf_path.strip())
        if parent:
            out.append(os.path.join(parent, name))
        if filename_from_path(settings.pdf_path) == name:
            out.append(settings.pdf_path.strip())
    out.append(str(here / "data" / name))
    return out


def resolve_ingested_pdf(filename: str | None) -> str | None:
    name = filename_from_path(filename) or "mybook.pdf"
    if name not in ALLOWED_PDFS:
        return None
    for path in _data_candidates(name):
        if path and os.path.isfile(path):
            return path
    return None


@router.get("/standards-pdf")
def download_standards_pdf(file: str | None = Query(default=None)):
    path = resolve_ingested_pdf(file)
    if not path:
        raise HTTPException(
            status_code=404,
            detail=(
                "PDF not found. Place mybook.pdf / 8325.pdf / 8326.pdf in "
                "ai-service/data or set PDF_PATH."
            ),
        )
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=os.path.basename(path) or "standards.pdf",
    )
