"""CJ그룹 채용(recruit.cj.net) 수집기.

- robots.txt: `User-agent: * / Allow: /`.
- 이용약관(www.cj.net/footer/use-info)은 회원 대상이다("약관의 적용은 회원에 한하며"). 자동 수집 조항은 없고,
  제10조(3)2 에 "서비스 이용 중 습득한 정보를 상업적 목적으로 이용하거나 허가 없이 제3자에게 노출 금지"가 있다
  (삼성커리어스와 같은 유형). 로그인하지 않고 제목·기간·링크·직무명·근무지만 저장한다.
- 목록: POST /recruit/ko/recruit/recruit/searchNewGonggoList.fo (JSON, 같은 호스트). pageIndex 가 페이지 크기다.
  마감된 공고도 목록에 남아 있으므로 zz_close_yn 으로 가린다.
- 직무명(job_cd_nm, 예: 'Data Science', '데이터 엔지니어')과 근무지(location_cd_nm, 예: '서울', '수원(광교)')가 목록에 있어
  상세를 보지 않는다. 여러 직무를 묶은 공채 공고는 직무명이 '직군별'이라 제목으로만 판별된다.
- 공고 링크는 사이트의 '링크 복사' 버튼이 만드는 주소와 같다(gubun 1 = 공채, 2 = 수시).
"""
from __future__ import annotations

from datetime import datetime

from ..companies import CJ_MAJOR
from ..fetch import Fetcher
from ..models import Posting
from .base import Source

BASE = "https://recruit.cj.net"
LIST_URL = f"{BASE}/recruit/ko/recruit/recruit/searchNewGonggoList.fo"
LIST_BODY = {
    "pageVal": "1", "pageIndex": "400", "orderDesc": "1", "sch_title": "",
    "arrGubun": "", "arrRecBu": "", "arrRecJob": "", "arrRecArea": "", "schArea": "N",
}
CAREER = {"A": "신입", "B": "경력", "C": "인턴", "E": "신입/경력", "K": "기타"}
EMPLOYMENT = {"A": "정규", "B": "계약", "C": "기타", "D": "파견"}
NO_JOB_NAMES = {"", "직군별"}


def _dt(date: str | None, hh: str | None, mi: str | None) -> datetime | None:
    """'YYYY.MM.DD' + 시 + 분."""
    if not (date or "").strip():
        return None
    try:
        day = datetime.strptime(date.strip(), "%Y.%m.%d")
        return day.replace(hour=int((hh or "0").strip() or 0), minute=int((mi or "0").strip() or 0))
    except ValueError:
        return None


def parse_list(data: dict, source_key: str) -> list[Posting]:
    out: list[Posting] = []
    for it in data.get("ds_newRecruitList") or []:
        num = (it.get("zz_jo_num") or "").strip()
        if not num:
            continue
        page = "detail.fo?" if str(it.get("gubun")) == "1" else "bestDetail.fo?direct=N&"
        job = (it.get("job_cd_nm") or "").strip()
        title = (it.get("many_lng_zz_title") or it.get("zz_title") or "").replace("<BR>", " ").replace("<br>", " ")
        out.append(
            Posting(
                source=source_key,
                external_id=num,
                company=(it.get("compnm") or "CJ").strip(),
                title=" ".join(title.split()),
                url=f"{BASE}/recruit/ko/recruit/recruit/{page}zz_jo_num={num}",
                start_at=_dt(it.get("zz_str_dt_str"), it.get("zz_str_hh"), it.get("zz_str_mi")),
                end_at=None if it.get("zz_till_hire") == "Y" else _dt(it.get("zz_end_dt_str"), it.get("zz_end_hh"), it.get("zz_end_mi")),
                career_type=CAREER.get(it.get("zz_target_1") or ""),
                employment_type=EMPLOYMENT.get(it.get("zz_jo_type") or ""),
                status="접수마감" if it.get("zz_close_yn") == "Y" else "접수중",
                job_text="" if job in NO_JOB_NAMES else job,
                location_raw=(it.get("location_cd_nm") or "").strip() or None,
            )
        )
    return out


class CJSource(Source):
    site_url = f"{BASE}/recruit/ko/recruit/recruit/list.fo"

    def __init__(self, key: str = "cj", companies: set[str] | None = CJ_MAJOR):
        self.key = key
        self.company = "CJ (CJ그룹 채용)"
        self.companies = companies

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        data = f.post(LIST_URL, json=LIST_BODY).json()
        if data.get("ErrorCode") not in (0, None):
            raise RuntimeError(f"CJ 목록 오류: {data.get('SVC_ERR_MSG_TEXT')}")
        return self.scope(parse_list(data, self.key), self.companies)
