"""LG Careers(careers.lg.com) 수집기. LG전자·LG화학·LG에너지솔루션·LG이노텍·LG유플러스 등 LG 계열사 전체 공고가 한 사이트에 올라온다.

- robots.txt 가 없다(요청하면 앱 페이지가 돌아온다). 공고 목록은 로그인 없이 공개.
- 목록: 페이지가 스스로 호출하는 POST api.careers.lg.com/rmk/search/retrieveJobNoticesList. 한 번에 전체 목록이 온다.
  각 항목에 시·도 단위 근무지(workLocationName)가 있다.
- 상세: POST api.careers.lg.com/rmk/job/retrieveJobNoticesDetail {jobNoticeId}. 근무지 자유 서술(workLocation,
  예: '가산, 창원, 마곡, 양재, 평택, 여의도')과 모집 직무별 locationName 이 있다.
- 공고 링크: https://careers.lg.com/apply/detail?id=<jobNoticeId>
- 저장 범위: 제목·기간·전형 구분·링크·근무지 문장만. 본문(detailContext)은 저장하지 않는다.
"""
from __future__ import annotations

import json
import time
from datetime import datetime

from playwright.sync_api import BrowserContext

from ..models import Posting
from .base import Source

BASE = "https://careers.lg.com"
API = "https://api.careers.lg.com"
LIST_BODY = {
    "lnbSearch": "", "hashTagText": "", "recDate": "POST_START_DATE", "order": "DESC",
    "careerList": [], "companyCodeList": [], "desireLocList": [], "jobGroupList": [],
}


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M", "%Y.%m.%d"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


def parse_list(data: dict, source_key: str) -> list[Posting]:
    out: list[Posting] = []
    for it in (data.get("data") or {}).get("jobNoticeList") or []:
        if it.get("noticeStatus") != "POSTING":
            continue  # '저장' 상태 등 게시 전 항목은 제외
        nid = it.get("jobNoticeId")
        if nid is None:
            continue
        out.append(
            Posting(
                source=source_key,
                external_id=str(nid),
                company=(it.get("companyName") or "LG").strip(),
                title=(it.get("jobNoticeName") or "").strip(),
                url=f"{BASE}/apply/detail?id={nid}",
                end_at=_dt(it.get("recEndDateTime")),
                career_type=it.get("careerTypeName") or None,
                employment_type=it.get("recruitTypeName") or None,
                status="접수중" if it.get("recAvail") else "접수마감",
                location_raw=(it.get("workLocationName") or "").strip() or None,
            )
        )
    return out


def location_text_from_detail(list_location: str | None, detail: dict) -> str | None:
    """목록의 시·도 + 상세의 근무지 서술 + 직무별 근무지를 한 텍스트로 합친다."""
    root = (detail.get("data") or {}).get("jobNoticesDetail") or {}
    jd = root.get("jobNoticesDetail") or {}
    lines: list[str] = []
    if list_location:
        lines.append(list_location)
    if (jd.get("workLocation") or "").strip():
        lines.append(jd["workLocation"].strip())
    for rec in root.get("recList") or []:
        loc = (rec.get("locationName") or "").strip()
        if loc:
            job = (rec.get("jobGroupName") or rec.get("orgName") or "").strip()
            lines.append(f"{job}: {loc}" if job else loc)
    return "\n".join(dict.fromkeys(lines)) or None


class LGCareersSource(Source):
    def __init__(self, key: str = "lg", companies: set[str] | None = None, delay_sec: float = 1.5):
        self.key = key
        self.company = "LG"
        self.companies = companies   # None 이면 계열사 전체. 예: {"LG전자", "LG화학"}
        self.delay_sec = delay_sec

    def _post(self, page, path: str, body: dict) -> dict:
        resp = page.request.post(f"{API}{path}", data=json.dumps(body), headers={"content-type": "application/json"})
        if resp.status != 200:
            raise RuntimeError(f"LG API {path} HTTP {resp.status}")
        return resp.json()

    def fetch_list(self, ctx: BrowserContext) -> list[Posting]:
        page = ctx.new_page()
        try:
            # 목록 페이지를 먼저 열어 페이지와 같은 세션·쿠키로 API 를 호출한다
            page.goto(f"{BASE}/apply", wait_until="networkidle", timeout=60_000)
            page.wait_for_timeout(800)
            data = self._post(page, "/rmk/search/retrieveJobNoticesList", LIST_BODY)
        finally:
            page.close()
        postings = parse_list(data, self.key)
        if self.companies:
            postings = [p for p in postings if p.company in self.companies]
        return postings

    def fetch_location_text(self, ctx: BrowserContext, posting: Posting) -> str | None:
        page = ctx.new_page()
        try:
            time.sleep(self.delay_sec)
            page.goto(posting.url, wait_until="domcontentloaded", timeout=60_000)
            detail = self._post(page, "/rmk/job/retrieveJobNoticesDetail", {"jobNoticeId": int(posting.external_id)})
        finally:
            page.close()
        jd = ((detail.get("data") or {}).get("jobNoticesDetail") or {}).get("jobNoticesDetail") or {}
        start = _dt(jd.get("recStartDate"))
        if start and posting.start_at is None:
            posting.start_at = start
        return location_text_from_detail(posting.location_raw, detail)
