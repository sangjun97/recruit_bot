"""신세계그룹 채용(job.shinsegae.com) 수집기.

- robots.txt 없음(404 로 앱 페이지가 돌아온다).
- 이용약관(/trms/tos)은 약관에 동의한 회원 대상이다. 자동 수집 조항은 없고 제11조 9호에 "서비스를 이용하여 얻은 정보를
  회사의 사전 승낙없이 복제 또는 유통시키거나 상업적으로 이용하거나 배포하는 행위" 금지가 있다(삼성커리어스와 같은 유형).
  가입·로그인하지 않고 제목·기간·링크·직무 분류·근무지 문장만 저장한다.
- 목록: GET /api/rcrut (JSON, 같은 호스트, 한 번에 전체). 접수 중인 공고만 온다.
  응답에 담당자 ID·내부 IP 같은 관리용 필드가 섞여 있다. 읽지도 저장하지도 않는다.
- 직무 분류(dutyNm)는 'IT/디지털' 등 7개 대분류뿐이라 AI·데이터 판별은 제목으로 한다.
- 상세: GET /api/rcrut/<id>. 근무지는 직무 소개(dutyInfoCn) 안의 자유 서술이다. 문의처(inqplCn)는 읽지 않는다.
- 공고 링크: /rcrut/detail/<id>
"""
from __future__ import annotations

import re
from datetime import datetime

from ..companies import SHINSEGAE_MAJOR
from ..fetch import Fetcher
from ..location import pick_location_lines
from ..models import Posting
from .base import Source

BASE = "https://job.shinsegae.com"
TAG_RE = re.compile(r"<[^>]+>")


def _dt(s: str | None) -> datetime | None:
    s = (s or "").strip()
    for fmt, size in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H:%M", 16), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(s[:size], fmt)
        except ValueError:
            continue
    return None


def parse_list(data: dict, source_key: str) -> list[Posting]:
    out: list[Posting] = []
    for it in data.get("body") or []:
        pid = it.get("pbancBscNo")
        if pid is None or it.get("delYn") == "Y":
            continue
        duties = [d.get("dutyNm", "").strip() for d in it.get("dutySeCd") or [] if d.get("dutyNm")]
        out.append(
            Posting(
                source=source_key,
                external_id=str(pid),
                company=(it.get("coNm") or "신세계").strip(),
                title=(it.get("pbancNm") or "").strip(),
                url=f"{BASE}/rcrut/detail/{pid}",
                start_at=_dt(it.get("rcptBgngDt")),
                end_at=_dt(it.get("rcptEndDt")),
                career_type=(it.get("rcrutSeNm") or "").strip() or None,
                status="접수중",   # 목록에는 게시 중인 공고만 올라온다
                job_text="\n".join(dict.fromkeys(duties)),
            )
        )
    return out


def location_text_from_detail(data: dict) -> str | None:
    """상세의 직무 소개에서 근무지 관련 줄만 고른다."""
    body = data.get("body") or {}
    html = body.get("dutyInfoCn") or ""
    text = TAG_RE.sub("\n", html.replace("&nbsp;", " "))
    return pick_location_lines(text, max_lines=4)


class ShinsegaeSource(Source):
    site_url = f"{BASE}/rcrut"

    def __init__(self, key: str = "shinsegae", companies: set[str] | None = SHINSEGAE_MAJOR):
        self.key = key
        self.company = "신세계 (신세계그룹 채용)"
        self.companies = companies

    def _get(self, f: Fetcher, url: str, **kw) -> dict:
        data = f.get(url, **kw).json()
        if data.get("resultCode") != "0000":
            raise RuntimeError(f"신세계 API 오류: {data.get('resultMessage')}")
        return data

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        # 사이트가 목록을 열 때 보내는 조건 그대로(신입 10, 경력 11)
        data = self._get(f, f"{BASE}/api/rcrut", params=[("sort", "1"), ("rcrutSeCd", "10"), ("rcrutSeCd", "11")])
        return self.scope(parse_list(data, self.key), self.companies)

    def fetch_detail(self, f: Fetcher, posting: Posting) -> str | None:
        return location_text_from_detail(self._get(f, f"{BASE}/api/rcrut/{posting.external_id}"))
