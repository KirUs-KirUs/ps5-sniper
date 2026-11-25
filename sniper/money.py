"""Цены: разбор строки цены и пересчёт в доллары."""
import re

_CURRENCIES = {
    "usd": "USD", "$": "USD", "у.е": "USD", "уе": "USD",
    "eur": "EUR", "€": "EUR",
    "mdl": "MDL", "лей": "MDL", "lei": "MDL",
    "руб": "RUB", "р.": "RUB",
}


def parse_price(raw: str):
    """'2 000 руб' -> (2000.0, 'RUB'); нечисловая цена -> (None, None)."""
    if not raw:
        return None, None
    s = raw.replace("\xa0", " ").strip().lower()
    m = re.search(r"\d[\d\s.,]*", s)
    if not m:
        return None, None
    number = re.sub(r"\s", "", m.group()).replace(",", ".").rstrip(".")
    try:
        value = float(number)
    except ValueError:
        return None, None
    rest = s[m.end():] + " " + s[: m.start()]
    for key, code in _CURRENCIES.items():
        if key in rest:
            return value, code
    return value, None


def to_usd(price, currency, rates: dict):
    """rates: сколько единиц валюты за 1 USD."""
    if price is None or currency not in rates:
        return None
    return round(price / float(rates[currency]), 2)
