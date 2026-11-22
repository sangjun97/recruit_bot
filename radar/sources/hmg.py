"""현대자동차(talent.hyundai.com)·기아(career.kia.com) 수집기. 두 사이트는 같은 시스템을 쓴다.

- robots.txt: 현대자동차는 `Allow: /` 뿐이다. 기아는 `Allow: /` 에 채용과 무관한 26개 페이지만 금지한다
  (목록 /apply/applyList.kc, 상세 /apply/applyView.kc, /api/ 는 허용).
- 이용약관: 자동 수집 조항은 없다. 제13조(회원의 의무)와 제17조 2 "이용자는 서비스를 이용함으로써 얻은 정보를 회사의
  사전승낙 없이 ... 영리목적으로 이용하거나 제3자에게 이용하게 하여서는 안됩니다" 가 있다(삼성커리어스와 같은 유형).
  제17조는 회원이 아닌 방문자에게도 적용되므로 사용자 승인 전까지는 기본 실행에서 빼 두었다
  (radar/sources/__init__.py 의 PENDING_SOURCES). 수집할 때는 제목·기간·링크·직무 분류·근무지만 저장한다.
- 목록: GET /api/rec/AP-{HM|KM}-FO-02700 (JSON, 같은 호스트). 접수 중인 공고만 온다. `X-HKMC-*` 헤더가 없으면
  기아는 400(HTML)을 돌려준다. HTML 페이지는 대기열(NetFunnel) 뒤에 있지만 JSON API 는 그렇지 않다.
- 공고 링크: /apply/applyView.{hc|kc}?recuYy=..&recuType=..&recuCls=..
- 근무지는 목록의 사업장 이름(workPlaceCodeNm, 예: '양재본사', '남양연구소')이라 상세를 보지 않는다.
"""
from __future__ import annotations

from datetime import datetime

from ..fetch import Fetcher
from ..models import Posting
from .base import Source

PAGE_SIZE = 200
NO_JOB_NAMES = {"", "직무별 상이"}


def _dt(date: str | None, time: str | None) -> datetime | None:
    """'YYYYMMDD' + 'HHMM'."""
    if not date:
        return None
    try:
        return datetime.strptime(f"{date}{(time or '0000')[:4]:0<4}", "%Y%m%d%H%M")
    except ValueError:
        return None


def parse_list(data: dict, source_key: str, company: str, base: str, view_ext: str) -> tuple[list[Posting], int]:
    """목록 JSON → (공고들, 전체 건수)."""
    body = data.get("data") or {}
    out: list[Posting] = []
    for it in body.get("list") or []:
        yy, typ, cls = it.get("recuYy"), it.get("recuType"), it.get("recuCls")
        if not yy or not typ or cls is None:
            continue
        field = (it.get("fldCodeNm") or "").strip()
        end = _dt(it.get("applyEndDt"), it.get("applyEndTm"))
        out.append(
            Posting(
                source=source_key,
                external_id=f"{yy}-{typ}-{cls}",
                company=company,
                title=(it.get("recuNoticeNm") or "").strip(),
                url=f"{base}/apply/applyView.{view_ext}?recuYy={yy}&recuType={typ}&recuCls={cls}",
                start_at=_dt(it.get("applyStartDt"), it.get("applyStartTm")),
                end_at=end,
                career_type=(it.get("channelCodeNm") or "").strip() or None,
                status="접수중",   # 목록에는 접수 중인 공고만 올라온다
                job_text="" if field in NO_JOB_NAMES else field,
                location_raw=(it.get("workPlaceCodeNm") or "").strip() or None,
            )
        )
    return out, int(body.get("listCnt") or len(out))


class HyundaiMotorGroupSource(Source):
    def __init__(self, key: str, company: str, base: str, hgr_cd: str, service: str, view_ext: str):
        self.key = key
        self.company = company
        self.base = base
        self.hgr_cd = hgr_cd          # 1 = 현대자동차, 2 = 기아
        self.service = service        # 'HM' / 'KM'
        self.view_ext = view_ext      # 'hc' / 'kc'
        self.site_url = f"{base}/apply/applyList.{view_ext}"
        # 사이트의 화면이 API 를 부를 때 붙이는 헤더. 로그인하지 않은 상태의 값(null) 그대로다
        self.headers = {"X-HKMC-SERVICE": service, "X-HKMC-TOKEN": "null", "X-HKMC-EMP-TOKEN": "null"}

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        url = f"{self.base}/api/rec/AP-{self.service}-FO-02700"
        postings: dict[str, Posting] = {}
        page, total = 1, 1
        while len(postings) < total and page <= 10:   # 10 은 안전장치
            params = {
                "hgrCd": self.hgr_cd, "lang": "ko", "page": page, "pageblock": PAGE_SIZE,
                "searchSectorList": "", "searchPlaceList": "", "searchText": "",
            }
            resp = f.get(url, params=params, headers=self.headers)
            if "json" not in resp.headers.get("content-type", ""):
                raise RuntimeError(f"{self.company} 목록 응답이 JSON 이 아님 (HTTP {resp.status_code})")
            items, total = parse_list(resp.json(), self.key, self.company, self.base, self.view_ext)
            if not items:
                break
            for p in items:
                postings[p.external_id] = p
            page += 1
        return list(postings.values())
