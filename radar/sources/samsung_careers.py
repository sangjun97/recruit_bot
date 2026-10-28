"""삼성커리어스(samsungcareers.com) 수집기. 삼성전자 DX/DS부문을 포함한 삼성 관계사 전체 공고가 한 사이트에 올라온다.

- robots.txt 없음. 이용약관은 회원(가입자) 대상이며 자동 수집 금지 조항은 없으나 제12조·제15조에
  "서비스에서 취득한 정보를 회사 승낙 없이 복제·제3자 제공·영리 이용 금지" 조항이 있다.
  그래서 공고 제목·기간·링크·근무지 문장만 저장하고 본문은 저장하지 않는다. 로그인하지 않는다.
- 공고 목록: 페이지가 스스로 POST /hr/list.data 로 불러오는 HTML 조각.
- 공고 상세: GET /recruit/detail.data?seqno=ID 가 JSON 을 돌려주며, 모집 직무마다 workPlaceKr(근무지)가 따로 있다.
- 공유 링크: /hr/?no=ID
"""
from __future__ import annotations

import re
import time
from datetime import datetime

from playwright.sync_api import BrowserContext
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from ..models import Posting
from .base import Source

BASE = "https://www.samsungcareers.com"
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def _clean(s: str | None) -> str:
    return WS_RE.sub(" ", TAG_RE.sub(" ", s or "")).strip()


def _date(s: str) -> datetime | None:
    try:
        return datetime.strptime(s.strip(), "%Y.%m.%d")
    except ValueError:
        return None


def parse_list_html(html: str, source_key: str) -> tuple[list[Posting], int]:
    """list.data 응답(HTML 조각)에서 공고 카드와 전체 페이지 수를 읽는다."""
    tree = HTMLParser(html)
    max_pages = 1
    cnt = tree.css_first("input.divCnt")
    if cnt is not None and (cnt.attributes.get("data-max") or "").isdigit():
        max_pages = int(cnt.attributes["data-max"])
    out: list[Posting] = []
    for a in tree.css("a[data-value]"):
        sn = (a.attributes.get("data-value") or "").replace(",", "").strip()
        if not sn.isdigit():
            continue
        company = _clean(a.css_first("p.company").text() if a.css_first("p.company") else "")
        title = _clean(a.css_first("h3.title").text() if a.css_first("h3.title") else "")
        spans = [_clean(s.text()) for s in a.css("p.info span")]
        period = next((s for s in spans if "~" in s), "")
        career = next((s for s in spans if s and "~" not in s), None)
        start = end = None
        if period:
            parts = [p.strip() for p in period.split("~")]
            start = _date(parts[0]) if parts[0] else None
            end = _date(parts[1]) if len(parts) > 1 and parts[1] else None
        if end is not None:
            end = end.replace(hour=23, minute=59)
        out.append(
            Posting(
                source=source_key,
                external_id=sn,
                company=company or "삼성",
                title=title,
                url=f"{BASE}/hr/?no={sn}",
                start_at=start,
                end_at=end,
                career_type=career,
                status="접수중",  # 목록에는 접수 중인 공고만 올라온다
            )
        )
    return out, max_pages


def location_text_from_detail(data: dict) -> str | None:
    """상세 JSON에서 '직무명: 근무지' 줄만 뽑는다. 본문(수행업무·자격요건 등)은 가져오지 않는다."""
    d = data.get("data") or {}
    lines: list[str] = []
    for it in d.get("items") or []:
        wp = _clean(it.get("workPlaceKr"))
        title = _clean(it.get("titleKr"))
        if wp:
            lines.append(f"{title}: {wp}" if title else wp)
    if not lines:
        # 직무별 근무지가 비어 있으면 기타 안내문에서 근무지 관련 줄만 찾는다
        for key in ("etcKr", "qlfctKr", "docInfoKr"):
            for ln in TAG_RE.sub("\n", (d.get("result") or {}).get(key) or "").splitlines():
                if re.search(r"근무\s*(지|장소|지역)|사업장|소재지", ln):
                    lines.append(_clean(ln))
    return "\n".join(dict.fromkeys(lines)) or None


class SamsungCareersSource(Source):
    def __init__(self, key: str = "samsung", companies: set[str] | None = None, delay_sec: float = 1.5):
        self.key = key
        self.company = "삼성"
        self.companies = companies   # None 이면 관계사 전체. 예: {"삼성전자 DX부문", "삼성전자 DS부문"}
        self.delay_sec = delay_sec

    def _list_form(self, page_no: int) -> dict[str, str]:
        return {
            "currentPageNo": str(page_no), "intNo": "0", "strVal": "", "strTxt": "", "strKey": "",
            "strCompany": "", "strType": "", "strOrderBy": "", "strEntity": "",
        }

    def fetch_list(self, ctx: BrowserContext) -> list[Posting]:
        page = ctx.new_page()
        postings: dict[str, Posting] = {}
        try:
            page.goto(f"{BASE}/hr/", wait_until="networkidle", timeout=60_000)
            page.wait_for_timeout(1000)
            page_no, max_pages = 1, 1
            while page_no <= max_pages:
                if page_no > 1:
                    time.sleep(self.delay_sec)
                resp = page.request.post(f"{BASE}/hr/list.data", form=self._list_form(page_no))
                items, max_pages = parse_list_html(resp.text(), self.key)
                for p in items:
                    postings[p.external_id] = p
                page_no += 1
                if page_no > 20:  # 안전장치
                    break
        finally:
            page.close()
        result = list(postings.values())
        if self.companies:
            result = [p for p in result if p.company in self.companies]
        return result

    def fetch_location_text(self, ctx: BrowserContext, posting: Posting) -> str | None:
        page = ctx.new_page()
        try:
            time.sleep(self.delay_sec)
            # 공유 링크로 열면 페이지가 스스로 detail.data 를 요청한다. 같은 세션으로 JSON만 다시 받는다
            page.goto(posting.url, wait_until="networkidle", timeout=60_000)
            resp = page.request.get(f"{BASE}/recruit/detail.data?seqno={posting.external_id}&strCode=")
            data = resp.json()
        finally:
            page.close()
        return location_text_from_detail(data)
