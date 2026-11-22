"""KT그룹 채용(recruit.kt.com) 수집기. KT 와 그룹사(kt cloud, kt ds 등) 공고가 올라온다.

- robots.txt: `User-agent: * / Allow: /`. 이용약관 페이지는 없다(개인정보처리방침만 있음).
- 목록: GET /api/recruit (JSON, 같은 호스트, 한 번에 전체). isInProgress=true 에는 접수가 끝나고 전형 중인 공고도
  섞여 있으므로 isInTime(접수 중)과 isTimeBefore(접수 예정)로 가린다.
- 공고 하나가 여러 모집 분야(recruitSectorList: 'AI서비스개발-서울(수서)', '물류-고양')를 묶는다.
  분야 이름에 직무와 지역이 함께 들어 있어 직무 판별과 근무지 추출 양쪽에 쓴다. 본문은 대부분 이미지라 쓰지 않는다.
- 응답에 지원자 수(submittedResumeCount 등)가 섞여 온다. 읽지도 저장하지도 않는다.
- 공고 링크: /careers/<recruitNoticeSn>
"""
from __future__ import annotations

from datetime import datetime

from ..companies import KT_MAJOR
from ..fetch import Fetcher
from ..models import Posting
from .base import Source

BASE = "https://recruit.kt.com"
PAGE_SIZE = 100
MAX_SECTORS = 60


def _dt(s: str | None) -> datetime | None:
    try:
        return datetime.strptime((s or "").strip()[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def parse_list(data: dict, source_key: str) -> list[Posting]:
    out: list[Posting] = []
    for it in data.get("data") or []:
        sn = it.get("recruitNoticeSn")
        if sn is None or not (it.get("isInTime") or it.get("isTimeBefore")):
            continue
        sectors = list(dict.fromkeys(
            (s.get("recruitSectorName") or "").strip() for s in it.get("recruitSectorList") or [] if (s.get("recruitSectorName") or "").strip()
        ))[:MAX_SECTORS]
        end = _dt(it.get("receiveEndDatetime"))
        out.append(
            Posting(
                source=source_key,
                external_id=str(sn),
                company=" ".join((it.get("company") or "KT").split()),
                title=(it.get("title") or it.get("recruitNoticeName") or "").strip(),
                url=f"{BASE}/careers/{sn}",
                start_at=_dt(it.get("receiveStartDatetime")),
                end_at=end,
                career_type=(it.get("recruitClassName") or "").strip() or None,
                employment_type=(it.get("recruitTypeName") or "").strip() or None,
                status="접수중" if it.get("isInTime") else "접수예정",
                job_text="\n".join(sectors),
                location_raw="\n".join(sectors) or None,
            )
        )
    return out


class KTSource(Source):
    site_url = f"{BASE}/careers/"

    def __init__(self, key: str = "kt", companies: set[str] | None = KT_MAJOR):
        self.key = key
        self.company = "KT (KT그룹 채용)"
        self.companies = companies

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        found: dict[str, Posting] = {}
        for page in range(1, 6):   # 5 는 안전장치
            params = {"currentPage": page, "pageSize": PAGE_SIZE, "isInProgress": "true", "isContainsContents": "false"}
            data = f.get(f"{BASE}/api/recruit", params=params, headers={"Accept": "application/json"}).json()
            if not data.get("isSuccess"):
                raise RuntimeError(f"KT 목록 오류: {data.get('errorMessage')}")
            for p in parse_list(data, self.key):
                found[p.external_id] = p
            if len(data.get("data") or []) < PAGE_SIZE:
                break
        return self.scope(list(found.values()), self.companies)
