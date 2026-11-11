from app.services.facts_answer import (
    compose_answer,
    compose_overview,
    exact_match_order,
    is_overview_question,
    validate_facts,
    validate_overview,
)

NOTE = "Зурвасын өргөнийг замын ангиллаар тогтооно."
BLOCKS = [
    {"code": "БНбД", "page": 447, "section": "9.3.3", "title": "",
     "content": "Хөвөөний бэхжүүлсэн зурвас 2.4-3.6 м."},
    {"code": "БНбД", "page": 139, "section": "3.2", "title": "Хүснэгт 3.2 Хөдөлгөөний зурвас",
     "content": "Хурдны зам: 3.75 м\nГол зам: 3.5-3.6 м\nХуримтлуулагч зам: 3.0-3.6 м\n" + NOTE},
]


def _facts(**kw):
    base = {"found": True, "chunk": 2, "subject": "Гол зам", "value": "3.5-3.6", "unit": "м",
            "cases": [], "note": ""}
    base.update(kw)
    return base


def test_keeps_supported_value_and_repoints_wrong_chunk():
    f = validate_facts(_facts(value="3.5–3.6", chunk=1), BLOCKS)
    assert f is not None and f["block"]["page"] == 139


def test_rejects_invented_value():
    assert validate_facts(_facts(value="4.2"), BLOCKS) is None


def test_not_found_returns_none():
    assert validate_facts(_facts(found=False), BLOCKS) is None


def test_drops_invented_case_and_paraphrased_note():
    f = validate_facts(_facts(
        cases=[{"case": "Хурдны зам", "value": "3.75", "unit": "м"},
               {"case": "Орон нутгийн зам", "value": "2.8", "unit": "м"}],
        note="Өргөнийг ангиллаас хамааруулна.",
    ), BLOCKS)
    assert [c["case"] for c in f["cases"]] == ["Хурдны зам"]
    assert f["note"] == ""


def test_keeps_copied_note():
    f = validate_facts(_facts(note=NOTE), BLOCKS)
    assert f["note"] == NOTE


def test_unit_not_doubled():
    f = validate_facts(_facts(value="3.5-3.6 м"), BLOCKS)
    text = compose_answer(f)
    assert text.startswith("Гол зам: **3.5-3.6 м**")
    assert "м м" not in text


def test_drops_duplicate_and_sentence_cases():
    f = validate_facts(_facts(cases=[
        {"case": "Гол замаас дээшхи ангиллын замын хөдөлгөөний зурвасын өргөн нь ийм байна", "value": "3.75", "unit": "м"},
        {"case": "Гол зам давхар", "value": "3.5-3.6", "unit": "м"},
    ]), BLOCKS)
    assert f["cases"] == []


def test_copied_passage_in_value_becomes_note():
    f = validate_facts(_facts(value=NOTE, unit="м"), BLOCKS)
    assert f["value"] == "" and f["note"] == NOTE
    text = compose_answer(f)
    assert text.startswith("**Гол зам**")
    assert "Тайлбар: " + NOTE in text


def test_invented_passage_in_value_rejected():
    assert validate_facts(_facts(value="Энэ бол номонд байхгүй урт өгүүлбэр бөгөөд зохиосон юм."), BLOCKS) is None


def test_compose_card_with_source_from_metadata():
    f = validate_facts(_facts(cases=[{"case": "Хурдны зам", "value": "3.75", "unit": "м"}]), BLOCKS)
    text = compose_answer(f)
    assert text.startswith("Гол зам: **3.5-3.6 м**")
    assert "• Хурдны зам — 3.75 м" in text
    assert text.endswith("Эх сурвалж: БНбД, х. 139, Хүснэгт 3.2")


LONG_BLOCKS = [
    {"code": "БНбД", "page": 499, "section": "11.3.5", "title": "",
     "content": "Явган хүний замын өргөн хамгийн багадаа 1.2 м байна. "
                "Хүн их явдаг газарт явган замыг хөдөлгөөний эрчмээр тооцож өргөсгөнө. "
                "Явган замын хучилт тэгш, гулгаагүй байна.\nХүснэгт 11.4"},
]


def test_headline_from_question():
    f = validate_facts(_facts(), BLOCKS)
    text = compose_answer(f, "Гол замын хөдөлгөөний зурвасын өргөн хэд вэ?")
    assert text.startswith("Гол замын хөдөлгөөний зурвасын өргөн **3.5-3.6 м** байна.")


def test_no_headline_for_overview_question():
    f = validate_facts(_facts(), BLOCKS)
    assert compose_answer(f, "Хурдны замын талаар мэдээлэл өг").startswith("Гол зам: **3.5-3.6 м**")


