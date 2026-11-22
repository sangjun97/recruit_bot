"""신한카드 채용(www.shinhancard.com) 수집기.

- robots.txt: `/mob/` 는 금지지만 채용 페이지들은 한 줄씩 명시적으로 허용돼 있다
  (`Allow: /mob/MOBFMCOMN/MOBFMCOM01.shc` 채용공고, `02.shc` 상세, `03.shc` 경력채용).
  페이지가 화면을 채우려고 부르는 `.ajax` 는 허용 목록에 없다. 그래서 `.ajax` 를 직접 부르지 않고,
  허용된 페이지를 브라우저로 열어 화면에 그려진 표만 읽는다(2026-11-22 사용자 결정: 공고 페이지를 읽을 수 있으면 그렇게 진행).
- 이용약관(온라인 회원 약관)은 회원 대상이고 자동 수집 조항은 없다. 제11조 "서비스 정보를 이용하여 얻은 정보를 승낙 없이
  복제 또는 유통하거나 상업적으로 이용하는 행위" 금지(삼성커리어스와 같은 유형).
- 채용공고(공채 공지)와 경력채용 두 표를 읽는다. 날짜만 있고 시각·근무지·직무 분류는 없다. 본문은 이미지라 읽지 않는다.
- 경력채용 표는 2026-11-22 에 비어 있어 실제 행 모양을 확인하지 못했다. 칸의 글자와 날짜를 일반적인 방법으로 읽는다.
- 광고·분석용 외부 요청은 보내지 않도록 신한카드 도메인이 아닌 요청은 끊는다.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from ..fetch import Fetcher
from ..models import Posting
from .base import Source

KST = timezone(timedelta(hours=9))
BASE = "https://www.shinhancard.com"
NOTICE_URL = f"{BASE}/mob/MOBFMCOMN/MOBFMCOM01.shc"   # 채용공고
CAREER_URL = f"{BASE}/mob/MOBFMCOMN/MOBFMCOM03.shc"   # 경력채용
DETAIL_URL = f"{BASE}/mob/MOBFMCOMN/MOBFMCOM02.shc"
DATE_RE = re.compile(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})")
GO_DETAIL_RE = re.compile(r"goDetail\('(\d+)'\s*,\s*'(\w+)'\)")

# 화면에 그려진 표의 각 행에서 칸의 글자와 링크의 클릭 동작만 꺼낸다
ROWS_JS = """els => els.map(tr => ({
  cells: Array.from(tr.querySelectorAll('td')).map(td => td.innerText.replace(/\\s+/g, ' ').trim()),
  title: (tr.querySelector('td.subject a, td a') || {innerText: ''}).innerText.replace(/\\s+/g, ' ').trim(),
  click: (tr.querySelector('td.subject a, td a') || {getAttribute: () => ''}).getAttribute('data-bind-click') || ''
}))"""


def _dates(text: str) -> list[datetime]:
    return [datetime(int(y), int(m), int(d)) for y, m, d in DATE_RE.findall(text)]


def parse_rows(rows: list[dict], source_key: str, board: str, now_kst: datetime) -> list[Posting]:
    """화면에서 읽은 행을 Posting 으로 바꾼다. board 는 'notice'(채용공고) 또는 'career'(경력채용)."""
    out: list[Posting] = []
    for r in rows:
        title = (r.get("title") or "").strip()
        click = r.get("click") or ""
        if not title or "{{" in title or "{{" in click:
            continue   # 아직 값이 채워지지 않은 틀(template) 행
        cells = [c for c in r.get("cells") or [] if c]
        days = _dates(" ".join(cells))
        start = days[0] if days else None
        end = days[1].replace(hour=23, minute=59) if len(days) > 1 else None
        m = GO_DETAIL_RE.search(click)
        if board == "notice" and m:
            seq, code = m.groups()
            # 순번이 다시 쓰일 수 있어 시작일을 함께 식별자로 쓴다
            ext_id = f"{code}-{seq}-{start:%Y%m%d}" if start else f"{code}-{seq}"
            url = f"{DETAIL_URL}?ancGdSeqN={seq}&hmpBlbBsnCCd={code}"
        else:
            digest = hashlib.sha1(f"{title}|{start}".encode("utf-8")).hexdigest()[:12]
            ext_id = f"{board}-{digest}"
            url = CAREER_URL if board == "career" else NOTICE_URL
        if end and end < now_kst:
            status = "접수마감"
        elif start and start > now_kst:
            status = "접수예정"
        else:
            status = "접수중"
        out.append(
            Posting(
                source=source_key,
                external_id=ext_id,
                company="신한카드",
                title=title,
                url=url,
                start_at=start,
                end_at=end,
                end_date_only=True,
                career_type="경력" if board == "career" else None,
                # 채용공고 표의 첫 칸은 '정기채용' 같은 구분이다
                employment_type=cells[0] if board == "notice" and cells and cells[0] != title and not _dates(cells[0]) else None,
                status=status,
            )
        )
    return out


class ShinhanCardSource(Source):
    site_url = NOTICE_URL
    min_interval_min = 60   # 브라우저로 두 페이지를 여는 소스라 한 시간에 한 번만

    def __init__(self, key: str = "shinhancard"):
        self.key = key
        self.company = "신한카드"

    def _read_table(self, f: Fetcher, url: str, row_selector: str) -> list[dict]:
        page = f.browser.new_page()
        # 신한카드 도메인이 아닌 요청(광고·분석 스크립트)은 보내지 않는다
        page.route("**/*", lambda route: route.continue_() if urlsplit(route.request.url).netloc.endswith("shinhancard.com") else route.abort())
        try:
            f.wait(url)
            resp = page.goto(url, wait_until="networkidle", timeout=60_000)
            if resp is not None and resp.status >= 400:
                raise RuntimeError(f"신한카드 채용 페이지 HTTP {resp.status}: {url}")
            page.wait_for_timeout(1500)
            more = page.locator("#btn_More a")   # '더보기': 화면에 10건씩 더 보여준다
            for _ in range(10):
                if more.count() == 0 or not more.first.is_visible():
                    break
                more.first.click()
                page.wait_for_timeout(700)
            return page.eval_on_selector_all(row_selector, ROWS_JS)
        finally:
            page.close()

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        now_kst = datetime.now(KST).replace(tzinfo=None)
        notice = self._read_table(f, NOTICE_URL, "tbody[data-bind-each='recruitList'] tr")
        career = self._read_table(f, CAREER_URL, "tbody[data-bind-each='careerRecruitList'] tr")
        return parse_rows(notice, self.key, "notice", now_kst) + parse_rows(career, self.key, "career", now_kst)
