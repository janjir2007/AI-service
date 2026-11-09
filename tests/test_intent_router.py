import pytest

from app.services.intent_router import classify_message, small_talk_reply, to_reply_script


@pytest.mark.parametrize(
    "message,intent",
    [
        ("Hi", "greeting"),
        ("hello!", "greeting"),
        ("Sain bnu?", "greeting"),
        ("Сайн байна уу", "greeting"),
        ("ugluunii mend", "greeting"),
        ("bayarlalaa", "thanks"),
        ("Баярлалаа!", "thanks"),
        ("bayartai", "bye"),
        ("Чи хэн бэ?", "identity"),
        ("who are you", "identity"),
        ("chi yu hiij chadah ve?", "capabilities"),
        ("yavgan zamiin urgun hed ve", "road"),
        ("II ангиллын замын хөдөлгөөний зурвасын өргөн хэд вэ?", "road"),
        ("Маргааш цаг агаар ямар байх вэ?", "unknown"),
    ],
)
def test_intents(message, intent):
    assert classify_message(message).intent == intent


def test_greeting_plus_question_goes_to_rag_without_greeting():
    r = classify_message("Sain bnu, yavgan zamiin urgun hed ve?")
    assert r.intent == "road"
    assert r.greeted is True
    assert r.query == "явган замын өргөн хэд вэ?"


def test_greeting_reply_in_users_script():
    latin = classify_message("sain bnu")
    cyr = classify_message("Сайн байна уу")
    assert to_reply_script(small_talk_reply(latin), latin).startswith("Sain baina uu!")
    assert small_talk_reply(cyr).startswith("Сайн байна уу!")


def test_morning_greeting_is_mirrored():
    r = classify_message("Өглөөний мэнд")
    assert small_talk_reply(r).startswith("Өглөөний мэнд!")
