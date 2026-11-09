from app.services.section_parser import parse_section_heading, detect_content_type


def test_section_heading_nested():
    ctx = parse_section_heading("3.2. Хөдөлгөөний зурвасын өргөн")
    assert ctx is not None
    assert ctx.chapter == "3"
    assert ctx.section == "3.2"
    assert ctx.title == "Хөдөлгөөний зурвасын өргөн"


def test_section_heading_long_number():
    line = "3.8. Төсөллөлтийн ангилалд зориулсан стандарт хөндлөн огтлолууд"
    ctx = parse_section_heading(line)
    assert ctx is not None
    assert ctx.section == "3.8"


def test_rejects_bare_number():
    assert parse_section_heading("12.") is None


def test_table_content_type():
    assert detect_content_type("Хүснэгт 5.2\nA | B") == "table"
