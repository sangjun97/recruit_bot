"""LG Careers(careers.lg.com) 수집기. LG전자·LG화학·LG에너지솔루션·LG이노텍·LG유플러스·LG CNS 등 LG 계열사 공고가 한 사이트에 올라온다.

- robots.txt 가 없다(careers.lg.com 은 앱 페이지, api.careers.lg.com 은 오류 페이지가 돌아온다). 공고는 로그인 없이 공개.
- 목록: POST api.careers.lg.com/rmk/search/retrieveJobNoticesList. 한 번에 전체 목록이 온다. 브라우저 없이 받을 수 있다.
  각 항목에 시·도 단위 근무지(workLocationName)와 대분류 직군(jobGroupName, 예: '연구/개발')이 있다.
- 상세: POST api.careers.lg.com/rmk/job/retrieveJobNoticesDetail {jobNoticeId}. 근무지 자유 서술(workLocation,
  예: '가산, 창원, 마곡, 양재, 평택, 여의도'), 모집 직무명(recruitJobName, recList[].jobGroupName), 직무별 locationName 이 있다.
- 공고 링크: https://careers.lg.com/apply/detail?id=<jobNoticeId>
- 저장 범위: 제목·기간·전형 구분·링크·직무명·근무지 문장만. 본문(detailContext)은 저장하지 않는다.
"""
from __future__ import annotations

from datetime import datetime

from ..companies import LG_MAJOR
from ..fetch import Fetcher
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
                location_raw=(it.get("workLocationName") or "").strip() or None,   # 시·도. 상세에서 보강한다
            )
        )
    return out


def _detail_parts(detail: dict) -> tuple[dict, list[dict]]:
    root = (detail.get("data") or {}).get("jobNoticesDetail") or {}
    return root.get("jobNoticesDetail") or {}, root.get("recList") or []


def location_text_from_detail(list_location: str | None, detail: dict) -> str | None:
    """목록의 시·도 + 상세의 근무지 서술 + 직무별 근무지를 한 텍스트로 합친다."""
    jd, rec_list = _detail_parts(detail)
    lines: list[str] = []
    if list_location:
        lines.append(list_location)
    if (jd.get("workLocation") or "").strip():
        lines.append(jd["workLocation"].strip())
    for rec in rec_list:
        loc = (rec.get("locationName") or "").strip()
        if loc:
            job = (rec.get("jobGroupName") or rec.get("orgName") or "").strip()
            lines.append(f"{job}: {loc}" if job else loc)
    return "\n".join(dict.fromkeys(lines)) or None


def job_text_from_detail(detail: dict) -> str:
    """상세의 모집 직무명(줄 단위): 공고의 recruitJobName 과 모집 단위별 jobGroupName."""
    jd, rec_list = _detail_parts(detail)
    names = [(jd.get("recruitJobName") or "").strip()]
    names += [(rec.get("jobGroupName") or "").strip() for rec in rec_list]
    return "\n".join(dict.fromkeys(n for n in names if n))


class LGCareersSource(Source):
    detail_for_classify = True
    site_url = f"{BASE}/apply"

    def __init__(self, key: str = "lg", companies: set[str] | None = LG_MAJOR):
        self.key = key
        self.company = "LG (LG Careers)"
        self.companies = companies   # None 이면 계열사 전체. 기본은 주력 계열사만(companies.py)

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        data = f.post(f"{API}/rmk/search/retrieveJobNoticesList", json=LIST_BODY).json()
        return self.scope(parse_list(data, self.key), self.companies)

    def fetch_detail(self, f: Fetcher, posting: Posting) -> str | None:
        detail = f.post(f"{API}/rmk/job/retrieveJobNoticesDetail", json={"jobNoticeId": int(posting.external_id)}).json()
        jd, _ = _detail_parts(detail)
        start = _dt(jd.get("recStartDate"))
        if start:
            posting.start_at = start
        posting.job_text = job_text_from_detail(detail)
        return location_text_from_detail(posting.location_raw, detail)
