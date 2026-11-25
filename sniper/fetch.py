"""Загрузка страниц makler.md с повторами и распознаванием блокировок."""
import time

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ru-RU,ru;q=0.9",
}


class SiteUnavailable(Exception):
    pass


class Fetcher:
    def __init__(self, retries: int = 3, backoff: float = 10, timeout: float = 30):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.retries, self.backoff, self.timeout = retries, backoff, timeout

    def __call__(self, url: str) -> str:
        last = None
        for attempt in range(self.retries):
            try:
                r = self.session.get(url, timeout=self.timeout)
                body = r.text
                if r.status_code == 200 and "cf-chl" not in body and "Just a moment" not in body[:3000]:
                    return body
                last = f"HTTP {r.status_code}" + (" (Cloudflare challenge)" if "cf-chl" in body else "")
            except requests.RequestException as e:
                last = f"{type(e).__name__}: {e}"
            if attempt < self.retries - 1:
                time.sleep(self.backoff * (attempt + 1))
        raise SiteUnavailable(f"{url}: {last}")
