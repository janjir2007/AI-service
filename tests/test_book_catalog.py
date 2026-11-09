from app.services.book_catalog import book_info, citation_label, preferred_filenames
from app.services.answer_compose import (
    extractive_answer,
    format_source_ref,
    labor_rows_for_query,
)


def test_job_title_routes_to_estimate_norms():
    names = preferred_filenames("Геодезийн туслах ажилчин")
    assert names == ["8326.pdf", "8325.pdf"]
    assert preferred_filenames("явган замын өргөн") is None
    assert preferred_filenames("8325 төсөв") == ["8325.pdf", "8326.pdf"]


def test_maps_ingested_filenames():
    bnbd = book_info("mybook.pdf")
    assert bnbd["book_id"] == "bnbd-auto-road"
    assert "БАРИЛГЫН НОРМ" in bnbd["book"]

    a = book_info("8325.pdf")
    b = book_info("/var/www/road/ai-service/data/8326.pdf")
    assert a["book"] == b["book"]
    assert a["code"] == "8325"
    assert b["code"] == "8326"
    assert a["book_id"] == "azbn-8325"


def test_citation_includes_book_and_page():
    src = {
        **book_info("mybook.pdf"),
        "page": 120,
        "section": "8.3.2",
    }
    ref = format_source_ref(src, 120)
    assert "МОНГОЛ УЛСЫН БАРИЛГЫН НОРМ БА ДУРЭМ" in ref
    assert "хуудас 120" in ref
    assert "8.3.2" in ref
    assert citation_label(src).startswith("МОНГОЛ")


def test_labor_row_extracts_geodesy_helper():
    hit = {
        "page": 233,
        "filename": "8326.pdf",
        "content": (
            "Код: 25-24-116 Нэр: Лавлагааны гадас зоох "
            "Ажилчдын хөдөлмөр зарцуулалт Зэрэг Хүн цаг "
            "Геодезийн туслах ажилчин III 0.094 Рейкчин IV 0.047"
        ),
    }
    rows = labor_rows_for_query([hit], "Геодезийн туслах ажилчин")
    assert rows
    assert rows[0]["name"] == "Геодезийн туслах ажилчин"
    assert rows[0]["value"] == "0.094"
    assert rows[0]["grade"] == "III"
    assert rows[0]["filename"] == "8326.pdf"


def test_extractive_mentions_book_name():
    hit = {
        "page": 12,
        "filename": "8325.pdf",
        "content": (
            "Асфальт бетоны үеийн зузаан 5.0 см-ээс багагүй байна. "
            "Энэ шаардлага төсвийн жишиг нормын хүснэгтэд заасан."
        ),
    }

    def src(h):
        return {**book_info(h.get("filename")), "page": 12, "section": "4.1"}

    out = extractive_answer([hit], src, "асфальт бетоны үеийн зузаан хэд вэ")
    assert "5.0" in out
    assert "АВТО ЗАМЫН БАРИЛГЫН АЖЛЫН ТӨСВИЙН ЖИШИГ НОРМ" in out
    assert "8325" in out
