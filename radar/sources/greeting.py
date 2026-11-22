"""그리팅(Greeting, greetinghr) 채용 솔루션을 쓰는 기업용 수집기. 기업마다 자기 도메인으로 채용 사이트를 연다.

- 공고 목록 페이지(예: /ko/apply)의 HTML 안 `__NEXT_DATA__` 에 접수 중인 공고 전체가 들어 있다. 같은 호스트, 요청 한 번.
- 공고 링크: <base>/ko/o/<openingId>. 지원 페이지(/o/*/apply)와 로그인(/a/*)은 robots.txt 로 금지돼 있어 건드리지 않는다.
- 날짜는 UTC(ISO 8601)로 오므로 한국 시각으로 바꿔 저장한다. 상시 공고는 마감일이 없다.
- 근무지는 목록의 주소 문자열(workspacePlace.place, 예: '서울특별시 강남구 대치동')이라 상세를 보지 않는다.
- 사업부 이름(workspaceDivision)은 'Core Tech(AI/DATA/Cloud/보안)' 처럼 키워드를 품고 있어 분류에 쓰지 않는다.
  직군(workspaceOccupation, 예: 'Data/AI(인공지능)')만 직무 텍스트로 쓴다.

현대오토에버(career.hyundai-autoever.com) 메모 (2026-11-22):
- robots.txt 는 `*` 에 `Allow: /` 이고 Content-Signal 로 `ai-train=no` 를 밝히며, ClaudeBot·GPTBot 등 AI 학습 수집기를
  이름으로 금지한다. 이 수집기는 학습용이 아니라 공고 제목과 링크만 다루지만, 그 뜻을 존중해 이 사이트의 문장은
  LLM 에 보내지 않는다(llm_ok=False). 이용약관 페이지는 없다(개인정보 처리방침·이메일무단수집거부만 있음).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from ..fetch import Fetcher
from ..models import Posting
from .base import Source

KST = timezone(timedelta(hours=9))
CAREER = {"EXPERIENCED": "경력", "NEW_COMER": "신입", "NEWCOMER": "신입", "NOT_MATTER": "신입/경력", "INTERN": "인턴"}
EMPLOYMENT = {
    "FULL_TIME_WORKER": "정규", "CONTRACT_WORKER": "계약", "INTERN": "인턴", "PART_TIME_WORKER": "계약",
    "FREELANCER": "계약",
}


def _kst(iso_utc: str | None) -> datetime | None:
    if not iso_utc:
        return None
    try:
        return datetime.fromisoformat(iso_utc.replace("Z", "+00:00")).astimezone(KST).replace(tzinfo=None)
    except ValueError:
        return None


def openings_from_html(html: str) -> list[dict]:
    """페이지의 __NEXT_DATA__ 에서 공고 목록(queryKey == ['openings'])을 꺼낸다."""
    node = HTMLParser(html).css_first("script#__NEXT_DATA__")
    if node is None:
        raise RuntimeError("__NEXT_DATA__ 가 없음 (차단 페이지이거나 사이트 구조가 바뀜)")
    data = json.loads(node.text())
    queries = (((data.get("props") or {}).get("pageProps") or {}).get("dehydratedState") or {}).get("queries") or []
    for q in queries:
        if q.get("queryKey") == ["openings"]:
            return (q.get("state") or {}).get("data") or []
    raise RuntimeError("__NEXT_DATA__ 에 공고 목록(openings)이 없음")


def _uniq(values) -> list[str]:
    return list(dict.fromkeys(v.strip() for v in values if v and v.strip()))


def parse_openings(items: list[dict], source_key: str, company: str, base: str) -> list[Posting]:
    out: list[Posting] = []
    for it in items:
        oid = it.get("openingId")
        if oid is None:
            continue
        positions = ((it.get("openingJobPosition") or {}).get("openingJobPositions")) or []
        # 직군(occupation)과 직무(job). 기업마다 한쪽만 채우기도 한다(오토에버는 직군, 우리카드는 직무가 구체적)
        occupations = _uniq(
            [(p.get("workspaceOccupation") or {}).get("occupation") for p in positions]
            + [(p.get("workspaceJob") or {}).get("job") for p in positions]
        )
        places = _uniq((p.get("workspacePlace") or {}).get("place") for p in positions)
        careers = _uniq(CAREER.get((p.get("jobPositionCareer") or {}).get("careerType") or "") for p in positions)
        employs = _uniq(EMPLOYMENT.get((p.get("jobPositionEmployment") or {}).get("employmentType") or "") for p in positions)
        out.append(
            Posting(
                source=source_key,
                external_id=str(oid),
                company=company,
                title=(it.get("title") or "").strip(),
                url=f"{base}/ko/o/{oid}",
                start_at=_kst(it.get("openDate")),
                end_at=_kst(it.get("dueDate")),
                career_type="/".join(careers) or None,
                employment_type="/".join(employs) or None,
                status="접수중",   # 목록에는 접수 중인 공고만 올라온다
                job_text="\n".join(occupations),
                location_raw="\n".join(places) or None,
            )
        )
    return out


class GreetingSource(Source):
    def __init__(self, key: str, company: str, base: str, list_path: str = "/ko/apply", llm_ok: bool = True):
        self.key = key
        self.company = company
        self.base = base.rstrip("/")
        self.site_url = f"{self.base}{list_path}"
        self.llm_ok = llm_ok

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        html = f.get(self.site_url).text
        return parse_openings(openings_from_html(html), self.key, self.company, self.base)
