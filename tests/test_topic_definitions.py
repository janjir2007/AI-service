from app.services.topic_answer import (
    compose_topic_answer,
    definition_in_sentence,
    glossary_definition,
    match_sections,
    parse_glossary,
    stem,
    stems,
)

HOVOO_DEF = "Хөвөө гэдэг нь зорчих хөдөлгөөний зурвастай залгаа, замын хэсэг юм."


def test_stem_case_forms():
    assert stem("хөвөөний") == stem("Хөвөө") == "хөвөө"
    assert stem("хүний") == "хүн"
    assert stem("замын") == "зам"
    assert stem("хучилтын") == stem("хучилт")
    assert stems("Хөвөөн дээрх") == ("хөвөө", "дээрх")


def test_definition_plain():
    assert definition_in_sentence(HOVOO_DEF, stems("хөвөө")) == HOVOO_DEF


def test_definition_after_merged_heading():
    assert definition_in_sentence("3.3 Хөвөө " + HOVOO_DEF, stems("хөвөөний")) == HOVOO_DEF


def test_definition_rejects_narrower_term():
    s = ("Тасралтгүй шугамтай үеийн үзэгдэх зай гэдэг нь замын аль нэг хэсэгт гүйцэж "
         "түрүүлэхийг хориглосон хучилтын тэмдэглэгээ хийхийг тодорхойлоход ашиглана.")
    assert definition_in_sentence(s, stems("үзэгдэх зай")) is None


def test_definition_needs_gedeg_ni():
    assert definition_in_sentence("Хөвөө нь олон янзын үүрэг гүйцэтгэнэ.", stems("хөвөө")) is None


GLOSSARY_ROWS = [
    {"document_id": 1, "page_number": 574, "filename": "mybook.pdf", "file_path": "data/mybook.pdf",
     "content": "SIDEWALK - Явган хүний зам. Явган зорчигчдод зориулсан, замын зорчих хэсгийн\n\n"
                "залгаа буюу зэрэгцээ баригдсан зам.\n\nSIGHT DISTANCE - Үзэгдэх зай. Жолооч явж буй "
                "чигтээ зорчих үед өмнө нь үзэгдэж\n\nбайгаа зай.\n\n"},
    {"document_id": 1, "page_number": 575, "filename": "mybook.pdf", "file_path": "data/mybook.pdf",
     "content": "SPEED - Хурд. Цагийн нэгжид замын уртаар илэрхийлэгдэх хөдөлгөөний үзүүлэлт"},
]


def test_glossary_entries():
    entries = parse_glossary(GLOSSARY_ROWS)
    side = glossary_definition(entries, stems("явган хүний зам"))
    assert side["text"].startswith("Явган зорчигчдод зориулсан") and side["page"] == 574
    sight = glossary_definition(entries, stems("үзэгдэх зай"))
    assert "өмнө нь үзэгдэж байгаа зай" in sight["text"]
    speed = glossary_definition(entries, stems("хурд"))
    assert speed["page"] == 575 and speed["text"].startswith("Цагийн нэгжид")


def test_glossary_unknown_term():
    assert glossary_definition(parse_glossary(GLOSSARY_ROWS), stems("хөвөө")) is None


def _sec(section, title, p_from, p_to, n, doc=1):
    return {"document_id": doc, "filename": "mybook.pdf", "file_path": "data/mybook.pdf",
            "section": section, "section_title": title, "p_from": p_from, "p_to": p_to, "n": n}


SECTIONS = [
    _sec("3.2", "Хөдөлгөөний зурвас", 135, 139, 6),
    _sec("3.3", "Хөвөө", 139, 140, 4),
    _sec("3.3.1", "Хөвөөн дээрх хамгаалалтын иржгэр ховилтой зурвас", 140, 140, 2),
    _sec("3.3.2", "Хөвөөн дээрх хамгаалалтын зорсон ховилтой зурвас", 141, 144, 5),
    _sec("4.3.4", "Уулзварын хөдөлгөөний зурвас, хөвөөний өргөн", 206, 206, 2),
    _sec("9.3.8", "Унадаг дугуйн болон явган хүний зам", 449, 450, 3),
]


def test_section_topic_family():
    main, others = match_sections(SECTIONS, stems("хөвөөний"))
    assert main["section"] == "3.3" and (main["p_from"], main["p_to"]) == (139, 144)
    assert [o["section"] for o in others] == ["4.3.4"]


def test_scattered_topic_has_no_main():
    main, others = match_sections(SECTIONS, stems("явган хүний зам"))
    assert main is None
    assert [o["section"] for o in others] == ["9.3.8"]


def test_compose_section_answer():
    main, others = match_sections(SECTIONS, stems("хөвөө"))
    text = compose_topic_answer("Хөвөө", {"text": HOVOO_DEF, "page": 139, "glossary": False}, main, others)
    assert text.splitlines()[0] == "Хөвөө"
    assert f"Тодорхойлолт: {HOVOO_DEF} (х. 139)" in text
    assert "Бусад хэсэг: 4.3.4 Уулзварын хөдөлгөөний зурвас, хөвөөний өргөн (х. 206)" in text
    assert text.endswith("Дэлгэрэнгүй: хэсэг 3.3, х. 139–144")


def test_compose_glossary_answer():
    main, others = match_sections(SECTIONS, stems("явган хүний зам"))
    text = compose_topic_answer(
        "Явган хүний зам",
        {"text": "Явган зорчигчдод зориулсан зам.", "page": 574, "glossary": True},
        main, others,
    )
    assert "(Нэр томьёо, х. 574)" in text
    assert "Номд тусдаа бүлэг байхгүй. Дараах хэсгүүдэд дурдсан: 9.3.8 Унадаг дугуйн болон явган хүний зам (х. 449–450)" in text
    assert "Дэлгэрэнгүй" not in text


def test_latin_huni_single_i():
    from app.services.script_utils import latin_to_cyrillic
    assert latin_to_cyrillic("yavgan huni zam") == "явган хүний зам"


def test_mention_pattern():
    from app.services.topic_answer import mention_pattern
    assert mention_pattern("явган хүний зам") == r"\mявга[а-яөүё]*\s+хүн[а-яөүё]*\s+зам[а-яөүё]*"


def test_merge_scattered_title_first():
    from app.services.topic_answer import merge_scattered
    title = [_sec("9.3.8", "Унадаг дугуйн болон явган хүний зам", 449, 450, 3)]
    mentions = [_sec("9.3.8", "Унадаг дугуйн болон явган хүний зам", 449, 450, 3),
                _sec("8.4.9", "Зохицуулалттай эгнээ", 415, 419, 2),
                _sec("9.3.4", "Замын хажуугийн орчны төсөллөлт", 446, 447, 2)]
    assert [s["section"] for s in merge_scattered(title, mentions)] == ["9.3.8", "8.4.9", "9.3.4"]


def test_compose_list_only():
    text = compose_topic_answer("Хучилт", None, None, [_sec("5.1", "Хучилтын бүтэц", 300, 302, 4)])
    assert "Тодорхойлолт" not in text
    assert "Дараах хэсгүүдэд дурдсан: 5.1 Хучилтын бүтэц (х. 300–302)" in text


def test_latin_tumur():
    from app.services.script_utils import latin_to_cyrillic
    assert latin_to_cyrillic("tumur zam") == "төмөр зам"
    assert latin_to_cyrillic("tumriin zam") == "төмрийн зам"
