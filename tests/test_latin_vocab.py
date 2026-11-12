from app.services.script_utils import latin_to_cyrillic


def test_vowels_fixed_by_book_vocabulary():
    assert latin_to_cyrillic("yerunhii zuil") == "ерөнхий зүйл"
    assert latin_to_cyrillic("tugs nuhtsul") == "төгс нөхцөл"
    assert latin_to_cyrillic("hungun tergend shiljuuleh") == "хөнгөн тэргэнд шилжүүлэх"


def test_ending_fixed_by_book_vocabulary():
    assert latin_to_cyrillic("ursgaliin") == "урсгалын"


def test_capital_input_works():
    assert latin_to_cyrillic("Yerunhii") == "ерөнхий"


def test_unknown_word_left_alone():
    assert latin_to_cyrillic("qwrtz") == "квртз"


def test_cyrillic_untouched():
    assert latin_to_cyrillic("ерунхий") == "ерунхий"


def test_soft_sign_fixed_by_book_vocabulary():
    assert latin_to_cyrillic("haritsaa") == "харьцаа"
    assert latin_to_cyrillic("barij") == "барьж"
    assert latin_to_cyrillic("baigali") == "байгаль"
