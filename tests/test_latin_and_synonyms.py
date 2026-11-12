from app.services.query_enhance import enhance_search_query
from app.services.script_utils import latin_to_cyrillic


def test_latin_question_with_i_rules():
    assert latin_to_cyrillic("hurdni zam hamgiin bagadaa heden egneetei baih ystoi ve?") == (
        "хурдны зам хамгийн багадаа хэдэн эгнээтэй байх ёстой вэ?"
    )


def test_known_words_unchanged():
    assert latin_to_cyrillic("sain bnu") == "сайн байна уу"
    assert latin_to_cyrillic("yavgan zamiin urgun hed ve") == "явган замын өргөн хэд вэ"


def test_egnee_synonym_added():
    q = enhance_search_query("Хурдны зам хэдэн эгнээтэй байх вэ?")
    assert "хөдөлгөөний зурвас" in q


def test_real_speed_question_still_expanded():
    q = enhance_search_query("80 км/ц хурдтай замд зогсох зай хэд вэ?")
    assert "хурдны хязгаар" in q
