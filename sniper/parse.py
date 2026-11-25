"""Разбор HTML страниц makler.md."""
import re

from bs4 import BeautifulSoup

from .money import parse_price

BASE = "https://makler.md"


def _text(node) -> str:
    if node is None:
        return ""
    return re.sub(r"[ \t\r\f\v]+", " ", node.get_text("\n")).strip()


def parse_list(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for art in soup.select("article[id^=tr_an-]"):
        an_id = art["id"].removeprefix("tr_an-")
        link = art.select_one("a.ls-detail_anUrl")
        if not an_id.isdigit() or link is None:
            continue
        href = link.get("href", "").split("?")[0]
        price_raw = _text(art.select_one(".ls-detail_price"))
        price, currency = parse_price(price_raw)
        img = art.select_one(".ls-detail_imgBlock img")
        text = _text(art.select_one(".subfir"))
        text = re.sub(r"\n\s*\n+", "\n", text)
        items.append({
            "id": an_id,
            "title": _text(link),
            "price": price,
            "currency": currency,
            "price_raw": price_raw,
            "city": _text(art.select_one(".ls-jobMeta_chip--city")),
            "text": text,
            "thumb": img.get("src", "") if img else "",
            "url": BASE + href,
        })
    return items


def parse_item(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    def meta(prop):
        tag = soup.find("meta", attrs={"property": prop})
        return tag.get("content", "").strip() if tag else ""

    text = meta("og:description")
    body = soup.select_one("#anText, .itemtable, .item_text")
    if body is not None and len(_text(body)) > len(text):
        text = _text(body)
    return {"text": text, "image": meta("og:image")}
