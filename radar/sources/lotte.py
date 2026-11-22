"""롯데그룹 채용(recruit.lotte.co.kr) 수집기.

- robots.txt 없음(307 → /error.html, 없는 경로와 같은 응답). 이용약관은 회원 가입 계약이고 수집·복제·재배포 조항이 없다.
  '이메일 무단수집거부' 고지가 있으므로 공고 본문의 연락처는 읽지도 저장하지도 않는다.
- 목록: GET /apply/announcement (서버 렌더링 HTML 한 장, 접수 중인 공고 전부).
- 직무 분류가 카드에 없다. 대신 같은 주소에 jobcd 를 붙이면 그 직무의 공고만 온다(0101 = AI, 0102 = 데이터분석).
  그래서 전체 목록과 AI·데이터 목록을 한 번씩 받아, 뒤쪽에 나온 공고에 직무 표시를 붙인다.
- 상세: GET /apply/announcement/detail/<id>. 근무지는 본문 표의 '근무지' 칸에 자유 서술로 있다.
- Imperva(Incapsula)가 앞에 있다. 차단되면 목록 대신 짧은 확인 페이지가 오므로 '공고 0건'과 구분해 오류로 처리한다.
"""
from __future__ import annotations

from datetime import datetime

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from ..companies import LOTTE_MAJOR
from ..fetch import Fetcher
from ..location import pick_location_lines
from ..models import Posting
from .base import Source

BASE = "https://recruit.lotte.co.kr"
LIST_URL = f"{BASE}/apply/announcement"
AI_JOB_CODES = ["0101", "0102"]                 # AI, 데이터분석
AI_JOB_LABEL = "AI·데이터분석 (롯데 직무 분류)"


class BlockedError(RuntimeError):
    pass


def _date(s: str) -> datetime | None:
    try:
        return datetime.strptime(s.strip(), "%Y.%m.%d")
    except ValueError:
        return None


def parse_list(html: str, source_key: str) -> list[Posting]:
    tree = HTMLParser(html)
    if tree.css_first("ul.job-card-list") is None:
        raise BlockedError("롯데 채용 목록 영역이 없음 (차단 확인 페이지이거나 사이트 구조가 바뀜)")
    out: list[Posting] = []
    for li in tree.css("ul.job-card-list > li"):
        a = li.css_first(".card-tit a")
        if a is None:
            continue   # '채용중인 공고가 없습니다.' 안내 줄
        pid = (a.attributes.get("href") or "").rstrip("/").rsplit("/", 1)[-1]
        if not pid.isdigit():
            continue
        company = li.css_first(".cmp-name")
        badge = li.css_first(".bage-group")
        date = li.css_first(".card-foot .date")
        start = end = None
        if date is not None and "~" in date.text():
            left, right = date.text().split("~", 1)
            start, end = _date(left), _date(right)
        out.append(
            Posting(
                source=source_key,
                external_id=pid,
                company=company.text(strip=True) if company else "롯데",
                title=a.text(strip=True),
                url=f"{LIST_URL}/detail/{pid}",
                start_at=start,
                end_at=end.replace(hour=23, minute=59) if end else None,
                end_date_only=True,   # 목록에는 날짜만 있다
                career_type=badge.text(strip=True) if badge else None,
                status="접수중",       # 목록에는 접수 중인 공고만 올라온다
            )
        )
    return out


def location_text_from_detail(html: str) -> str | None:
    """상세 본문에서 근무지 칸만 읽는다. 표의 '근무지' 머리 칸 아래 칸들을 모으고, 못 찾으면 근무지가 든 줄만 고른다."""
    tree = HTMLParser(html)
    found: list[str] = []
    for table in tree.css("table"):
        rows = [row.css("th, td") for row in table.css("tr")]
        for r, cells in enumerate(rows):
            for c, cell in enumerate(cells):
                if cell.text(strip=True).replace(" ", "") != "근무지":
                    continue
                for below in rows[r + 1:]:
                    if c < len(below):
                        value = " ".join(below[c].text(separator=" ", strip=True).split())
                        if value:
                            found.append(value)
    if found:
        return "\n".join(dict.fromkeys(found))[:400]
    body = tree.css_first(".board-body, .board-view, .view-cont") or tree.body
    return pick_location_lines(body.text(separator="\n") if body else "", max_lines=4)


class LotteSource(Source):
    site_url = LIST_URL

    def __init__(self, key: str = "lotte", companies: set[str] | None = LOTTE_MAJOR):
        self.key = key
        self.company = "롯데 (롯데그룹 채용)"
        self.companies = companies

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        postings = parse_list(f.get(LIST_URL).text, self.key)
        if postings:
            ai = parse_list(f.get(LIST_URL, params=[("jobcd", c) for c in AI_JOB_CODES]).text, self.key)
            ai_ids = {p.external_id for p in ai}
            for p in postings:
                p.job_text = AI_JOB_LABEL if p.external_id in ai_ids else ""
        return self.scope(postings, self.companies)

    def fetch_detail(self, f: Fetcher, posting: Posting) -> str | None:
        return location_text_from_detail(f.get(posting.url).text)
