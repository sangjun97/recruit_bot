"""한화그룹 채용 '한화인'(www.hanwhain.com) 수집기.

- robots.txt: 페이지 호스트(www.hanwhain.com)에는 없다(앱 페이지가 돌아온다). 공고 데이터는 다른 호스트
  hwadm.hanwhain.com 의 포털 API 에서 오는데, 그 호스트의 /robots.txt 는 403 차단 안내 페이지를 돌려준다
  ("접속 가능한 네트워크 환경이 아닙니다"). robots 규칙은 어디에도 없고, 포털 API 는 사이트를 여는 모든 브라우저가
  직접 부르는 공개 경로다. 금지 규칙이 없고 아래 약관도 개인적인 이용을 막지 않아 2026-11-22 사용자 결정으로 추가했다.
- 이용약관: 자동 수집 조항은 없다. 제13조(회원의 의무)와 제16조 "이용자는 서비스를 이용함으로써 얻은 정보를 회사의 사전승낙
  없이 ... 영리목적으로 이용하거나 제 3자에게 이용하게 하여서는 안됩니다" 가 있다(삼성커리어스·현대자동차와 같은 유형).
  제목·기간·링크·직무명·근무지만 저장한다.
- 목록: POST hwadm.hanwhain.com/new-backend/portal/api/rcRecruit/search-rcrt (JSON). 접수 중인 공고만 온다.
  목록에는 직무·근무지·신입경력 구분이 없어, 저장할 공고만 상세(get-rcrt)를 한 번 읽는다.
- 상세: 모집 단위(unitDt)마다 직무명(ruNm)과 근무지(ruWorkpl)가 있다. 본문(ruDtlJob 등)과 문의처는 읽지 않는다.
- 공고 링크: www.hanwhain.com/portal/apply/recruit/detail?rtSeq=<rtSeq>
"""
from __future__ import annotations

from datetime import datetime

from ..companies import HANWHA_MAJOR
from ..fetch import Fetcher
from ..models import Posting
from .base import Source

SITE = "https://www.hanwhain.com"
API = "https://hwadm.hanwhain.com/new-backend/portal/api/rcRecruit"
PAGE_SIZE = 200


def _dt(s: str | None) -> datetime | None:
    try:
        return datetime.strptime((s or "").strip()[:16], "%Y.%m.%d %H:%M")
    except ValueError:
        return None


def _list_body(page: int) -> dict:
    return {
        "langCd": "ko", "searchText": "", "sdSeqList": None, "rtNrcrtYn": "", "rtCarrYn": "", "rtIntnYn": "",
        "rtPermanentWorkYn": "", "rtTempWorkYn": "", "djSeqList": None, "rjSeqList": None,
        "page": page, "size": PAGE_SIZE,
    }


def parse_list(data: dict, source_key: str) -> tuple[list[Posting], bool]:
    """목록 JSON → (공고들, 다음 페이지 여부)."""
    body = data.get("data") or {}
    out: list[Posting] = []
    for it in body.get("list") or []:
        seq = it.get("rtSeq")
        if seq is None:
            continue
        end = _dt(it.get("rtAcptEndDttm"))
        out.append(
            Posting(
                source=source_key,
                external_id=str(seq),
                company=(it.get("sdNm") or "한화").strip(),
                title=" ".join((it.get("rtNm") or "").split()),
                url=f"{SITE}/portal/apply/recruit/detail?rtSeq={seq}",
                start_at=_dt(it.get("rtAcptStrtDttm")),
                end_at=None if end and end.year >= 2029 else end,   # 인재풀 공고는 먼 날짜(2029.12.31)로 온다
                status="접수중",   # 목록에는 접수 중인 공고만 올라온다
            )
        )
    return out, bool(body.get("hasNext"))


def apply_detail(posting: Posting, data: dict) -> str | None:
    """상세에서 신입·경력 구분, 고용 형태, 직무명을 채우고 근무지 텍스트를 돌려준다."""
    item = (data.get("data") or {}).get("item") or {}
    career = [name for flag, name in (("rtNrcrtYn", "신입"), ("rtCarrYn", "경력"), ("rtIntnYn", "인턴")) if item.get(flag) == "Y"]
    employ = [name for flag, name in (("rtPermanentWorkYn", "정규"), ("rtTempWorkYn", "계약")) if item.get(flag) == "Y"]
    posting.career_type = "/".join(career) or posting.career_type
    posting.employment_type = "/".join(employ) or posting.employment_type
    units = item.get("unitDt") or []
    names = list(dict.fromkeys((u.get("ruNm") or "").strip() for u in units if (u.get("ruNm") or "").strip()))
    posting.job_text = "\n".join(names)
    lines = []
    for u in units:
        place = " ".join((u.get("ruWorkpl") or "").split())
        if place:
            name = (u.get("ruNm") or "").strip()
            lines.append(f"{name}: {place}" if name else place)
    return "\n".join(dict.fromkeys(lines))[:600] or None


class HanwhaSource(Source):
    site_url = f"{SITE}/portal/apply/recruit"

    def __init__(self, key: str = "hanwha", companies: set[str] | None = HANWHA_MAJOR):
        self.key = key
        self.company = "한화 (한화인)"
        self.companies = companies

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        postings: dict[str, Posting] = {}
        for page in range(10):   # 10 은 안전장치
            data = f.post(f"{API}/search-rcrt", json=_list_body(page)).json()
            items, has_next = parse_list(data, self.key)
            for p in items:
                postings[p.external_id] = p
            if not has_next or not items:
                break
        return self.scope(list(postings.values()), self.companies)

    def fetch_detail(self, f: Fetcher, posting: Posting) -> str | None:
        body = {"rtSeq": int(posting.external_id), "hidnKey": None, "langCd": "ko"}
        return apply_detail(posting, f.post(f"{API}/get-rcrt", json=body).json())
