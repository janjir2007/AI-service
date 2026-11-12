from app.services.facts_answer import answer_type_ok, expected_kind, validate_facts

Q22 = "Хурдны зам хамгийн багадаа хэдэн хөдөлгөөний зурвастай байх ёстой вэ?"
P40 = {"code": "БНбД", "page": 40, "section": "1.5.10", "title": "", "content_type": "text",
       "content": "Хурдны авто замын чиглэл тус бүрт хамгийн багадаа хоёр чигээрээ явах хөдөлгөөний "
                  "зориулалттай зурвас байх шаардлагатай."}
P386 = {"code": "БНбД", "page": 386, "section": "8.4.1", "title": "", "content_type": "text",
        "content": "Зургаа эсвэл илүү олон зурвастай хурдны авто замын хувьд хамгийн бага өргөн нь 6.6 м байна."}


def test_kinds():
    assert expected_kind(Q22) == "count"
    assert expected_kind("Хурдны замын хөдөлгөөний зурвасын өргөн хэд вэ?") == "length"
    assert expected_kind("80 км/ц хурдтай замд зогсох үеийн үзэгдэх зай хэд вэ?") == "length"
    assert expected_kind("Хурдны замын тухай мэдээлэл өг") is None


def test_width_rejected_for_count_question():
    assert not answer_type_ok(Q22, "6.6", "м")
    f = {"found": True, "chunk": 2, "subject": "", "value": "6.6", "unit": "м", "cases": [], "note": ""}
    assert validate_facts(f, [P40, P386], Q22) is None


def test_count_supported_by_number_word():
    f = {"found": True, "chunk": 1, "subject": "", "value": "2", "unit": "", "cases": [], "note": ""}
    assert validate_facts(f, [P40, P386], Q22) is not None


def test_length_question_keeps_meters():
    assert answer_type_ok("Хурдны замын хөдөлгөөний зурвасын өргөн хэд вэ?", "3.75", "м")


def test_drainage_is_not_distance():
    q = "Ус зайлуулах сувгийн дагуу налуу хэд байх ёстой вэ?"
    assert expected_kind(q) is None
    assert answer_type_ok(q, "0.3", "%")
