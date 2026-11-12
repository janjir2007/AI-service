from app.services.facts_answer import compose_answer, table_lookup

C1 = "Хөдөлгөөний зурвасын өргөн (м)"
C2 = "Өгсөх, гүйцэж түрүүлэх зурвасын өргөн (м)"
C3 = "Эргэх, хурд авах, хурд хасах зурвас (м)"
T32 = {
    "code": "БНбД", "page": 139, "section": "3.2", "title": "Хөдөлгөөний зурвасын өргөн", "content_type": "table",
    "content": "Хүснэгт 3.2. Жишиг зурвасын өргөн (х. 139)\n"
               f"Баганууд: Замын төрөл | {C1} | {C2} | {C3}\n"
               f"Хурдны замд — {C1}: 3.75; {C2}: 3.75; {C3}: 3.5\n"
               f"Олон зурваст гол — {C1}: 3.5-3.6; {C2}: 3.5; {C3}: 3.5\n"
               f"Гол зам — {C1}: 3.5-3.6; {C2}: 3.5; {C3}: 3.5\n"
               f"Хуримтлуулагч зам — {C1}: 3.0-3.6; {C2}: 3.0-3.5; {C3}: 3.0-3.5",
}

D = "Хамгийн бага зогсох үеийн үзэгдэх зай (төсөллөлтөөр) (м)"
T21 = {
    "code": "БНбД", "page": 94, "section": "2.2.3", "title": "Зогсох үеийн үзэгдэх зай", "content_type": "table",
    "content": "Хүснэгт 2.1. Зогсох үеийн үзэгдэх хамгийн бага зай (х. 94)\n"
               f"Баганууд: Тооцоот хурд (км/ц) | Бодит хурд (км/ц) | Зай (м) | Тоормосны (м) зай | {D}\n"
               f"Тооцоот хурд (км/ц) 60 — Бодит хурд (км/ц): 60; Зай (м): 41.7; Тоормосны (м) зай: 41.7; {D}: 85\n"
               f"Тооцоот хурд (км/ц) 80 — Бодит хурд (км/ц): 80; Зай (м): 55.6; Тоормосны (м) зай: 81.2; {D}: 140",
}


def test_q01_row_and_column():
    q = "Хурдны замын хөдөлгөөний зурвасын өргөн хэд вэ?"
    f = table_lookup(q, [T32])
    assert f["value"] == "3.75" and f["unit"] == "м" and len(f["cases"]) == 3
    text = compose_answer(f, q)
    assert text.startswith("Хурдны замын хөдөлгөөний зурвасын өргөн **3.75 м** байна.")
    assert text.endswith("Эх сурвалж: БНбД, х. 139, Хүснэгт 3.2")


def test_q02_gol_zam_not_olon_zurvast():
    assert table_lookup("Гол замын хөдөлгөөний зурвасын өргөн хэд вэ?", [T32])["value"] == "3.5-3.6"


def test_q03_right_column():
    assert table_lookup("Хуримтлуулагч замын өгсөх зурвасын өргөн хэд вэ?", [T32])["value"] == "3.0-3.5"


def test_q04_whole_column():
    q = "Хөдөлгөөний зурвасын өргөн хэд вэ?"
    f = table_lookup(q, [T32])
    assert f["value"] == "" and len(f["cases"]) == 4
    text = compose_answer(f, q)
    assert text.startswith("**Хөдөлгөөний зурвасын өргөн:**")
    assert "• Хурдны замд — 3.75 м" in text and "• Хуримтлуулагч зам — 3.0-3.6 м" in text


def test_q19_number_row():
    f = table_lookup("80 км/ц хурдтай замд зогсох үеийн үзэгдэх зай хэд вэ?", [T21])
    assert f["value"] == "140" and f["unit"] == "м" and f["cases"] == []


def test_unrelated_question_not_answered():
    assert table_lookup("Явган замын өргөн хэд вэ?", [T32, T21]) is None


def test_number_without_matching_row_not_answered():
    assert table_lookup("100 км/ц хурдтай замд зогсох үеийн үзэгдэх зай хэд вэ?", [T21]) is None


T33 = {
    "code": "БНбД", "page": 140, "section": "3.3", "title": "Хөвөө", "content_type": "table",
    "content": "Хүснэгт 3.3. Хөвөөний өргөн (х. 140)\n"
               "Баганууд: Замын төрөл | Хөдөлгөөний зурвасын өргөн дэх хөвөө (м)\n"
               "Хурдны зам — Хөдөлгөөний зурвасын өргөн дэх хөвөө (м): 0.5\n"
               "Олон зурваст гол зам — Хөдөлгөөний зурвасын өргөн дэх хөвөө (м): 0.5\n"
               "Хуримтлуулагч зам — Хөдөлгөөний зурвасын өргөн дэх хөвөө (м): 1.5",
}


def test_column_only_needs_full_cover():
    # "гол" names a row this table does not have, so no whole-column answer
    assert table_lookup("Гол замын хөдөлгөөний зурвасын өргөн хэд вэ?", [T33]) is None
