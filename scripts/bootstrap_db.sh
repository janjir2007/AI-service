#!/usr/bin/env bash
# Create ai_* tables (incl. ai_document_chunks) and ingest PDF. Run on api.rcos.mn VPS.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing ai-service/.env — copy .env.example and set DATABASE_URL (same as road/.env)."
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || {
  echo "Create venv: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
}

echo "==> Python deps (PyMuPDF / fitz for PDF ingest)"
pip install -q -r requirements.txt
python -c "import fitz" || {
  echo "ERROR: PyMuPDF (fitz) still missing after pip install."
  exit 1
}

echo "==> Migrations (pgvector + ai_document_chunks)"
python scripts/run_migrations.py

echo "==> Ingest PDF (PDF_PATH in .env)"
python -m app.ingest

echo "==> Done. Restart uvicorn/systemd, then:"
echo "    curl -s http://127.0.0.1:8000/health"
echo "    curl -s https://api.rcos.mn/api/norm-ai/health"
