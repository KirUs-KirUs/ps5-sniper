import json
from pathlib import Path

import pytest

from sniper import main as M
from sniper.fetch import SiteUnavailable

CAT = "https://makler.md/ru/computers-and-office-equipment/game-consoles?list"

CONFIG = {
    "category_url": CAT,
    "max_pages": 5,
    "page_delay_sec": 0,
    "deal_usd": 650,
    "rates_per_usd": {"USD": 1, "RUB": 16, "MDL": 17, "EUR": 0.9},
    "active_hours": 6,
    "forget_days": 30,
    "failure_alert_after": 3,
    "summary_top": 10,
    "min_usd": 150,
}


def article(an_id, title, price="650 USD", city="Тирасполь", text=""):
    return f"""
    <article id="tr_an-{an_id}">
      <div class="ls-detail_imgBlock"><img src="https://media.makler.md/t/{an_id}.jpg"></div>
      <span class="ls-detail_price">{price}</span>
      <a href="/ru/computers-and-office-equipment/game-consoles/an/{an_id}" class="ls-detail_anUrl"><span>{title}</span></a>
      <div class="subfir">{text}</div>
      <span class="ls-jobMeta_chip ls-jobMeta_chip--city">{city}</span>
    </article>"""


def page(*arts):
    return "<html><body>" + "".join(arts) + "</body></html>"


ITEM = """<html><head>
<meta property="og:description" content="Полное описание, с дисководом">
<meta property="og:image" content="https://media.makler.md/production/an/original/x.jpg">
</head><body><div id="anText">Полное описание, с дисководом, 2 геймпада</div></body></html>"""


class FakeSite:
    def __init__(self, pages):
        self.pages = pages  # list of html for page 1..n
        self.down = False
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        if self.down:
            raise SiteUnavailable("boom")
        if "/an/" in url:
            return ITEM
        n = int(url.split("page=")[1]) if "page=" in url else 1
        return self.pages[n - 1] if n <= len(self.pages) else page()


class FakeTG:
    def __init__(self):
        self.sent = []
        self.fail = False

    def send_photo(self, photo, caption):
        if self.fail:
            raise RuntimeError("tg down")
        self.sent.append(("photo", caption))

    def send_message(self, text):
        if self.fail:
            raise RuntimeError("tg down")
        self.sent.append(("text", text))


@pytest.fixture
def paths(tmp_path):
    return tmp_path / "state.json", tmp_path / "widget.json"


def run(site, tg, paths, now):
    return M.run(CONFIG, paths[0], paths[1], site, tg, now=now)


BASE_PAGES = [page(article(1, "PS5 Slim с дисководом", "600 USD"),
                   article(2, "Диски для PS5", "20 USD"),
                   article(3, "Sony PlayStation 5 Pro", "15 000 руб"))]


def test_first_run_sends_single_summary(paths):
    site, tg = FakeSite(BASE_PAGES), FakeTG()
    assert run(site, tg, paths, "2026-11-25T10:00:00+00:00") == 0
    assert len(tg.sent) == 1
    assert "PS5 Slim" in tg.sent[0][1]
    state = json.loads(paths[0].read_text(encoding="utf-8"))
    assert set(state["listings"]) == {"1", "3"}
    assert all(l["notified"] for l in state["listings"].values())
    assert not any("/an/" in c for c in site.calls)  # без захода в карточки


def test_quiet_when_nothing_changed(paths):
    site, tg = FakeSite(BASE_PAGES), FakeTG()
    run(site, tg, paths, "2026-11-25T10:00:00+00:00")
    run(site, tg, paths, "2026-11-25T11:00:00+00:00")
    assert len(tg.sent) == 1


