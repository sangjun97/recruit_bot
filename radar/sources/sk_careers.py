"""SK Careers(www.skcareers.com) 수집기. SK그룹 계열사 공고가 한 사이트에 올라온다.

- robots.txt: `Allow: /Recruit` 가 명시돼 있고 `Disallow: /*?searchText=` 만 금지한다(검색어를 주소에 붙인 URL 을 만들지 말 것).
  SK하이닉스 Talent Hub(talent.skhynix.com)·SK이노베이션 계열(recruit.skinnovation.com)·SK텔레콤(careers.sktelecom.com)
  자체 사이트는 robots.txt 가 목록을 금지하므로 쓰지 않는다. 세 회사 공고는 이 사이트에 회사명으로 올라온다.
- 이용약관(2021-01-13)은 회원 대상이고 자동 수집 조항은 없다. 제10조(3)2 에 "서비스 이용 중 습득한 정보를 상업적 목적으로
  이용하거나 허가 없이 제3자에게 노출 금지"가 있다(삼성커리어스와 같은 형태). 제목·기간·링크·직무 분류·근무지 문장만 저장한다.
- 목록: POST /Recruit/GetRecruitList (form). 한 번에 전체 목록이 온다. 본문 키 7개를 모두 보내야 하고(빠지면 오류 페이지로 302),
  `Accept-Language: ko-KR` 이 없으면 값이 영어로 온다. 날짜는 '2026년 11월 22일(일)' 형식이고 시각은 없다.
- 상세: GET /Recruit/Detail/<noticeID> (서버 렌더링 HTML). 요약 상자에 마감 시간(23:59 또는 17:00)과 지역('경기/인천 - 용인')이 있다.
- 직무 분류(jobRole, 예: 'Tech R&D/Data Engineering')가 목록에 있어 상세를 보지 않고도 AI·데이터 직무를 가릴 수 있다.
"""
from __future__ import annotations

import re
from datetime import datetime

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from ..companies import SK_MAJOR
from ..fetch import Fetcher
from ..location import load_region_dict, pick_location_lines
from ..models import Posting
from .base import Source

BASE = "https://www.skcareers.com"
KO = {"Accept-Language": "ko-KR,ko;q=0.9"}
LIST_FORM = {   # 페이지가 보내는 기본값 그대로. sort=2 는 마감일 순
    "sort": "2", "searchText": "", "corpCode": "", "jobRole": "0",
    "recruitType": "", "workingType": "", "workingRegion": "",
}
KDATE_RE = re.compile(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일")
WS_RE = re.compile(r"\s+")


def _kdate(s: str | None) -> datetime | None:
    m = KDATE_RE.search(s or "")
    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def parse_list(data: dict, source_key: str) -> list[Posting]:
    out: list[Posting] = []
    for it in data.get("list") or []:
        nid = (it.get("noticeID") or "").strip()
        if not nid:
            continue
        end = _kdate(it.get("end"))
        remain = it.get("remainDay")
        # 직무 분류는 ' • ' 로 여러 묶음이 이어진다. 묶음 하나를 한 줄로 저장한다
        roles = [r.strip() for r in (it.get("jobRole") or "").split("•") if r.strip()]
        out.append(
            Posting(
                source=source_key,
                external_id=nid,
                company=(it.get("corpName") or "SK").strip(),
                title=(it.get("title") or "").strip(),
                url=f"{BASE}/Recruit/Detail/{nid}",
                start_at=_kdate(it.get("start")),
                end_at=end.replace(hour=23, minute=59) if end else None,
                end_date_only=True,   # 목록에는 날짜만 있다. 마감 시각은 상세에서 받는다
                career_type=(it.get("recruitType") or "").strip() or None,
                employment_type=(it.get("workingType") or "").strip() or None,
                status="접수마감" if isinstance(remain, int) and remain < 0 else "접수중",
                job_text="\n".join(roles),
                location_raw=(it.get("workingArea") or "").strip() or None,   # 넓은 권역(예: '경기/인천'). 상세에서 보강
            )
        )
    return out


def parse_detail(html: str) -> dict:
    """상세 요약 상자의 항목(라벨 → 값 목록)과 본문의 근무지 관련 줄을 읽는다. 본문은 돌려주지 않는다."""
    tree = HTMLParser(html)
    fields: dict[str, list[str]] = {}
    label = ""
    for item in tree.css(".floating-box .box-detail-item"):
        lab, val = item.css_first(".label"), item.css_first(".value")
        name = WS_RE.sub(" ", lab.text() if lab else "").strip()
        if name:
            label = name   # 값이 여러 개면 라벨이 빈 행이 이어진다
        value = WS_RE.sub(" ", val.text() if val else "").strip()
        if label and value:
            fields.setdefault(label, []).append(value)
    body = tree.css_first(".detail-content-box")
    body_lines = pick_location_lines(body.text(separator="\n") if body else "", max_lines=4) or ""
    return {"fields": fields, "location_lines": [ln for ln in body_lines.splitlines() if ln]}


def location_text(list_area: str | None, detail: dict) -> str | None:
    """가장 구체적인 근무지 텍스트를 고른다.

    지역 행의 세부 지명('경기/인천 - 용인' 의 '용인')과 본문의 근무지 줄에서 지역이 잡히면 그것만 쓰고,
    안 잡히면 넓은 권역 표기('경기/인천')로 물러난다. 권역 표기를 같이 넣으면 '인천'이 근무지로 잘못 잡힌다.
    """
    areas = detail["fields"].get("지역") or []
    specifics = [a.split(" - ", 1)[1].strip() for a in areas if " - " in a]
    specific_text = "\n".join(dict.fromkeys(specifics + detail["location_lines"]))
    if specific_text and load_region_dict().extract(specific_text):
        return specific_text
    broad = "\n".join(dict.fromkeys(a.split(" - ", 1)[0].strip() for a in areas)) or (list_area or "")
    return "\n".join(x for x in (broad, specific_text) if x) or None


class SkCareersSource(Source):
    site_url = f"{BASE}/Recruit"

    def __init__(self, key: str = "sk", companies: set[str] | None = SK_MAJOR):
        self.key = key
        self.company = "SK (SK Careers)"
        self.companies = companies   # None 이면 계열사 전체. 기본은 주력 계열사만(companies.py)

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        resp = f.post(f"{BASE}/Recruit/GetRecruitList", data=LIST_FORM, headers=KO)
        data = resp.json()   # 요청이 잘못되면 오류 페이지(HTML)로 넘어가 여기서 실패한다
        if not data.get("success"):
            raise RuntimeError("SK Careers 목록 응답이 success 가 아님")
        return self.scope(parse_list(data, self.key), self.companies)

    def fetch_detail(self, f: Fetcher, posting: Posting) -> str | None:
        detail = parse_detail(f.get(posting.url, headers=KO).text)
        m = re.fullmatch(r"(\d{1,2}):(\d{2})", (detail["fields"].get("마감 시간") or [""])[0])
        if m and posting.end_at:
            posting.end_at = posting.end_at.replace(hour=int(m.group(1)), minute=int(m.group(2)))
            posting.end_date_only = False
        return location_text(posting.location_raw, detail)
