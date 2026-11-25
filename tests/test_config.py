import json
from pathlib import Path


def test_config_is_valid():
    cfg = json.loads((Path(__file__).parent.parent / "config.json").read_text(encoding="utf-8"))
    for key in ("category_url", "max_pages", "page_delay_sec", "deal_usd", "min_usd", "rates_per_usd",
                "active_hours", "forget_days", "failure_alert_after", "summary_top"):
        assert key in cfg, key
    assert set(cfg["rates_per_usd"]) >= {"USD", "EUR", "MDL", "RUB"}
    assert all(isinstance(v, (int, float)) and v > 0 for v in cfg["rates_per_usd"].values())
