"""CLI: python -m app.ingest [--force] [--all] [pdf ...]"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from app.config import get_settings
from app.services.ingestion_service import IngestionService


def _print_stats(stats: dict) -> None:
    print(f"Document: {stats['document']}")
    print(f"Pages: {stats['pages']}")
    print(f"Words: {stats['words']}")
    print(f"Sections detected: {stats['sections_detected']}")
    print(f"Chunks created: {stats['chunks_created']}")
    print(f"Tables detected: {stats['tables_detected']}")
    print(f"Embeddings created: {stats['embeddings_created']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest standards PDF into RAG store")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-ingest if the same PDF hash already exists",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Ingest every PDF in ai-service/data (mybook.pdf, 8325.pdf, 8326.pdf)",
    )
    parser.add_argument("pdfs", nargs="*", help="Optional PDF paths to ingest")
    args = parser.parse_args()
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    paths: list[str] = list(args.pdfs)
    if args.all:
        data_dir = Path(__file__).resolve().parents[1] / "data"
        paths.extend(sorted(str(p) for p in data_dir.glob("*.pdf")))
    if not paths:
        if settings.pdf_path:
            paths = [settings.pdf_path]
        else:
            print("PDF_PATH is not set and no PDF arguments given.", file=sys.stderr)
            return 1

    seen: set[str] = set()
    uniq: list[str] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            uniq.append(p)

    failed = 0
    for pdf_path in uniq:
        print(f"--- Ingest {pdf_path}")
        try:
            stats = IngestionService().run(pdf_path, force=args.force)
        except RuntimeError as exc:
            print(str(exc))
            continue
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            failed += 1
            continue
        except Exception as exc:
            logging.exception("Ingestion failed")
            print(f"Ingestion failed: {exc}", file=sys.stderr)
            failed += 1
            continue
        _print_stats(stats)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
