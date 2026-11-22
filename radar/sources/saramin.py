"""사람인(saramin.co.kr)의 기업별 공고 페이지 수집기. 공식 채용 사이트를 읽을 수 없는 회사를 보완하는 용도로만 쓴다.

- 2026-11-22 사용자 결정: 공식 사이트에서 모으기 어려운 회사는 채용 포털을 거쳐서라도 모은다.
- robots.txt: `Allow: /zf_user/company-info/` (기업 정보·기업별 공고 목록)가 명시돼 있다. 공고 상세(/zf_user/jobs/relay/view)도
  금지 목록에 없다. 상세는 열지 않고 링크만 건다.
- 이용약관(개인회원 약관)은 회원 대상이다. 자동 수집 조항은 없고 "서비스를 이용하여 얻은 정보를 회사의 사전동의 없이 복사, 복제 …
  하거나 이를 타인에게 제공할 수 없습니다"(회원), "사이트의 정보 및 서비스를 이용한 영리 행위" 금지가 있다. 가입·로그인하지 않는다.
- 목록: GET /zf_user/company-info/view-inner-recruit?csn=<기업 식별값>. 그 회사가 직접 올린 공고만 나온다
  (키워드 검색은 '롯데카드 상담사' 같은 파견·대행 업체 공고가 대부분이라 쓰지 않는다).
  접수가 끝난 공고도 한동안 목록에 남는다. '접수마감' 표시로 가린다.
- 마감일은 '~11.01(일)' 처럼 연도 없이 온다. 오늘 기준으로 가까운 해로 채운다. '채용시'·'상시채용'은 마감일 없음.
- 저장하는 것: 제목, 직무 분류, 근무지, 경력·고용 형태, 마감일, 사람인 공고 링크. 본문은 읽지 않는다.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from ..fetch import Fetcher
from ..models import Posting
from .base import Source

BASE = "https://www.saramin.co.kr"
KST = timezone(timedelta(hours=9))
REC_ID_RE = re.compile(r"rec_idx=(\d+)")
MD_RE = re.compile(r"(\d{1,2})[./](\d{1,2})")
AGO_RE = re.compile(r"(\d+)\s*일\s*전")


def _end_date(text: str, today: datetime) -> datetime | None:
    """'~11.01(일)', '오늘마감', '내일마감', '채용시', '상시채용' → 마감 시각(날짜만 있으므로 23:59)."""
    text = text.strip()
    if "오늘" in text:
        day = today
    elif "내일" in text:
        day = today + timedelta(days=1)
    else:
        m = MD_RE.search(text)
        if not m:
            return None
        day = today.replace(month=int(m.group(1)), day=int(m.group(2)))
        # 연도가 없다. 넉 달 넘게 지난 날짜로 읽히면 내년 것으로 본다(12월에 보는 '~01.18')
        if day < today - timedelta(days=120):
            day = day.replace(year=today.year + 1)
    return day.replace(hour=23, minute=59, second=0, microsecond=0)


def _career(text: str) -> str | None:
    if "신입" in text and "경력" in text:
        return "신입/경력"
    if "경력무관" in text:
        return "신입/경력"
    if "신입" in text:
        return "신입"
    if "경력" in text:
        return "경력"
    if "인턴" in text:
        return "인턴"
    return None


def parse_list(html: str, source_key: str, company: str, now_kst: datetime) -> list[Posting]:
    tree = HTMLParser(html)
    today = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    out: list[Posting] = []
    for item in tree.css("div.list_item"):
        a = item.css_first(".job_tit a.str_tit") or item.css_first("a[href*='rec_idx=']")
        m = REC_ID_RE.search((a.attributes.get("href") or "") if a else "")
        if not m:
            continue
        title = " ".join((a.attributes.get("title") or a.text()).split())
        support = item.css_first(".support_info")
        closed = bool(support and "접수마감" in support.text())
        date = item.css_first(".support_detail .date")
        ago = AGO_RE.search(item.css_first(".support_detail .deadlines").text() if item.css_first(".support_detail .deadlines") else "")
        career_node = item.css_first(".recruit_info .career")
        career_text = " ".join(career_node.text().split()) if career_node else ""
        parts = [x.strip() for x in career_text.split("·")]
        place = item.css_first(".recruit_info .work_place")
        sectors = [" ".join(s.text().split()) for s in item.css(".job_meta .job_sector span")]
        out.append(
            Posting(
                source=source_key,
                external_id=m.group(1),
                company=company,
                title=title,
                url=f"{BASE}/zf_user/jobs/relay/view?rec_idx={m.group(1)}",
                start_at=today - timedelta(days=int(ago.group(1))) if ago else None,
                end_at=_end_date(date.text() if date else "", today),
                end_date_only=True,
                career_type=_career(career_text),
                employment_type=parts[1] if len(parts) > 1 else None,
                status="접수마감" if closed else "접수중",
                job_text="\n".join(dict.fromkeys(s for s in sectors if s)),
                location_raw=" ".join(place.text().split()) if place else None,
            )
        )
    return out


class SaraminCompanySource(Source):
    portal = True
    portal_name = "사람인"
    llm_ok = False          # 포털에서 읽은 문장은 LLM 에 보내지 않는다
    min_interval_min = 180  # 보완용이라 자주 읽지 않는다

    def __init__(self, key: str, company: str, csn: str):
        self.key = key
        self.company = f"{company} (사람인)"
        self.posting_company = company
        self.csn = csn   # 사람인 기업 페이지 주소의 csn 값
        self.site_url = f"{BASE}/zf_user/company-info/view-inner-recruit?csn={csn}"

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        html = f.get(f"{BASE}/zf_user/company-info/view-inner-recruit", params={"csn": self.csn}).text
        if "진행중" not in html and "list_item" not in html:
            raise RuntimeError("사람인 기업 공고 페이지 구조가 바뀌었거나 차단됨")
        return parse_list(html, self.key, self.posting_company, datetime.now(KST).replace(tzinfo=None))