def test_new_listing_notified_once_and_deal_marked(paths):
    site, tg = FakeSite(BASE_PAGES), FakeTG()
    run(site, tg, paths, "2026-11-25T10:00:00+00:00")
    site.pages = [page(article(9, "PS5 Slim", "550 USD", city="Бендеры"), *[])] + BASE_PAGES
    run(site, tg, paths, "2026-11-25T11:00:00+00:00")
    run(site, tg, paths, "2026-11-25T12:00:00+00:00")
    assert len(tg.sent) == 2
    kind, msg = tg.sent[1]
    assert kind == "photo"
    assert "ВЫГОДНО" in msg and "Бендеры" in msg and "дисковод" in msg.lower()
    assert "https://makler.md/ru/computers-and-office-equipment/game-consoles/an/9" in msg


def test_bump_does_not_notify(paths):
    site, tg = FakeSite(BASE_PAGES), FakeTG()
    run(site, tg, paths, "2026-11-25T10:00:00+00:00")
    # объявление 3 поднято наверх
    site.pages = [page(article(3, "Sony PlayStation 5 Pro", "15 000 руб"),
                       article(1, "PS5 Slim с дисководом", "600 USD"))]
    run(site, tg, paths, "2026-11-25T11:00:00+00:00")
    assert len(tg.sent) == 1


def test_price_drop_notified(paths):
    site, tg = FakeSite(BASE_PAGES), FakeTG()
    run(site, tg, paths, "2026-11-25T10:00:00+00:00")
    site.pages = [page(article(1, "PS5 Slim с дисководом", "550 USD"))]
    run(site, tg, paths, "2026-11-25T11:00:00+00:00")
    assert len(tg.sent) == 2
    msg = tg.sent[1][1]
    assert "600" in msg and "550" in msg and "снижен" in msg.lower()
    # рост цены — без уведомления
    site.pages = [page(article(1, "PS5 Slim с дисководом", "580 USD"))]
    run(site, tg, paths, "2026-11-25T12:00:00+00:00")
    assert len(tg.sent) == 2


def test_telegram_failure_retried_next_run(paths):
    site, tg = FakeSite(BASE_PAGES), FakeTG()
    run(site, tg, paths, "2026-11-25T10:00:00+00:00")
    site.pages = [page(article(9, "PS5 Slim", "550 USD"))] + BASE_PAGES
    tg.fail = True
    run(site, tg, paths, "2026-11-25T11:00:00+00:00")
    state = json.loads(paths[0].read_text(encoding="utf-8"))
    assert state["listings"]["9"]["notified"] is False
    tg.fail = False
    run(site, tg, paths, "2026-11-25T12:00:00+00:00")
    assert sum("an/9" in m for _, m in tg.sent) == 1


def test_site_down_keeps_data_and_alerts_once(paths):
    site, tg = FakeSite(BASE_PAGES), FakeTG()
    run(site, tg, paths, "2026-11-25T10:00:00+00:00")
    before = json.loads(paths[0].read_text(encoding="utf-8"))["listings"]
    site.down = True
    for h in range(11, 16):
        assert run(site, tg, paths, f"2026-11-25T{h}:00:00+00:00") == 0
    state = json.loads(paths[0].read_text(encoding="utf-8"))
    assert state["listings"] == before
    assert state["health"]["consecutive_failures"] == 5
    alerts = [m for _, m in tg.sent if "недоступен" in m]
    assert len(alerts) == 1
    widget = json.loads(paths[1].read_text(encoding="utf-8"))
    assert widget["status"] == "down"
    site.down = False
    run(site, tg, paths, "2026-11-25T17:00:00+00:00")
    assert any("восстановлен" in m for _, m in tg.sent)
    assert json.loads(paths[1].read_text(encoding="utf-8"))["status"] == "ok"


def test_photo_failure_falls_back_to_text(paths):
    site = FakeSite(BASE_PAGES)

    class PhotoFails(FakeTG):
        def send_photo(self, photo, caption):
            raise RuntimeError("bad photo")

    tg = PhotoFails()
    run(site, tg, paths, "2026-11-25T10:00:00+00:00")
    site.pages = [page(article(9, "PS5 Slim", "550 USD"))] + BASE_PAGES
    run(site, tg, paths, "2026-11-25T11:00:00+00:00")
    assert tg.sent[-1][0] == "text" and "an/9" in tg.sent[-1][1]


