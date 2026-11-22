"""수집에 쓰는 HTTP 클라이언트와, 필요할 때만 띄우는 브라우저를 한데 묶는다.

- 대부분의 소스는 httpx 만 쓴다. 브라우저(Playwright)는 페이지를 열어야만 목록이 나오는 사이트에서만 쓰고,
  그런 소스가 처음 `browser` 를 요청할 때 한 번만 띄운다.
- 같은 호스트에는 `delay_sec` 간격을 두고 요청한다(사이트에 부담을 주지 않기 위한 장치).
"""
from __future__ import annotations

import time
from urllib.parse import urlsplit

import httpx


class Fetcher:
    def __init__(self, user_agent: str, delay_sec: float = 1.5, timeout: float = 30.0):
        self.user_agent = user_agent
        self.delay_sec = delay_sec
        self.http = httpx.Client(
            headers={"User-Agent": user_agent, "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5"},
            timeout=timeout,
            follow_redirects=True,
        )
        self._last: dict[str, float] = {}
        self._pw = None
        self._browser = None
        self._ctx = None

    # --- 예의 -----------------------------------------------------------------
    def wait(self, url: str) -> None:
        """같은 호스트에 대한 직전 요청으로부터 delay_sec 이 지나도록 기다린다."""
        host = urlsplit(url).netloc
        last = self._last.get(host)
        if last is not None:
            remain = self.delay_sec - (time.monotonic() - last)
            if remain > 0:
                time.sleep(remain)
        self._last[host] = time.monotonic()

    # --- HTTP -----------------------------------------------------------------
    def get(self, url: str, **kw) -> httpx.Response:
        self.wait(url)
        resp = self.http.get(url, **kw)
        resp.raise_for_status()
        return resp

    def post(self, url: str, **kw) -> httpx.Response:
        self.wait(url)
        resp = self.http.post(url, **kw)
        resp.raise_for_status()
        return resp

    # --- 브라우저 (필요할 때만) -------------------------------------------------
    @property
    def browser(self):
        """Playwright BrowserContext. 처음 쓸 때 Chromium 을 띄운다."""
        if self._ctx is None:
            from playwright.sync_api import sync_playwright

            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch()
            self._ctx = self._browser.new_context(user_agent=self.user_agent, locale="ko-KR")
        return self._ctx

    def close(self) -> None:
        self.http.close()
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()
        self._pw = self._browser = self._ctx = None

    def __enter__(self) -> "Fetcher":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
