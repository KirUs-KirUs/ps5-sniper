from sniper.commands import parse_updates
from sniper.notify import format_check_report


def upd(uid, chat, text):
    return {"update_id": uid, "message": {"chat": {"id": chat}, "text": text}}


def test_check_from_owner_requested():
    assert parse_updates([upd(10, 42, "/check")], "42") == (11, {"check"})


def test_russian_word_and_bot_suffix():
    assert parse_updates([upd(1, 42, "Проверь")], "42")[1] == {"check"}
    assert parse_updates([upd(1, 42, "/check@ps5_bot")], "42")[1] == {"check"}


def test_strangers_ignored():
    assert parse_updates([upd(5, 999, "/check")], "42") == (6, set())


def test_other_text_asks_for_help():
    assert parse_updates([upd(7, 42, "привет"), {"update_id": 8}], "42") == (9, {"help"})


def test_no_updates_keeps_offset():
    assert parse_updates([], "42") == (None, set())


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


def test_list_command():
    from sniper.commands import parse_command
    assert parse_command("/list") == "list"
    assert parse_command("Список") == "list"
    assert parse_command("/check@bot") == "check"
    assert parse_command("привет") is None


def test_format_list():
    from sniper.notify import format_list
    items = [{"title": "PS5 Slim", "url": "https://x/1", "price": 600, "currency": "USD", "usd": 600,
              "city": "Тирасполь", "disc": "yes"},
             {"title": "PS5", "url": "https://x/2", "price": 700, "currency": "USD", "usd": 700,
              "city": "Бендеры", "disc": "unknown"}]
    msg = format_list(items, 650, "2026-11-25T15:28:59+00:00")
    assert "2" in msg and "🔥" in msg and "Бендеры" in msg and "❓" in msg
    assert "Подходящих объявлений пока нет" in format_list([], 650, None)
