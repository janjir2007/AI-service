from app.services.facts_answer import compose_answer, table_lookup, unknown_class_term

C1 = "Хөдөлгөөний зурвасын өргөн (м)"
T32 = {"code": "БНбД", "page": 139, "section": "3.2", "title": "", "content_type": "table",
       "content": "Хүснэгт 3.2. Жишиг зурвасын өргөн (х. 139)\n"
                  f"Баганууд: Замын төрөл | {C1}\n"
                  f"Хурдны замд — {C1}: 3.75\nГол зам — {C1}: 3.5-3.6\nХуримтлуулагч зам — {C1}: 3.0-3.6"}


def test_roman_class_detected_and_removed():
    rest, note = unknown_class_term("II ангиллын замын хөдөлгөөний зурвасын өргөн хэд вэ?")
    assert rest == "Замын хөдөлгөөний зурвасын өргөн хэд вэ?"
    assert "«II ангилал»" in note and "Зэрэг 2 (Хуримтлуулагч зам)" in note


def test_numbered_class_detected():
    assert unknown_class_term("3-р ангиллын замын налуу хэд вэ?")[1]


def test_book_terms_untouched():
    q = "Зэрэг 2 замын хөдөлгөөний зурвасын өргөн хэд вэ?"
    assert unknown_class_term(q) == (q, "")


def test_cleaned_question_lists_all_classes():
    rest, _ = unknown_class_term("II ангиллын замын хөдөлгөөний зурвасын өргөн хэд вэ?")
    f = table_lookup(rest, [T32])
    text = compose_answer(f, rest)
    assert "• Хуримтлуулагч зам — 3.0-3.6 м" in text
