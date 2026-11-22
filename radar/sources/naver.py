"""네이버 채용(recruit.navercorp.com) 수집기. 네이버와 주요 자회사(클라우드·랩스·웹툰·파이낸셜·스노우) 공고가 올라온다.

- robots.txt 없음(404). 이용약관 페이지도 없다(개인정보 처리방침만 있음).
- 목록: GET /rcrt/loadJobList.do (같은 호스트). 응답 헤더는 text/html 이지만 본문은 JSON 이다. 한 번에 10건씩 온다.
- 직무 분류는 행에 첫 번째 세부 직무 이름(subJobCdNm)만 실려 온다. 그래서 전체 목록에 더해
  AI/ML·Data Engineering·Data Science 직무 코드로 거른 목록을 한 번 더 받아, 거기 나온 공고에 직무 표시를 붙인다.
- 근무지는 목록의 지역 코드(분당·서울·춘천·세종)라 상세를 보지 않는다.
- 공고 링크: /rcrt/view.do?annoId=<annoId>&lang=ko
"""
from __future__ import annotations

from datetime import datetime

from ..companies import NAVER_MAJOR
from ..fetch import Fetcher
from ..models import Posting
from .base import Source

BASE = "https://recruit.navercorp.com"
LIST_URL = f"{BASE}/rcrt/loadJobList.do"
PAGE = 10
AI_SUB_JOBS = "1010005,1010006,1010009"   # AI/ML, Data Engineering, Data Science
AI_JOB_LABEL = "AI/ML·Data Engineering·Data Science (네이버 직무 분류)"
COMPANY_KO = {
    "NAVER": "네이버", "NAVER Cloud": "네이버클라우드", "NAVER LABS": "네이버랩스", "NAVER WEBTOON": "네이버웹툰",
    "NAVER FINANCIAL": "네이버파이낸셜", "SNOW": "스노우", "NAVER I&S": "네이버아이앤에스",
}
WORK_AREA = {"0010": "분당", "0020": "서울", "0030": "춘천", "0040": "세종", "0050": "글로벌"}
OPEN_ENDED_YEARS = (2099, 2999)   # 채용시 마감, 상시모집


def _dt(s: str | None) -> datetime | None:
    try:
        return datetime.strptime((s or "").strip()[:19], "%Y.%m.%d %H:%M:%S")
    except ValueError:
        return None


def parse_list(data: dict, source_key: str) -> tuple[list[Posting], int]:
    """목록 JSON → (공고들, 전체 건수)."""
    out: list[Posting] = []
    for it in data.get("list") or []:
        aid = it.get("annoId")
        if aid is None:
            continue
        end = _dt(it.get("endYmdTime"))
        company = (it.get("sysCompanyCdNm") or "NAVER").strip()
        out.append(
            Posting(
                source=source_key,
                external_id=str(aid),
                company=COMPANY_KO.get(company, company),
                title=(it.get("annoSubject") or "").strip(),
                url=f"{BASE}/rcrt/view.do?annoId={aid}&lang=ko",
                start_at=_dt(it.get("staYmdTime")),
                end_at=None if end and end.year in OPEN_ENDED_YEARS else end,
                career_type=(it.get("entTypeCdNm") or "").strip() or None,
                employment_type=(it.get("empTypeCdNm") or "").strip() or None,
                status="접수중",   # 목록에는 채용 진행 중인 공고만 올라온다
                job_text=(it.get("subJobCdNm") or "").strip(),
                location_raw=WORK_AREA.get(it.get("workAreaCd") or ""),
            )
        )
    return out, int(data.get("totalSize") or 0)


class NaverSource(Source):
    site_url = f"{BASE}/rcrt/list.do"

    def __init__(self, key: str = "naver", companies: set[str] | None = NAVER_MAJOR):
        self.key = key
        self.company = "네이버 (NAVER Careers)"
        self.companies = companies

    def _fetch_all(self, f: Fetcher, sub_jobs: str = "") -> list[Posting]:
        found: dict[str, Posting] = {}
        first, total = 0, 1
        while first < total and first < 500:   # 500 은 안전장치
            params = {
                "annoId": "", "sw": "", "subJobCdArr": sub_jobs, "sysCompanyCdArr": "", "empTypeCdArr": "",
                "entTypeCdArr": "", "workAreaCdArr": "", "firstIndex": first,
            }
            data = f.get(LIST_URL, params=params).json()
            if "list" not in data:
                raise RuntimeError("네이버 목록 응답에 list 가 없음")
            items, total = parse_list(data, self.key)   # 결과가 0건이면 result 가 'N' 으로 온다(오류 아님)
            if not items:
                break
            for p in items:
                found[p.external_id] = p
            first += PAGE
        return list(found.values())

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        postings = self._fetch_all(f)
        ai_ids = {p.external_id for p in self._fetch_all(f, AI_SUB_JOBS)} if postings else set()
        for p in postings:
            if p.external_id in ai_ids:
                p.job_text = "\n".join(x for x in (p.job_text, AI_JOB_LABEL) if x)
        return self.scope(postings, self.companies)
