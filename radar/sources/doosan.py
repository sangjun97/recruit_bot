"""두산그룹 채용(career.doosan.com) 수집기.

- robots.txt 없음(404 오류 페이지). 이용약관 페이지도 없다(개인정보처리방침과 이메일주소 무단수집거부만 있음).
  이메일 수집 거부 고지가 있으므로 연락처는 읽지 않는다. 목록만 읽고 상세는 열지 않는다.
- 목록: GET /dsp/sa/RecList.jsp (서버 렌더링 HTML 한 장, 접수 중인 공고 전부).
- 공고마다 고유 주소가 없다. 상세는 목록 페이지에서 양식을 보내 여는 구조라, 링크는 목록 페이지로 건다.
- 목록에는 회사·구분·제목·기간(날짜만)이 있고 직무 분류와 근무지는 없다. AI·데이터 판별은 제목으로 한다.
"""
from __future__ import annotations

import re
from datetime import datetime

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from ..companies import DOOSAN_MAJOR
from ..fetch import Fetcher
from ..models import Posting
from .base import Source

BASE = "https://career.doosan.com"
LIST_URL = f"{BASE}/dsp/sa/RecList.jsp"
GO_DETAIL_RE = re.compile(r"goDetail\('(\d+)'")
PERIOD_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})?")
CAREER = {"신입/인턴십": "신입/인턴", "경력": "경력"}


def _date(s: str | None) -> datetime | None:
    try:
        return datetime.strptime(s or "", "%Y-%m-%d")
    except ValueError:
        return None


def parse_list(html: str, source_key: str) -> list[Posting]:
    tree = HTMLParser(html)
    if tree.css_first("ul.list-cont") is None:
        raise RuntimeError("두산 채용 목록 영역이 없음 (차단 페이지이거나 사이트 구조가 바뀜)")
    out: list[Posting] = []
    for li in tree.css("ul.list-cont > li"):
        a = li.css_first("a.list-tit")
        m = GO_DETAIL_RE.search((a.attributes.get("onclick") or "") if a else "")
        title = li.css_first("strong")
        if not m or title is None:
            continue
        badge = li.css_first("div.company span.badge-type")
        kind = " ".join(badge.text().split()) if badge else ""
        company_node = li.css_first("div.company")
        company = " ".join(company_node.text(deep=False).split()) if company_node else "두산"
        deadline = li.css_first("div.deadline")
        pm = PERIOD_RE.search(deadline.text() if deadline else "")
        end = _date(pm.group(2)) if pm else None
        out.append(
            Posting(
                source=source_key,
                external_id=m.group(1),
                company=company or "두산",
                title=" ".join(title.text().split()),
                url=LIST_URL,   # 공고별 주소가 없어 목록으로 보낸다
                start_at=_date(pm.group(1)) if pm else None,
                end_at=end.replace(hour=23, minute=59) if end else None,
                end_date_only=True,
                career_type=CAREER.get(kind),
                employment_type=kind if kind not in CAREER else None,   # '전문/생산/계약직'
                status="접수중",   # 목록에는 접수 중인 공고만 올라온다
            )
        )
    return out


class DoosanSource(Source):
    site_url = LIST_URL

    def __init__(self, key: str = "doosan", companies: set[str] | None = DOOSAN_MAJOR):
        self.key = key
        self.company = "두산 (두산그룹 채용)"
        self.companies = companies

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        return self.scope(parse_list(f.get(LIST_URL).text, self.key), self.companies)