def test_negotiable_price_not_deal(paths):
    site, tg = FakeSite(BASE_PAGES), FakeTG()
    run(site, tg, paths, "2026-11-25T10:00:00+00:00")
    site.pages = [page(article(9, "PS5 Slim", "Договорная"))] + BASE_PAGES
    run(site, tg, paths, "2026-11-25T11:00:00+00:00")
    msg = tg.sent[-1][1]
    assert "ВЫГОДНО" not in msg and "an/9" in msg


def test_widget_json(paths):
    site, tg = FakeSite(BASE_PAGES), FakeTG()
    run(site, tg, paths, "2026-11-25T10:00:00+00:00")
    w = json.loads(paths[1].read_text(encoding="utf-8"))
    assert w["status"] == "ok"
    assert w["last_ok"] == "2026-11-25T10:00:00+00:00"
    assert w["count"] == 2
    assert w["new_24h"] == 0  # стартовая база не считается «новыми»
    assert w["min"]["usd"] == 600 and w["min"]["model"] == "Slim"
    assert w["top"][0]["deal"] is True
    assert w["top"][0]["url"].endswith("/an/1")


def test_too_cheap_is_ignored(paths):
    site, tg = FakeSite(BASE_PAGES), FakeTG()
    run(site, tg, paths, "2026-11-25T10:00:00+00:00")
    site.pages = [page(article(9, "Horizon zero dawn remastered ps5", "600 руб"))] + BASE_PAGES
    run(site, tg, paths, "2026-11-25T11:00:00+00:00")
    assert len(tg.sent) == 1


def test_mixed_listing_price_not_used_for_deal_or_min(paths):
    site = FakeSite([page(article(5, "PS5-PS4 прошитые Магазин", "220 USD"),
                          article(1, "PS5 Slim с дисководом", "600 USD"))])
    tg = FakeTG()
    run(site, tg, paths, "2026-11-25T10:00:00+00:00")
    w = json.loads(paths[1].read_text(encoding="utf-8"))
    assert w["min"]["usd"] == 600
    assert w["count"] == 2
    assert not next(t for t in w["top"] if t["id"] == "5")["deal"]


def test_rejected_after_detail_never_notified(paths, monkeypatch):
    site, tg = FakeSite(BASE_PAGES), FakeTG()
    run(site, tg, paths, "2026-11-25T10:00:00+00:00")
    monkeypatch.setattr(__import__("tests.test_main", fromlist=["x"]), "ITEM",
                        ITEM.replace("с дисководом", "Digital Edition, без дисковода"))
    site.pages = [page(article(9, "Продам PS5", "500 USD"))] + BASE_PAGES
    run(site, tg, paths, "2026-11-25T11:00:00+00:00")
    site.pages = [page(article(9, "Продам PS5", "450 USD"))] + BASE_PAGES
    run(site, tg, paths, "2026-11-25T12:00:00+00:00")
    assert len(tg.sent) == 1
    w = json.loads(paths[1].read_text(encoding="utf-8"))
    assert all(t["id"] != "9" for t in w["top"])


def test_listing_failing_new_rules_is_dropped_from_widget(paths, monkeypatch):
    site, tg = FakeSite([page(article(7, "PS5 Slim с дисководом", "600 USD"),
                              article(1, "PS5 Slim с дисководом", "620 USD"))]), FakeTG()
    run(site, tg, paths, "2026-11-25T10:00:00+00:00")
    import sniper.main as sm
    real = sm.classify
    monkeypatch.setattr(sm, "classify", lambda t, x="": {**real(t, x), "is_ps5": False, "reason": "rule"}
                        if "7" in x else real(t, x))
    site.pages = [page(article(7, "PS5 Slim с дисководом", "600 USD", text="7"),
                       article(1, "PS5 Slim с дисководом", "620 USD"))]
    run(site, tg, paths, "2026-11-25T11:00:00+00:00")
    w = json.loads(paths[1].read_text(encoding="utf-8"))
    assert [t["id"] for t in w["top"]] == ["1"]
