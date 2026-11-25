from pathlib import Path

from sniper.money import parse_price, to_usd
from sniper.parse import parse_item, parse_list

FIX = Path(__file__).parent / "fixtures"


def test_parse_list_fixture():
    items = parse_list((FIX / "list.html").read_text(encoding="utf-8"))
    assert len(items) == 36
    first = items[0]
    assert first["id"].isdigit()
    assert set(first) >= {"id", "title", "price", "currency", "city", "text", "thumb", "url"}
    assert first["url"].startswith("https://makler.md/ru/computers-and-office-equipment/game-consoles/an/")
    assert {i["city"] for i in items} <= {"Тирасполь", "Бендеры"}
    slim = next(i for i in items if "PS5 SLIM 1 TB" in i["title"])
    assert slim["text"]
    assert slim["thumb"].startswith("https://media.makler.md/")


def test_parse_list_ignores_top_query_suffix():
    items = parse_list((FIX / "list.html").read_text(encoding="utf-8"))
    assert all("?" not in i["url"] for i in items)


def test_parse_list_empty_page():
    assert parse_list("<html><body>nothing</body></html>") == []


def test_parse_item():
    d = parse_item((FIX / "item.html").read_text(encoding="utf-8"))
    assert "Жёсткий диск 500" in d["text"]
    assert d["image"].startswith("https://media.makler.md/production/an/original/")


def test_parse_price():
    assert parse_price("650 USD") == (650.0, "USD")
    assert parse_price("2 000 руб") == (2000.0, "RUB")
    assert parse_price("12 500 MDL") == (12500.0, "MDL")
    assert parse_price("500 EUR") == (500.0, "EUR")
    assert parse_price("Договорная") == (None, None)
    assert parse_price("") == (None, None)


def test_to_usd():
    rates = {"USD": 1, "RUB": 16.3, "MDL": 17.5, "EUR": 0.92}
    assert to_usd(1630, "RUB", rates) == 100
    assert to_usd(650, "USD", rates) == 650
    assert to_usd(None, None, rates) is None
    assert to_usd(100, "XXX", rates) is None
