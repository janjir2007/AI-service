from app.services.answer_compose import (
    answer_headline,
    extractive_answer,
    is_degenerate,
    sanitize_answer,
)


def test_detects_lll_garbage():
    assert is_degenerate("төсөLLL" * 50)


def test_sanitize_strips_degenerate():
    assert sanitize_answer("төсөLLL" * 50) == ""


def test_detects_comma_list_loop():
    unit = "зам, давхар зам, барилгын зам, хурдны авто зам, "
    assert is_degenerate(unit * 20)


def test_sanitize_compresses_long_repeat():
    unit = "Хурдны авто замын зааглах зурвасын ердийн өргөн. "
    out = sanitize_answer(unit * 15)
    assert "ердийн өргөн" in out
    assert out.count("ердийн өргөн") <= 2


def test_extractive_prefers_matching_sentence():
    query = (
        "Туслах зам болон чигээрээ явах хөдөлгөөний урсгалтай замуудын "
        "хоорондох өндөрсөлтийн зөрүү нь ойролцоогоор"
    )
    hit = {
        "page": 394,
        "content": (
            "Зураг 8.7. Туслах замуудтай, өндөрлөсөн хурдны авто замын ердийн болон\n"
            "хязгаарлагдмал хөндлөн огтлол\n"
            "Хиймэл байгууламж дээрх өндөрлөсөн хэсгийн замын зурвас газрын зохион\n"
            "байгуулалт нь асар их уян хатан байх ёстой.\n"
            "Туслах зам болон чигээрээ явах хөдөлгөөний урсгалтай замуудын хоорондох\n"
            "өндөрсөлтийн зөрүү нь ойролцоогоор 6.0 м байна. Энэхүү хэсэгт зааглах зурвасын\n"
            "өргөн нь 3.0-6.6 м байхаар өгөгдсөн.\n"
        ),
    }

    def src(_):
        return {"page": 394, "section": "8.7", "title": "Туслах замууд"}

    out = extractive_answer([hit], src, query)
    assert "6.0 м байна" in out
    assert out.find("6.0 м") < 250


def test_headline_for_which_road_question():
    q = "ямар зам дээр 3.6-9.0 м өргөн зааглах зурвас"
    sent = (
        "Олон зурваст зам дээр 3.6-9.0 м өргөн зааглах зурвас байгуулах нь "
        "нэг төвшингийн уулзвар дээр зүүн гар тийш эргэх тээврийн хэрэгсэлд "
        "хамгаалагдсан сул зай гаргаж өгөх боломжийг хангана."
    )
    assert answer_headline(q, sent) == "Олон зурваст зам"


def test_why_question_includes_rationale():
    query = "18 м-ээс өргөн зааглах зурвас тохиромжгүй. яагаад?"
    hit = {
        "page": 433,
        "content": (
            "Дохиололтой эсвэл ойрын хугацаанд дохиолол тавих нэг төвшингийн уулзвар дээр\n"
            "18 м-ээс өргөн зааглах зурвас төсөллөх нь тохиромжгүй байна.  Зааглах зурвас\n"
            "өргөсөх тусам дохиоллын үүрэг, ач холбогдол буурна.  Учир нь жолооч нар өргөн\n"
            "зааглах зурвасыг туулах гэж илүү цаг зарцуулдаг.\n"
        ),
    }

    def src(_):
        return {"page": 433, "section": "9.5", "title": "Зааглах зурвас"}

    out = extractive_answer([hit], src, query)
    assert "Тайлбар (баримт)" in out
    assert "дохиоллын үүрэг" in out
    assert "Учир нь" in out