def test_generic_subject_dropped():
    f = validate_facts(_facts(subject="замын ангилал"), BLOCKS)
    assert compose_answer(f).startswith("**3.5-3.6 м**")


def test_note_extended_with_following_sentences():
    f = validate_facts(_facts(chunk=1, value="1.2", subject="Явган зам",
                              note="Явган хүний замын өргөн хамгийн багадаа 1.2 м байна."), LONG_BLOCKS)
    assert "эрчмээр тооцож өргөсгөнө." in f["note"]
    assert "гулгаагүй байна." in f["note"]
    assert "Хүснэгт" not in f["note"]


def test_overview_detection():
    assert is_overview_question("Явган замын талаар мэдээлэл өг")
    assert is_overview_question("Хурдны зам гэж юу вэ?")
    assert not is_overview_question("Явган замын өргөн хэд вэ?")


def test_overview_validate_and_compose():
    raw = {"found": True, "points": [
        {"chunk": 1, "text": "Явган хүний замын өргөн хамгийн багадаа 1.2 м байна."},
        {"chunk": 3, "text": "Хүн их явдаг газарт явган замыг хөдөлгөөний эрчмээр тооцож өргөсгөнө."},
        {"chunk": 1, "text": "Явган зам заавал улаан өнгөтэй байх ёстой гэж заасан."},
        {"chunk": 1, "text": "Явган хүний замын өргөн хамгийн багадаа 1.2 м байна."},
        {"chunk": 3, "text": NOTE},
    ]}
    blocks = LONG_BLOCKS + BLOCKS
    points = validate_overview(raw, blocks)
    assert [p["block"]["page"] for p in points] == [499, 499, 139]
    text = compose_overview(points, "Явган замын талаар мэдээлэл өг")
    assert text.startswith("**Явган замын талаар:**")
    assert text.endswith("Эх сурвалж: БНбД, х. 499, хэсэг 11.3.5; х. 139, Хүснэгт 3.2")


def test_overview_not_found():
    assert validate_overview({"found": False, "points": []}, BLOCKS) == []


def test_yes_no_and_meaning_questions():
    assert is_overview_question("Хөдөө орон нутгийн замын хөдөлгөөний зурвас 3.5 м-ээс бага байж болох уу?")
    assert is_overview_question("2А-ХрЗ-ЗХГ-2-70 гэдэг нь юу гэсэн үг вэ?")
    assert not is_overview_question("Хөдөө, орон нутгийн замын хөвөөний өргөн хэд вэ?")


def test_meaning_question_heading():
    points = [{"text": NOTE, "block": BLOCKS[1]}]
    assert compose_overview(points, "2А-ХрЗ-ЗХГ-2-70 гэдэг нь юу гэсэн үг вэ?").startswith("**2А-ХрЗ-ЗХГ-2-70:**")


def test_latin_road_words():
    from app.services.script_utils import latin_to_cyrillic
    assert latin_to_cyrillic("zogsoh uyiin uzegdeh zai hed ve") == "зогсох үеийн үзэгдэх зай хэд вэ"


TABLE_BLOCK = {"code": "БНбД", "page": 93, "section": "2.2", "title": "Хүснэгт 2.1", "content_type": "table",
               "content": "Тооцоот хурд 60: Зогсох үеийн үзэгдэх зай (м): 85\n"
                          "Тооцоот хурд 80: Зогсох үеийн үзэгдэх зай (м): 140"}
Q80 = "80 км/ц хурдтай замд зогсох үеийн үзэгдэх зай хэд вэ?"


def test_row_check_rejects_value_from_other_row():
    assert validate_facts(_facts(value="85", unit="", subject="", chunk=1), [TABLE_BLOCK], Q80) is None


def test_row_check_keeps_right_row_and_fills_unit():
    f = validate_facts(_facts(value="140", unit="", subject="", chunk=1), [TABLE_BLOCK], Q80)
    assert f is not None and f["unit"] == "м"


def test_overview_drops_fragments():
    raw = {"found": True, "points": [
        {"chunk": 1, "text": "нь 3.0-3.6 м\nЗурвасын өргөнийг замын ангиллаар тогтооно."},
        {"chunk": 2, "text": NOTE},
    ]}
    points = validate_overview(raw, BLOCKS)
    assert [p["text"] for p in points] == [NOTE]


def test_exact_match_order():
    blocks = [{"content": "Хурдны зам"}, {"content": "2А-ХрЗ-ЗХГ-2-70 гэдэг нь хуримтлуулагч зам"}]
    assert exact_match_order("2А-ХрЗ-ЗХГ-2-70 гэдэг нь юу гэсэн үг вэ?", blocks) == [1, 0]
    assert exact_match_order("Явган замын өргөн хэд вэ?", blocks) == [0, 1]
