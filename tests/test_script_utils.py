from app.services.script_utils import cyrillic_to_latin, detect_script, latin_to_cyrillic, reply_script


def test_detect_script():
    assert detect_script("Сайн байна уу") == "cyrillic"
    assert detect_script("sain bnu") == "latin"
    assert detect_script("Явган zamын өргөн") == "mixed"
    # Roman numerals are not Latin text
    assert detect_script("II ангиллын зам") == "cyrillic"
    assert detect_script("123 ?") == "none"


def test_reply_script_follows_majority():
    assert reply_script("sain bnu") == "latin"
    assert reply_script("Явган zamын өргөн хэд вэ") == "cyrillic"


def test_latin_to_cyrillic_common_phrases():
    assert latin_to_cyrillic("sain bnu") == "сайн байна уу"
    assert latin_to_cyrillic("yavgan zamiin urgun hed ve") == "явган замын өргөн хэд вэ"
    assert latin_to_cyrillic("Явган zamын өргөн") == "Явган замын өргөн"


def test_latin_to_cyrillic_keeps_numbers_and_roman():
    assert latin_to_cyrillic("II angilliin zam 3,75 m") == "II ангиллын зам 3,75 м"


def test_cyrillic_to_latin():
    assert cyrillic_to_latin("Сайн байна уу! Танд юугаар туслах вэ?") == "Sain baina uu! Tand yuugaar tuslah ve?"
    assert cyrillic_to_latin("Өглөөний мэнд") == "Ugluunii mend"
    assert cyrillic_to_latin("замын өргөн 3,75 м") == "zamiin urgun 3,75 m"
