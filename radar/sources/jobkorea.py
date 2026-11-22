"""잡코리아(jobkorea.co.kr) 검색 결과에서 특정 회사가 직접 올린 공고만 골라 읽는 수집기. 보완용이다.

- 2026-11-22 사용자 결정: 공식 사이트에서 모으기 어려운 회사는 채용 포털을 거쳐서라도 모은다.
- robots.txt: `*` 에 대해 /corp/, /login/, /user/ 등만 금지한다. 검색(/Search/)과 공고(/Recruit/GI_Read/)는 금지 목록에 없다.
  기업 페이지(/corp/)는 금지라 열지 않는다. 그래서 회사 이름으로 검색한 첫 쪽을 읽고, 올린 회사 이름이 정확히 맞는 공고만 남긴다.
- 이용약관(운영사 웍스피어의 개인회원 약관)은 회원 대상이다. 자동 수집 조항은 없고 "회원은 서비스를 이용하여 얻은 정보를 회사의
  사전동의 없이 복사, 복제 … 하거나 이를 타인에게 제공할 수 없다", "사이트의 정보 및 서비스를 이용한 영리 행위" 금지가 있다.
- 알아 둘 것: 잡코리아는 경쟁사(사람인)가 채용 정보를 대량으로 긁어 영업에 쓴 일로 소송을 내 이긴 적이 있다. 이 수집기는 회사 한 곳의
  검색 결과 한 쪽을 3시간에 한 번 읽어 제목과 링크만 남기는 개인 용도지만, 문제가 되면 SOURCES 에서 빼면 된다.
- 검색 결과에는 '하나카드 상담사' 같은 파견·대행 업체 공고가 대부분이다. 회사 이름이 정확히 맞는 공고만 남긴다.
- 목록에는 마감일이 없다. 목록에서 사라지면 마감으로 본다. 첫 쪽만 읽으므로 공고가 뒤로 밀리면 마감으로 잘못 볼 수 있다.
- 화면 구조(클래스 이름)가 자주 바뀌는 사이트다. 공고 링크는 있는데 회사 이름을 하나도 못 읽으면 오류로 드러낸다.
"""
from __future__ import annotations

import re

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from ..fetch import Fetcher
from ..models import Posting
from .base import Source

BASE = "https://www.jobkorea.co.kr"
GI_RE = re.compile(r"/Recruit/GI_Read/(\d+)")
CORP_MARK_RE = re.compile(r"\(주\)|㈜|주식회사|\s+")
CAREER_RE = re.compile(r"^(신입·경력|신입/경력|신입|경력무관|경력)")


def norm_company(name: str) -> str:
    return CORP_MARK_RE.sub("", name or "").casefold()


def parse_search(html: str, source_key: str, company: str, corp_names: set[str]) -> tuple[list[Posting], int]:
    """검색 결과에서 corp_names 의 회사가 올린 공고만 Posting 으로 바꾼다. (공고들, 화면에 있던 공고 수)를 돌려준다."""
    tree = HTMLParser(html)
    wanted = {norm_company(n) for n in corp_names}
    # 공고 하나에 같은 주소의 링크가 여럿 달린다: 로고(글자 없음), 제목, 회사 이름 순
    texts: dict[str, list[str]] = {}
    cards: dict[str, object] = {}
    for a in tree.css("a[href*='/Recruit/GI_Read/']"):
        m = GI_RE.search(a.attributes.get("href") or "")
        if not m:
            continue
        gid = m.group(1)
        text = " ".join(a.text().split())
        texts.setdefault(gid, [])
        if text and text not in texts[gid]:
            texts[gid].append(text)
        if (a.attributes.get("data-sentry-component") == "Title" or gid not in cards) and a.parent is not None:
            cards[gid] = a
    out: list[Posting] = []
    named = 0
    for gid, parts in texts.items():
        if len(parts) < 2:
            continue
        named += 1
        title, corp = parts[0], parts[1]
        if norm_company(corp) not in wanted:
            continue
        # 카드 전체 글자에서 근무지·직무·경력을 고른다(회사 이름 다음 칸부터)
        node = cards[gid]
        card_text: list[str] = []
        for _ in range(6):
            node = node.parent
            if node is None:
                break
            tokens = [" ".join(t.split()) for t in node.text(separator="|").split("|")]
            tokens = [t for t in tokens if t]
            if corp in tokens and len(tokens) >= 4:
                card_text = tokens[tokens.index(corp) + 1:]
                break
        career = next((CAREER_RE.match(t).group(1) for t in card_text if CAREER_RE.match(t)), None)
        location = card_text[0] if card_text else None
        sector = card_text[1] if len(card_text) > 1 and not CAREER_RE.match(card_text[1]) and "지원" not in card_text[1] else ""
        out.append(
            Posting(
                source=source_key,
                external_id=gid,
                company=company,
                title=title,
                url=f"{BASE}/Recruit/GI_Read/{gid}",
                career_type={"경력무관": "신입/경력", "신입·경력": "신입/경력"}.get(career or "", career),
                status="접수중",   # 검색 결과에는 진행 중인 공고만 나온다
                job_text=sector,
                location_raw=location,
            )
        )
    return out, named


class JobKoreaSearchSource(Source):
    portal = True
    portal_name = "잡코리아"
    llm_ok = False
    min_interval_min = 180

    def __init__(self, key: str, company: str, keyword: str, corp_names: set[str]):
        self.key = key
        self.company = f"{company} (잡코리아)"
        self.posting_company = company
        self.keyword = keyword
        self.corp_names = corp_names   # 잡코리아에 표시되는 회사 이름. '(주)'·'㈜' 표기와 공백은 무시하고 맞춘다
        self.site_url = f"{BASE}/Search/?stext={keyword}&tabType=recruit"

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        html = f.get(f"{BASE}/Search/", params={"stext": self.keyword, "tabType": "recruit"}).text
        postings, named = parse_search(html, self.key, self.posting_company, self.corp_names)
        if named == 0 and "/Recruit/GI_Read/" in html:
            raise RuntimeError("잡코리아 검색 결과에서 회사 이름을 읽지 못함 (화면 구조가 바뀜)")
        if "/Recruit/GI_Read/" not in html and "검색결과" not in html:
            raise RuntimeError("잡코리아 검색 결과 페이지가 아님 (차단됐거나 구조가 바뀜)")
        return postings
