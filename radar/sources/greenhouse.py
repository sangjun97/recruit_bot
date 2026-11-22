"""Greenhouse 채용 솔루션의 공개 Job Board API 로 받는 수집기. 쿠팡과 크래프톤이 쓴다.

- 두 회사의 자체 채용 사이트는 자동화된 접근을 막는다(쿠팡 coupang.jobs 는 봇 확인 화면, 크래프톤 krafton.com 은 403).
  공고 페이지를 읽을 수 없어서, 두 회사가 공고를 올리는 채용 솔루션(Greenhouse)의 공개 API 로 받는다
  (2026-11-22 사용자 결정: 공개 API 로 받는 것도 추가).
- API: GET https://boards-api.greenhouse.io/v1/boards/<이름>/jobs. 인증 없이 열려 있고 문서화돼 있다
  (docs.greenhouse.io/job-board.html). 이 호스트의 robots.txt 는 `/embed/` 만 금지한다.
- 한 번에 전체 목록이 온다(쿠팡 약 520KB, 전 세계 공고 포함). 서버에 부담을 주지 않도록 수집 간격을 둔다.
- 마감일은 대부분 없다. 목록에서 사라지면 마감으로 본다.
- 목록에는 제목·근무 도시·게시일과 회사가 정한 부가 항목(metadata)만 있다. 본문은 받지 않는다(content 를 요청하지 않는다).
- 공고 링크는 API 가 주는 주소(absolute_url) 그대로다. 사람이 브라우저로 열면 각 회사의 지원 페이지로 간다.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from ..fetch import Fetcher
from ..models import Posting
from .base import Source

API = "https://boards-api.greenhouse.io/v1/boards"
KST = timezone(timedelta(hours=9))
EMPLOYMENT = {
    "Regular": "정규", "Contractor": "계약", "Professional Contractor": "계약", "Internship": "인턴",
    "Full-time": "정규", "Contract": "계약", "Intern": "인턴",
}
CAREER_HINTS = [
    (re.compile(r"인턴|Intern", re.I), "인턴"),
    (re.compile(r"신입\s*가능|신입/경력|신입·경력"), "신입/경력"),
    (re.compile(r"신입|New\s*Grad", re.I), "신입"),
    (re.compile(r"\d+\s*년\s*이상|경력|Senior|Sr\.|Staff|Principal|Lead|Director|Manager", re.I), "경력"),
]


def _kst(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso).astimezone(KST).replace(tzinfo=None)
    except ValueError:
        return None


def _career(title: str) -> str | None:
    for pattern, label in CAREER_HINTS:
        if pattern.search(title):
            return label
    return None


def parse_jobs(data: dict, source_key: str, company: str, location_filter: re.Pattern | None = None) -> list[Posting]:
    """API 응답을 Posting 으로 바꾼다. location_filter 가 있으면 근무지가 맞는 공고만 남긴다(전 세계 공고가 섞인 게시판용)."""
    out: list[Posting] = []
    for it in data.get("jobs") or []:
        jid = it.get("id")
        location = ((it.get("location") or {}).get("name") or "").strip()
        if jid is None or (location_filter is not None and not location_filter.search(location)):
            continue
        meta = {m.get("name"): m.get("value") for m in it.get("metadata") or [] if isinstance(m.get("value"), str)}
        # 회사가 붙인 직무 분류(예: 크래프톤의 'Job Category - Data' = 'Machine Learning')를 직무 텍스트로 쓴다
        categories = [v.strip() for k, v in meta.items() if k and k.startswith("Job Category") and v.strip()]
        title = " ".join((it.get("title") or "").split())
        out.append(
            Posting(
                source=source_key,
                external_id=str(jid),
                company=company,
                title=title,
                url=(it.get("absolute_url") or "").strip(),
                start_at=_kst(it.get("first_published")),
                end_at=_kst(it.get("application_deadline")),
                career_type=_career(title),
                employment_type=EMPLOYMENT.get(meta.get("Employment Type") or ""),
                status="접수중",   # 게시판에는 접수 중인 공고만 올라온다
                job_text="\n".join(dict.fromkeys(categories)),
                location_raw=location or None,
            )
        )
    return [p for p in out if p.url]


class GreenhouseSource(Source):
    def __init__(
        self, key: str, company: str, board: str, site_url: str,
        location_filter: str | None = None, min_interval_min: int = 60,
    ):
        self.key = key
        self.company = company
        self.board = board
        self.site_url = site_url
        self.location_filter = re.compile(location_filter, re.I) if location_filter else None
        self.min_interval_min = min_interval_min

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        data = f.get(f"{API}/{self.board}/jobs", timeout=60).json()
        if "jobs" not in data:
            raise RuntimeError(f"Greenhouse 응답에 jobs 가 없음: {self.board}")
        return parse_jobs(data, self.key, self.company, self.location_filter)
