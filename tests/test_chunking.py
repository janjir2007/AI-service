from app.services.chunking_service import build_chunks_from_pages, estimate_tokens


def test_build_chunks_preserves_section():
    pages = [
        (
            1,
            "3.2. Хөдөлгөөний зурвасын өргөн\n\nII ангиллын замын хөдөлгөөний зурвас 7.0 м байна.",
            [],
        )
    ]
    chunks, _, _ = build_chunks_from_pages(pages)
    assert chunks
    assert any(c.section == "3.2" for c in chunks)
    assert any("7.0" in c.content for c in chunks)


def test_estimate_tokens_positive():
    assert estimate_tokens("hello") >= 1
