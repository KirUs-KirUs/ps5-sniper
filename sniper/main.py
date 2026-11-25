"""Один проход мониторинга: обход категории -> отбор PS5 -> уведомления -> сохранение состояния."""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .classify import classify
from .fetch import Fetcher, SiteUnavailable
from .money import to_usd
from .notify import Telegram, format_drop, format_summary, is_deal, price_str, send_listing
from .parse import parse_item, parse_list

ROOT = Path(__file__).resolve().parent.parent


# ---------- состояние ----------

def load_json(path: Path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save_json(path: Path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)  # атомарно: файл либо старый, либо новый целиком


def new_state():
    return {"initialized": False, "listings": {},
            "health": {"last_run": None, "last_ok": None, "consecutive_failures": 0,
                       "alerted_down": False, "last_error": None}}


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


# ---------- обход ----------

def page_url(base: str, n: int) -> str:
    return base if n == 1 else f"{base}{'&' if '?' in base else '?'}page={n}"


def crawl(cfg, fetch) -> list[dict]:
    """Все объявления категории. Ошибка первой страницы -> SiteUnavailable; последующих — обход обрывается."""
    seen, items = set(), []
    for n in range(1, cfg["max_pages"] + 1):
        if n > 1 and cfg["page_delay_sec"]:
            time.sleep(cfg["page_delay_sec"])
        try:
            page = parse_list(fetch(page_url(cfg["category_url"], n)))
        except SiteUnavailable:
            if n == 1:
                raise
            print(f"page {n} failed, partial crawl")
            break
        fresh = [i for i in page if i["id"] not in seen]
        if not fresh:
            if n == 1:
                raise SiteUnavailable("первая страница без объявлений (изменилась вёрстка или блокировка?)")
            break
        seen.update(i["id"] for i in fresh)
        items.extend(fresh)
    return items


# ---------- основной проход ----------

def run(cfg, state_path, widget_path, fetch, tg, now: str | None = None) -> int:
    now = now or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    state = load_json(state_path, None) or new_state()
    health = state["health"]
    health["last_run"] = now

    try:
        items = crawl(cfg, fetch)
    except SiteUnavailable as e:
        health["consecutive_failures"] += 1
        health["last_error"] = str(e)[:300]
        print(f"SITE UNAVAILABLE ({health['consecutive_failures']}): {e}")
        if health["consecutive_failures"] >= cfg["failure_alert_after"] and not health["alerted_down"]:
            try:
                tg.send_message(f"⚠️ <b>PS5 Sniper:</b> Makler.md недоступен уже "
                                f"{health['consecutive_failures']} проверки подряд.\n<code>{str(e)[:200]}</code>")
                health["alerted_down"] = True
            except Exception as te:  # noqa: BLE001
                print(f"telegram alert failed: {te}")
        save_json(state_path, state)
        save_json(widget_path, build_widget(cfg, state, now))
        return 0

    rates, deal = cfg["rates_per_usd"], cfg["deal_usd"]
    listings = state["listings"]
    first_run = not state["initialized"]

    # 1. отбор PS5 и обновление состояния
    for it in items:
        c = classify(it["title"], it["text"])
        if not c["is_ps5"]:
            continue
        # в объявлениях «PS5/PS4» цена обычно «от» и относится к другой консоли — в доллары не пересчитываем
        usd = None if c["mixed"] else to_usd(it["price"], it["currency"], rates)
        if usd is not None and usd < cfg.get("min_usd", 0):
            continue  # слишком дёшево для консоли: игра, аренда, услуга
        old = listings.get(it["id"])
        if old is None:
            listings[it["id"]] = {**it, "model": c["model"], "disc": c["disc"], "usd": usd,
                                  "first_seen": now, "last_seen": now, "notified": False,
                                  "baseline": first_run, "image": "", "detail_loaded": False,
                                  "price_history": [[now, it["price"], it["currency"]]]}
            continue
        if old.get("rejected"):
            old["last_seen"] = now
            continue
        prev = {"price": old["price"], "currency": old["currency"], "usd": old["usd"], "price_raw": old.get("price_raw")}
        old.update({k: it[k] for k in ("title", "price", "currency", "price_raw", "city", "thumb", "url")})
        if not old.get("detail_loaded"):
            old["text"] = it["text"]
        old.update(last_seen=now, usd=usd, model=c["model"] if c["model"] != "PS5" else old["model"])
        if c["disc"] == "yes":
            old["disc"] = "yes"
        if it["price"] != prev["price"] or it["currency"] != prev["currency"]:
            old["price_history"].append([now, it["price"], it["currency"]])
            dropped = (prev["currency"] == it["currency"] and None not in (prev["price"], it["price"])
                       and it["price"] < prev["price"]) or (
                prev["currency"] != it["currency"] and None not in (prev["usd"], usd) and usd < prev["usd"])
            if dropped and old["notified"]:
                # сохраняем самую старую цену, если прошлое уведомление о снижении ещё не ушло
                old.setdefault("pending_drop", prev)
            elif not dropped:
                old.pop("pending_drop", None)

    # 2. первый запуск: тихая база + одна сводка
    if first_run:
        active = sorted_active(cfg, listings, now)
        try:
            tg.send_message(format_summary(active, deal, cfg["summary_top"]))
            for l in listings.values():
                l["notified"] = True
            state["initialized"] = True
        except Exception as e:  # noqa: BLE001
            print(f"summary failed, will retry: {e}")
    else:
        # 3. новые объявления
        pending = sorted((l for l in listings.values() if not l["notified"]), key=lambda l: l["first_seen"])
        for l in pending:
            if not l.get("detail_loaded"):
                try:
                    d = parse_item(fetch(l["url"]))
                    if d["text"]:
                        l["text"] = d["text"]
                    l["image"] = d["image"]
                    l["detail_loaded"] = True
                    c = classify(l["title"], l["text"])
                    if not c["is_ps5"]:  # полное описание показало, что это не консоль с дисководом
                        l["notified"] = True
                        l["rejected"] = c["reason"]
                        continue
                    l["disc"] = c["disc"]
                    if c["model"] != "PS5":
                        l["model"] = c["model"]
                except SiteUnavailable as e:
                    print(f"detail failed for {l['id']}: {e}")
            try:
                send_listing(tg, l, deal)
                l["notified"] = True
            except Exception as e:  # noqa: BLE001
                print(f"telegram failed for {l['id']}: {e}")
        # 4. снижения цен
        for l in listings.values():
            if "pending_drop" in l and l["notified"]:
                try:
                    tg.send_message(format_drop(l, l["pending_drop"], deal))
                    del l["pending_drop"]
                except Exception as e:  # noqa: BLE001
                    print(f"telegram drop failed for {l['id']}: {e}")

    # 5. здоровье и очистка
    if health["alerted_down"]:
        try:
            tg.send_message("✅ <b>PS5 Sniper:</b> доступ к Makler.md восстановлен.")
            health["alerted_down"] = False
        except Exception as e:  # noqa: BLE001
            print(f"telegram recovery failed: {e}")
    health.update(last_ok=now, consecutive_failures=0, last_error=None)
    cutoff = _ts(now) - timedelta(days=cfg["forget_days"])
    for k in [k for k, l in listings.items() if _ts(l["last_seen"]) < cutoff]:
        del listings[k]

    save_json(state_path, state)
    save_json(widget_path, build_widget(cfg, state, now))
    print(f"ok: {len(items)} listings scanned, {len(sorted_active(cfg, listings, now))} active PS5")
    return 0


def sorted_active(cfg, listings, now) -> list[dict]:
    cutoff = _ts(now) - timedelta(hours=cfg["active_hours"])
    active = [l for l in listings.values() if _ts(l["last_seen"]) >= cutoff and not l.get("rejected")]
    deal = cfg["deal_usd"]
    return sorted(active, key=lambda l: (not is_deal(l, deal), l["usd"] is None, l["usd"] or 0))


def build_widget(cfg, state, now) -> dict:
    h = state["health"]
    if h["consecutive_failures"] == 0:
        status = "ok"
    elif h["consecutive_failures"] < cfg["failure_alert_after"]:
        status = "degraded"
    else:
        status = "down"
    ref = _ts(h["last_ok"]) if h["last_ok"] else _ts(now)
    active = sorted_active(cfg, state["listings"], ref.isoformat())
    day_ago = _ts(now) - timedelta(hours=24)
    priced = [l for l in active if l["usd"] is not None]
    cheapest = min(priced, key=lambda l: l["usd"]) if priced else None

    def card(l):
        return {"id": l["id"], "title": l["title"], "model": l["model"], "city": l.get("city"),
                "price": price_str(l), "usd": l["usd"], "disc": l["disc"], "url": l["url"],
                "thumb": l.get("thumb"), "deal": is_deal(l, cfg["deal_usd"]),
                "new": not l.get("baseline") and _ts(l["first_seen"]) >= day_ago}

    return {
        "updated": now,
        "last_ok": h["last_ok"],
        "status": status,
        "error": h["last_error"],
        "count": len(active),
        "new_24h": sum(1 for l in active if not l.get("baseline") and _ts(l["first_seen"]) >= day_ago),
        "deals": sum(1 for l in active if is_deal(l, cfg["deal_usd"])),
        "min": card(cheapest) if cheapest else None,
        "top": [card(l) for l in active[:8]],
        "list_url": cfg["category_url"],
    }


def load_env(path: Path):
    """Подхватывает KEY=VALUE из локального .env (не в git). Переменные окружения важнее файла."""
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (p.strip() for p in line.split("=", 1))
        os.environ.setdefault(key, value.strip('"').strip("'"))


def cli():
    load_env(ROOT / ".env")
    cfg = load_json(ROOT / "config.json", None)
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    missing = [n for n, v in (("TELEGRAM_BOT_TOKEN", token), ("TELEGRAM_CHAT_ID", chat)) if not v]
    if missing:
        # ::error:: попадает в аннотации GitHub, их видно без входа в аккаунт
        print(f"::error::Не заданы секреты: {', '.join(missing)} "
              "— запустите windows/setup.ps1, он создаст файл .env")
        sys.exit(1)
    sys.exit(run(cfg, ROOT / "data" / "state.json", ROOT / "data" / "widget.json", Fetcher(), Telegram(token, chat)))


if __name__ == "__main__":
    try:
        cli()
    except Exception as e:  # noqa: BLE001
        print(f"::error::{type(e).__name__}: {e}")
        raise
