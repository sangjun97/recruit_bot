"""카카오 영입(careers.kakao.com) 수집기. 카카오 본사 공고와, '[공동체]' 로 실리는 계열사(카카오페이·카카오모빌리티 등) 공고가 올라온다.

- robots.txt 없음: /robots.txt 가 401 빈 응답이다. 없는 경로는 모두 401 이고 실제 파일은 200 이라 '파일 없음'으로 읽었다.
- 이용약관(/etc/agreement)은 회원 대상이다. 자동 수집 조항은 없고 제10조(3)2 에 "서비스 이용 중 습득한 정보를 상업적 목적으로
  이용하거나 허가 없이 제3자에게 노출시키는 행위" 금지가 있다(삼성커리어스와 같은 유형). 제목·기간·링크·근무지만 저장한다.
- 목록: GET /public/api/job-list (JSON, 같은 호스트, 15건씩). part 를 비우면 테크만 오므로 직군별로 따로 받는다.
  AI·데이터 직무는 테크와 서비스비즈에 있어 그 둘만 받는다. company=ALL 이면 계열사 공고도 온다.
- 목록 행에 공고 본문(introduction, workContentDesc 등)이 통째로 실려 온다. 읽지도 저장하지도 않는다.
- 마감일(endDate)은 대부분 없다('영입 종료 시'). 목록에서 사라지면 마감으로 본다.
- 신입·경력 구분은 제목 끝의 괄호에만 있다: 'Data Scientist (경력)'.
- 공고 링크: /jobs/<realId>
"""
from __future__ import annotations

import html
import re
from datetime import datetime

from ..companies import KAKAO_MAJOR
from ..fetch import Fetcher
from ..models import Posting
from .base import Source

BASE = "https://careers.kakao.com"
PARTS = ("TECHNOLOGY", "BUSINESS_SERVICES")
CAREER_RE = re.compile(r"\((신입/경력|경력/신입|신입|경력|인턴)[^)]*\)")


def _dt(s: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat((s or "").strip()[:19])
    except ValueError:
        return None


def parse_list(data: dict, source_key: str) -> tuple[list[Posting], int]:
    """목록 JSON → (공고들, 전체 페이지 수)."""
    out: list[Posting] = []
    for it in data.get("jobList") or []:
        rid = (it.get("realId") or "").strip()
        if not rid:
            continue
        title = " ".join(html.unescape(it.get("jobOfferTitle") or "").split())
        m = CAREER_RE.search(title)
        skills = [s.get("skillSetName", "").strip() for s in it.get("skillSetList") or [] if s.get("skillSetName")]
        out.append(
            Posting(
                source=source_key,
                external_id=rid,
                company=(it.get("companyName") or "카카오").strip(),
                title=title,
                url=f"{BASE}/jobs/{rid}",
                start_at=_dt(it.get("regDate")),
                end_at=_dt(it.get("endDate")),
                career_type=m.group(1) if m else None,
                employment_type=(it.get("employeeTypeName") or "").strip() or None,
                status="접수마감" if it.get("closeFlag") else "접수중",
                job_text="\n".join(dict.fromkeys(skills)),
                location_raw=(it.get("locationName") or "").strip() or None,
            )
        )
    return out, int(data.get("totalPage") or 1)


class KakaoSource(Source):
    site_url = f"{BASE}/jobs"

    def __init__(self, key: str = "kakao", companies: set[str] | None = KAKAO_MAJOR):
        self.key = key
        self.company = "카카오 (카카오 영입)"
        self.companies = companies

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        found: dict[str, Posting] = {}
        for part in PARTS:
            page, pages = 1, 1
            while page <= pages and page <= 20:   # 20 은 안전장치
                params = {"skillSet": "", "part": part, "company": "ALL", "keyword": "", "employeeType": "", "page": page}
                data = f.get(f"{BASE}/public/api/job-list", params=params, headers={"Accept": "application/json"}).json()
                items, pages = parse_list(data, self.key)
                for p in items:
                    found[p.external_id] = p
                page += 1
        return self.scope(list(found.values()), self.companies)
