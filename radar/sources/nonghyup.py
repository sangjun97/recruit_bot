"""NH농협카드 수집기. NH농협카드는 별도 회사가 아니라 NH농협은행의 카드 부문(NH카드분사)이라
범농협 채용시스템(with.nonghyup.com)에서 농협은행 공고 가운데 카드 부문 것만 골라 읽는다.

- robots.txt 없음(오류 페이지로 넘어간다).
- 이용약관: 자동 수집 조항은 없다. 제12조 "이용자는 개인적인 용도가 아닌 어떠한 경우에도 이 사이트 서비스를 사용할 수 없습니다",
  제10조 "서비스에서 얻은 정보를 … 이용자의 이용이외의 목적으로 복제하거나 … 제 3자에게 제공하는 행위" 금지.
  개인적인 이용은 허용하므로 2026-11-22 사용자 결정(개인 이용까지 막는 약관만 제외)에 따라 추가했다.
- 목록: 먼저 /main.do 를 열어 세션 쿠키를 받은 뒤 POST /jbnf/jbnfLst.do (서버 렌더링 HTML).
  법인=NH농협은행(srcAuthDsc=1), 제목 검색어 '카드'로 좁혀 한 쪽(10건)만 읽는다. 사이트 전체는 1,600건이 넘으므로 항상 좁혀서 읽는다.
- 마감된 공고도 목록에 남는다. 접수 기간으로 가린다. 목록에는 날짜만 있다.
- 상세: GET /jbnf/jbnfDtl.do?jbnfSqno=<id>. 근무지는 본문의 '근 무 지 : …' 줄(글자 사이에 공백이 있다).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from ..fetch import Fetcher
from ..location import pick_location_lines
from ..models import Posting
from .base import Source

BASE = "https://with.nonghyup.com"
KST = timezone(timedelta(hours=9))
ID_RE = re.compile(r"fn_jbnfDtl\('(\d+)'\)")
SPACED_LOCATION_RE = re.compile(r"근\s*무\s*(지|장\s*소|지\s*역)")


def _date(s: str) -> datetime | None:
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d")
    except ValueError:
        return None


def is_card_row(title: str, region: str, office: str) -> bool:
    return "카드" in office or "카드분사" in title or "카드분사" in region


def parse_list(html: str, source_key: str, now_kst: datetime) -> list[Posting]:
    out: list[Posting] = []
    for tr in HTMLParser(html).css("table.table tbody tr"):
        td = tr.css("td")
        if len(td) < 6:
            continue
        a = td[1].css_first("a")
        m = ID_RE.search((a.attributes.get("onclick") or "") if a else "")
        if not m:
            continue
        title = " ".join(a.text().split())
        region, office = td[3].text(strip=True), td[4].text(strip=True)
        if not is_card_row(title, region, office):
            continue
        left, _, right = td[5].text(strip=True).partition("~")
        start, end = _date(left), _date(right)
        end = end.replace(hour=23, minute=59) if end else None
        out.append(
            Posting(
                source=source_key,
                external_id=m.group(1),
                company="NH농협카드",
                title=title,
                url=f"{BASE}/jbnf/jbnfDtl.do?jbnfSqno={m.group(1)}",
                start_at=start,
                end_at=end,
                end_date_only=True,
                employment_type=td[0].text(strip=True) or None,   # 일반계약직, 전문직 등
                status="접수마감" if end and end < now_kst else "접수중",
                location_raw=" ".join(x for x in (region, office) if x) or None,
            )
        )
    return out


def location_text_from_detail(html: str) -> str | None:
    """상세 본문에서 근무지 줄만 고른다. '근 무 지' 처럼 띄어 쓴 표기를 붙여서 찾는다."""
    body = HTMLParser(html).body
    text = body.text(separator="\n") if body else ""
    text = SPACED_LOCATION_RE.sub(lambda m: "근무" + m.group(1).replace(" ", ""), text)
    return pick_location_lines(text, max_lines=3)


class NonghyupCardSource(Source):
    site_url = f"{BASE}/jbnf/jbnfLst.do"

    def __init__(self, key: str = "nhcard"):
        self.key = key
        self.company = "NH농협카드 (범농협 채용)"

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        f.get(f"{BASE}/main.do")   # 세션 쿠키를 받는다. 쿠키 없이 목록을 요청하면 응답이 끝나지 않는다
        form = {"srcAuthDsc": "1", "pageIndex": "1", "srcJbnfTinm": "카드"}
        html = f.post(f"{BASE}/jbnf/jbnfLst.do", data=form).text
        if "table" not in html:
            raise RuntimeError("범농협 채용 목록 표가 없음")
        return parse_list(html, self.key, datetime.now(KST).replace(tzinfo=None))

    def fetch_detail(self, f: Fetcher, posting: Posting) -> str | None:
        detail = location_text_from_detail(f.get(posting.url).text)
        return detail or posting.location_raw
