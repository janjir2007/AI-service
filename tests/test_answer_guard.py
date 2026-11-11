from app.services.answer_guard import numbers_in, unsupported_numbers

Q11 = "100 км/цаг хурдтай замд зогсох үеийн үзэгдэх зай хэд байх ёстой вэ?"
TABLE_21 = (
    "Хүснэгт 2.1. Зогсох үеийн үзэгдэх хамгийн бага зай (х. 94)\n"
    "Тооцоот хурд (км/ц) 100 — Бодит хурд (км/ц): 90; Хамгийн бага зогсох үеийн үзэгдэх зай (төсөллөлтөөр) (м): 200"
)
RADIUS_TABLE = (
    "Хүснэгт 2.15. Түр замын эргэц үзүүлэлт (%) (х. 133)\n"
    "Радиус (м) 185 — Тооцоот хурд (км/ц) 40: 3.7; Тооцоот хурд (км/ц) 50: 4.6"
)


def test_invented_number_is_flagged():
    answer = "100 км/цаг хурдтай замд зогсох үеийн үзэгдэх зай 185 метр байх ёстой."
    assert unsupported_numbers(answer, [TABLE_21], Q11) == ["185"]


def test_number_from_unrelated_line_is_flagged():
    # 185 exists in the context, but only as a curve radius: not about stopping sight distance.
    answer = "Зогсох үеийн үзэгдэх зай 185 метр байх ёстой."
    assert unsupported_numbers(answer, [RADIUS_TABLE, TABLE_21], Q11) == ["185"]


def test_number_from_matching_line_passes():
    answer = "100 км/цаг үед зогсох үеийн үзэгдэх зай 200 м байна (хуудас 94, хэсэг 2.2)."
    assert unsupported_numbers(answer, [RADIUS_TABLE, TABLE_21], Q11) == []


def test_bus_stop_answer_to_charging_question_is_flagged():
    q = "Цахилгаан автомашины цэнэглэх станц хоорондын зай хэд байх ёстой вэ?"
    context = ["Автобусны буудал хоорондын зай нь дор хаяж 3.5 км байх нь тохиромжтой."]
    answer = "Автобусны буудал хоорондын зай нь дор хаяж 3.5 км байх нь тохиромжтой."
    assert unsupported_numbers(answer, context, q) == ["3.5"]


def test_table_row_with_column_names_passes():
    q = "Хурдны замын хөдөлгөөний зурвасын өргөн хэд вэ?"
    context = ["Хурдны замд — Хөдөлгөөний зурвасын өргөн (м): 3.75; Өгсөх, гүйцэж түрүүлэх зурвасын өргөн (м): 3.75"]
    assert unsupported_numbers("Хурдны замын зурвасын өргөн 3.75 м.", context, q) == []


def test_wrapped_sentence_uses_neighbour_lines():
    q = "Явган хүний замын өргөн хамгийн багадаа хэд вэ?"
    context = ["Явган хүний замын өргөнийг тооцохдоо\nхамгийн багадаа 1.2 м байхаар төсөллөнө."]
    assert unsupported_numbers("Явган хүний замын өргөн 1.2 м.", context, q) == []


def test_citations_list_markers_and_question_numbers_are_ignored():
    answer = "1. Гол хариулт: 200 м.\n2. Эх сурвалж: хуудас 94, хэсэг 2.2.1, Хүснэгт 2.1"
    assert unsupported_numbers(answer, [TABLE_21], Q11) == []


def test_same_number_different_format():
    assert numbers_in("3,50 ба 3.0") == {"3.5", "3"}
    assert unsupported_numbers("өргөн 3.0 м", ["өргөн 3 м"]) == []


def test_mixed_script_question_still_matches():
    # "zogsoh uyiin uzegdeh" is converted by rules to "зогсох уыиин узэгдэх" (у instead of ү).
    q = "80 км/ц хурдтай замд зогсох уыиин узэгдэх заи хэд вэ?"
    row = "Тооцоот хурд (км/ц) 80 — Хамгийн бага зогсох үеийн үзэгдэх зай (төсөллөлтөөр) (м): 140"
    assert unsupported_numbers("Зогсох үеийн үзэгдэх зай 140 м.", [row], q) == []
