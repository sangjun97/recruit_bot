"""삼성커리어스(samsungcareers.com) 수집기. 삼성전자 DX/DS부문을 포함한 삼성 관계사 공고가 한 사이트에 올라온다.

- robots.txt 없음(302). 이용약관은 회원(가입자) 대상이며 자동 수집 금지 조항은 없으나 제12조·제15조에
  "서비스에서 취득한 정보를 회사 승낙 없이 복제·제3자 제공·영리 이용 금지" 조항이 있다.
  그래서 공고 제목·기간·링크·직무명·근무지 문장만 저장하고 본문은 저장하지 않는다. 로그인하지 않는다.
- 공고 목록: POST /hr/list.data (HTML 조각). 브라우저 없이 받을 수 있다. 접수 중인 공고만 올라온다.
- 공고 상세: GET /recruit/detail.data?seqno=ID (JSON). 모집 직무마다 titleKr(직무명)·workPlaceKr(근무지)가 있고,
  result.startdate/enddate 에 분 단위 접수 기간(YYYYMMDDHHMM)이 있다. 목록에는 날짜만 있다.
- 공유 링크: /hr/?no=ID
- 삼성 공고는 여러 직무를 한 공고로 묶으므로('경력사원 채용(AI, IT, 경영기획 ...)') 직무명을 job_text 로 저장해
  AI·데이터 직무 판별에 쓴다.
"""
from __future__ import annotations

import re
from datetime import datetime

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from ..companies import SAMSUNG_MAJOR
from ..fetch import Fetcher
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


def _stamp(s: str | None) -> datetime | None:
    """상세의 'YYYYMMDDHHMM' 표기."""
    try:
        return datetime.strptime((s or "").strip()[:12], "%Y%m%d%H%M")
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
                end_date_only=True,   # 목록에는 날짜만 있다. 실제 마감 시각은 상세에서 받는다
                career_type=career,
                status="접수중",       # 목록에는 접수 중인 공고만 올라온다
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


def job_text_from_detail(data: dict) -> str:
    """상세 JSON의 모집 직무명 목록(줄 단위)."""
    items = (data.get("data") or {}).get("items") or []
    names = [_clean(it.get("titleKr")) for it in items]
    return "\n".join(dict.fromkeys(n for n in names if n))


def apply_detail(posting: Posting, data: dict) -> None:
    """상세에서만 알 수 있는 값(분 단위 접수 기간, 직무명)을 posting 에 채운다."""
    result = (data.get("data") or {}).get("result") or {}
    start, end = _stamp(result.get("startdate")), _stamp(result.get("enddate"))
    if start:
        posting.start_at = start
    if end:
        posting.end_at = end
        posting.end_date_only = False
    posting.job_text = job_text_from_detail(data)


class SamsungCareersSource(Source):
    detail_for_classify = True
    site_url = f"{BASE}/hr/"

    def __init__(self, key: str = "samsung", companies: set[str] | None = SAMSUNG_MAJOR):
        self.key = key
        self.company = "삼성 (삼성커리어스)"
        self.companies = companies   # None 이면 관계사 전체. 기본은 주력 계열사만(companies.py)

    def _list_form(self, page_no: int) -> dict[str, str]:
        return {
            "currentPageNo": str(page_no), "intNo": "0", "strVal": "", "strTxt": "", "strKey": "",
            "strCompany": "", "strType": "", "strOrderBy": "", "strEntity": "",
        }

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        postings: dict[str, Posting] = {}
        page_no, max_pages = 1, 1
        while page_no <= max_pages and page_no <= 20:   # 20 은 안전장치
            resp = f.post(f"{BASE}/hr/list.data", data=self._list_form(page_no))
            items, max_pages = parse_list_html(resp.text, self.key)
            for p in items:
                postings[p.external_id] = p
            page_no += 1
        return self.scope(list(postings.values()), self.companies)

    def fetch_detail(self, f: Fetcher, posting: Posting) -> str | None:
        resp = f.get(f"{BASE}/recruit/detail.data", params={"seqno": posting.external_id, "strCode": ""})
        data = resp.json()
        apply_detail(posting, data)
        return location_text_from_detail(data)
