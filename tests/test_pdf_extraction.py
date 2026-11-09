import os

import pytest

from app.services.pdf_service import extract_pdf_pages


@pytest.mark.skipif(
    not os.environ.get("PDF_PATH") or not os.path.isfile(os.environ.get("PDF_PATH", "")),
    reason="PDF_PATH not set or file missing",
)
def test_extract_first_page_has_text():
    pages = extract_pdf_pages(os.environ["PDF_PATH"])
    assert len(pages) >= 1
    assert pages[0].page_number == 1
