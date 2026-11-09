from app.services.answer_compose import best_sentences_for_hit
from app.services.query_enhance import (
    direct_answer_from_hits,
    enhance_search_query,
    is_misleading_excerpt,
    retrieval_relevant,
)


def test_enhance_fixes_signal_typo_and_adds_speed_terms():
    q = "Гэрлэн дохиог хурдны хязгаар хэд байдаг вэ?"
    out = enhance_search_query(q)
    assert "гэрэлэн дохио" in out.lower()
    assert "урьдах хурд" in out


def test_misleading_ramp_metering_not_speed_limit():
    query = "Гэрлэн дохиог хурдны хязгаар хэд байдаг вэ?"
    lead = (
        "Орчны замын гэрлэн дохиог орцын төгсгөлийн өмнө тавьж "
        "хурдны авто зам руу нэвтрэх тээврийн хэрэгслийн тоог хязгаарлана."
    )
    assert is_misleading_excerpt(query, lead)


def test_direct_answer_finds_speed_on_signal_roads():
    query = "Гэрлэн дохиог хурдны хязгаар хэд байдаг вэ?"
    hit = {
        "page": 219,
        "content": (
            "4.4.3 Дохиоллын зохицуулалт "
            "Гэрлэн дохиог хурдны хязгаар 80 км/цаг ба түүнээс доош байх авто замуудад хэрэглэнэ."
        ),
    }
    out = direct_answer_from_hits(query, [hit], best_sentences_for_hit)
    assert out is not None
    assert "80" in out
    assert "219" in out


def test_retrieval_not_relevant_for_misleading_lead():
    query = "Гэрлэн дохиог хурдны хязгаар хэд байдаг вэ?"
    lead = (
        "Орчны замын гэрлэн дохиог орцын төгсгөлийн өмнө тавьж "
        "хурдны авто зам руу нэвтрэх тээврийн хэрэгслийн тоог хязгаарлана."
    )
    pack = (12.0, lead, {"page": 361, "content": lead})
    assert not retrieval_relevant(query, pack)
