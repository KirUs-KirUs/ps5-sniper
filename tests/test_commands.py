from sniper.commands import parse_updates
from sniper.notify import format_check_report


def upd(uid, chat, text):
    return {"update_id": uid, "message": {"chat": {"id": chat}, "text": text}}


def test_check_from_owner_requested():
    offset, check, other = parse_updates([upd(10, 42, "/check")], "42")
    assert (offset, check, other) == (11, True, False)


def test_russian_word_and_bot_suffix():
    assert parse_updates([upd(1, 42, "Проверь")], "42")[1] is True
    assert parse_updates([upd(1, 42, "/check@ps5_bot")], "42")[1] is True


def test_strangers_ignored():
    offset, check, other = parse_updates([upd(5, 999, "/check")], "42")
    assert offset == 6 and check is False and other is False


def test_other_text_asks_for_help():
    offset, check, other = parse_updates([upd(7, 42, "привет"), {"update_id": 8}], "42")
    assert (offset, check, other) == (9, False, True)


def test_no_updates_keeps_offset():
    assert parse_updates([], "42") == (None, False, False)


def test_check_report_ok():
    w = {"status": "ok", "error": None, "count": 12, "deals": 5, "new_24h": 1,
         "min": {"price": "8 000 руб (~$497)", "model": "Fat", "city": "Рыбница", "url": "https://x/1"}}
    msg = format_check_report(w, sent=0)
    assert "12" in msg and "Рыбница" in msg and "нового нет" in msg.lower()
    assert "Отправлено" in format_check_report(w, sent=2)


def test_check_report_site_down():
    w = {"status": "degraded", "error": "HTTP 403", "count": 0, "deals": 0, "new_24h": 0, "min": None}
    msg = format_check_report(w, sent=0)
    assert "недоступен" in msg and "HTTP 403" in msg
