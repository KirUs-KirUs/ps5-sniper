"""Telegram-уведомления."""
import html
import re

import requests

DISC_LABEL = {"yes": "💿 Дисковод: есть", "unknown": "❓ Дисковод: не указан — уточните"}


class Telegram:
    def __init__(self, token: str, chat_id: str):
        self.base = f"https://api.telegram.org/bot{token}/"
        self.chat_id = chat_id

    def _call(self, method, **data):
        r = requests.post(self.base + method, data={"chat_id": self.chat_id, "parse_mode": "HTML", **data}, timeout=30)
        if not r.ok or not r.json().get("ok"):
            raise RuntimeError(f"Telegram {method}: {r.status_code} {r.text[:200]}")

    def send_message(self, text: str):
        self._call("sendMessage", text=text, disable_web_page_preview="true")

    def send_photo(self, photo: str, caption: str):
        self._call("sendPhoto", photo=photo, caption=caption)


CUR_LABEL = {"RUB": "руб", "USD": "$", "EUR": "€", "MDL": "лей"}


def esc(s) -> str:
    return html.escape(str(s or ""), quote=False)


def price_str(l: dict) -> str:
    if l.get("price") is None:
        return esc(l.get("price_raw") or "цена не указана")
    p = f"{l['price']:,.0f}".replace(",", " ")
    s = f"{p} {CUR_LABEL.get(l.get('currency'), l.get('currency') or '')}".strip()
    if l.get("currency") == "USD":
        s = f"${p}"
    elif l.get("currency") and l.get("usd") is not None:
        s += f" (~${l['usd']:.0f})"
    return s


def model_label(l: dict) -> str:
    m = l.get("model") or "PS5"
    return "PS5" if m == "PS5" else f"PS5 {m}"


def is_deal(l: dict, deal_usd: float) -> bool:
    return l.get("usd") is not None and l["usd"] <= deal_usd


def _trim(text: str, limit: int) -> str:
    text = re.sub(r"[ \t]*\n\s*", "\n", (text or "").strip())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def format_new(l: dict, deal_usd: float, text_limit: int = 450) -> str:
    head = "🔥 <b>ВЫГОДНО</b> · " if is_deal(l, deal_usd) else "🆕 "
    return (
        f"{head}<b>{model_label(l)}</b>\n<b>{esc(l['title'])}</b>\n"
        f"💰 {price_str(l)}\n"
        f"📍 {esc(l.get('city') or '—')}\n"
        f"{DISC_LABEL.get(l.get('disc'), DISC_LABEL['unknown'])}\n\n"
        f"{esc(_trim(l.get('text'), text_limit))}\n\n"
        f"🔗 {esc(l['url'])}"
    )


def format_drop(l: dict, old: dict, deal_usd: float) -> str:
    head = "📉🔥 <b>Цена снижена — ВЫГОДНО</b>" if is_deal(l, deal_usd) else "📉 <b>Цена снижена</b>"
    return (
        f"{head}\n<b>{esc(l['title'])}</b> · {model_label(l)}\n"
        f"Было: <s>{price_str(old)}</s>\nСтало: <b>{price_str(l)}</b>\n"
        f"📍 {esc(l.get('city') or '—')} · {DISC_LABEL.get(l.get('disc'), DISC_LABEL['unknown'])}\n"
        f"🔗 {esc(l['url'])}"
    )


def format_summary(listings: list[dict], deal_usd: float, top: int) -> str:
    lines = [f"🎮 <b>PS5 Sniper запущен</b>\nСейчас найдено подходящих объявлений: {len(listings)}. "
             f"Дальше буду присылать только новые и снижения цены.\n"]
    for l in listings[:top]:
        mark = "🔥" if is_deal(l, deal_usd) else "•"
        disc = "" if l.get("disc") == "yes" else " ❓диск"
        lines.append(f"{mark} <a href=\"{esc(l['url'])}\">{esc(_trim(l['title'], 60))}</a> — "
                     f"{price_str(l)}, {esc(l.get('city'))}{disc}")
    return "\n".join(lines)


def send_listing(tg, l: dict, deal_usd: float):
    """Фото + подпись (лимит 1024), при ошибке — обычный текст."""
    photo = l.get("image") or l.get("thumb")
    if photo:
        try:
            tg.send_photo(photo, format_new(l, deal_usd, text_limit=350)[:1024])
            return
        except Exception as e:  # noqa: BLE001 — любой сбой фото -> текст
            print(f"photo failed for {l['id']}: {e}")
    tg.send_message(format_new(l, deal_usd, text_limit=1500))
