"""HD현대 채용(recruit.hd.com) 수집기.

- robots.txt: `Disallow: /hdcareerAdministrator/` + `Allow: /`. 목록·상세·API 경로 모두 허용.
- 이용약관은 없고 법적고지가 있다: "사이트 내의 정보를 개인적인 용도로 사용하시거나 고객님의 컴퓨터에 저장하실 수 있습니다.
  ... 본 서버로의 링크 등은 가능합니다." 개인 용도·저장·링크를 명시적으로 허용한다.
- 목록: GET /api/v1/jobda/getRecruitNoticeList?isPost=true&LANG=KR (JSON, 같은 호스트).
  서버 쪽 필터가 없어 2024년 이후 공고 전체(600여 건, 약 1.5MB)가 한 번에 온다. 사이트에 부담을 주지 않도록
  3시간에 한 번만 받는다(min_interval_min).
- isInProgress 는 모든 행이 true 라 쓸 수 없다. 접수 기간(KST)으로 접수 중인 공고를 가린다.
- 공고 하나가 여러 모집 단위(recruitSectorList: 회사-직무-세부-지역)를 묶는다. 직무와 지역은 단위별로 읽는다.
  지역 칸에 '경력', '책임급' 같은 다른 값이 들어오기도 하므로 근무지 사전으로 걸러진다.
- 응답에 지원자 수(submittedResumeCount 등)와 공고 본문(contents)이 섞여 온다. 읽지도 저장하지도 않는다.
- 공고 링크: /kr/mainLayout/applyDetail/<recruitNoticeSn>
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..companies import HD_MAJOR
from ..fetch import Fetcher
from ..models import Posting
from .base import Source

BASE = "https://recruit.hd.com"
KST = timezone(timedelta(hours=9))
MAX_ROLES = 60


def _dt(s: str | None) -> datetime | None:
    try:
        return datetime.strptime((s or "").strip()[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _uniq(values) -> list[str]:
    return list(dict.fromkeys(v.strip() for v in values if v and v.strip()))


def parse_list(data: dict, source_key: str, now_kst: datetime) -> list[Posting]:
    """접수 기간 안에 있는 공고만 Posting 으로 바꾼다. now_kst 는 시간대 정보가 없는 한국 시각."""
    out: list[Posting] = []
    for it in data.get("data") or []:
        sn = it.get("recruitNoticeSn")
        start, end = _dt(it.get("receiveStartDatetime")), _dt(it.get("receiveEndDatetime"))
        if sn is None or not start or not end or not (start <= now_kst < end):
            continue
        units = it.get("recruitSectorList") or []
        roles = _uniq(" - ".join(x for x in ((u.get("job") or "").strip(), (u.get("jobDetail") or "").strip()) if x) for u in units)
        areas = _uniq(u.get("area") for u in units)
        out.append(
            Posting(
                source=source_key,
                external_id=str(sn),
                company=(it.get("companyCategory") or "HD현대").strip(),
                title=(it.get("recruitNoticeName") or "").strip(),
                url=f"{BASE}/kr/mainLayout/applyDetail/{sn}",
                start_at=start,
                end_at=None if end.year >= 2099 else end,   # 상시 인재풀은 2100-12-31 로 온다
                career_type=(it.get("recruitClassName") or "").strip() or None,
                employment_type=(it.get("recruitTypeName") or "").strip() or None,
                status="접수중",
                job_text="\n".join(roles[:MAX_ROLES]),
                location_raw="\n".join(areas[:30]) or None,
            )
        )
    return out


class HDHyundaiSource(Source):
    site_url = f"{BASE}/kr/mainLayout/apply"
    min_interval_min = 180

    def __init__(self, key: str = "hd", companies: set[str] | None = HD_MAJOR):
        self.key = key
        self.company = "HD현대 (HD현대 채용)"
        self.companies = companies

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        resp = f.get(f"{BASE}/api/v1/jobda/getRecruitNoticeList", params={"isPost": "true", "LANG": "KR"}, timeout=90)
        now_kst = datetime.now(KST).replace(tzinfo=None)
        return self.scope(parse_list(resp.json(), self.key, now_kst), self.companies)
