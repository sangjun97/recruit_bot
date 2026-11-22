"""recruiter.co.kr(리크루터, jobflex) 채용 솔루션을 쓰는 기업용 수집기.

현대카드(careerhyundai) 등 여러 기업이 같은 솔루션을 쓴다. 기업마다 <subdomain>.recruiter.co.kr 를 쓴다.

robots.txt 주의 (2026-11-22 확인):
- <subdomain>.recruiter.co.kr/robots.txt 는 채용 페이지(/career/*)를 허용하고 첨부파일·게시판만 금지한다(기업별로 다시 확인할 것).
- 목록 데이터를 내려주는 api-recruiter.recruiter.co.kr/robots.txt 는 'User-agent: * / Disallow: /' 로 전체 금지다.
그래서 API 호스트를 직접 호출하지 않는다. 허용된 공고 목록 페이지(/career/recruit)를 브라우저로 열고,
페이지가 화면을 그리려고 스스로 받은 목록 응답을 읽는다. 상세도 공고 페이지를 열어 화면의 글자만 읽는다.
사람이 브라우저로 공고 페이지를 보는 것과 같은 요청만 나간다. 2026-11-22 에 사용자가 이 방식을 승인했다
("공고 페이지에서 가져올 수 있는 사이트면 그렇게 진행").
"""
from __future__ import annotations

import re
from datetime import datetime

from ..fetch import Fetcher
from ..location import pick_location_lines
from ..models import Posting
from .base import Source

LIST_API_MARK = "/position/v1/jobflex"

CAREER_TYPE = {
    "CAREER": "경력", "NEW": "신입", "INTERN": "인턴", "ALL": "신입/경력", "NEW_CAREER": "신입/경력",
    "ANY": "경력 무관", "FIELD_DIFFERENCE": "분야별 상이",
}
STATUS = {"IN_SUBMISSION": "접수중", "POST_SUBMISSION": "접수마감", "PRE_SUBMISSION": "접수예정"}
TITLE_TAG_RE = re.compile(r"^\s*\[([^\]]+)\]")


def parse_items(
    items: list[dict], subdomain: str, source_key: str, company: str, title_companies: dict[str, str] | None = None
) -> list[Posting]:
    """목록 JSON 항목을 Posting 으로 바꾼다.

    title_companies: 한 사이트에 여러 회사 공고가 섞여 있을 때 제목 머리말('[현대카드] ...')로 회사를 가린다.
    """
    out: list[Posting] = []
    for it in items:
        sn = it.get("positionSn")
        if sn is None:
            continue
        title = (it.get("title") or "").strip()
        tags = [t.get("tagName") for t in it.get("tagList", []) if t.get("tagName")]
        career = CAREER_TYPE.get(it.get("careerType") or "") or (tags[0] if tags else None)
        comp = company
        m = TITLE_TAG_RE.match(title)
        if title_companies and m:
            comp = title_companies.get(m.group(1).strip(), company)
        out.append(
            Posting(
                source=source_key,
                external_id=str(sn),
                company=comp,
                title=title,
                url=f"https://{subdomain}.recruiter.co.kr/career/jobs/{sn}",
                start_at=_dt(it.get("startDateTime")),
                end_at=_dt(it.get("endDateTime")),
                career_type=career,
                employment_type=it.get("classificationCode") or None,
                status=STATUS.get(it.get("submissionStatus") or "", it.get("submissionStatus")),
            )
        )
    return out


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


class RecruiterCoKrSource(Source):
    def __init__(
        self, key: str, company: str, subdomain: str, title_companies: dict[str, str] | None = None,
        list_path: str = "/career/recruit", min_interval_min: int = 0,
    ):
        self.key = key
        self.min_interval_min = min_interval_min   # 브라우저로 여는 소스라, 급하지 않은 곳은 간격을 둔다
        self.company = company
        self.subdomain = subdomain
        self.title_companies = title_companies
        self.base = f"https://{subdomain}.recruiter.co.kr"
        # 공고 목록 페이지 경로는 기업마다 다르다(/career/recruit, /career/jobs, /career/apply). 틀리면 404 가 온다
        self.site_url = f"{self.base}{list_path}"

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        captured: dict[int, dict] = {}
        total_pages = {"n": 1}

        def on_response(resp) -> None:
            if LIST_API_MARK not in resp.url or resp.request.method != "POST":
                return
            try:
                body = resp.json()
            except Exception:
                return
            pages = int((body.get("pagination") or {}).get("totalPages") or 1)
            total_pages["n"] = max(total_pages["n"], pages)
            for it in body.get("list", []):
                if it.get("positionSn") is not None:
                    captured[int(it["positionSn"])] = it

        page = f.browser.new_page()
        page.on("response", on_response)
        try:
            f.wait(self.site_url)
            resp = page.goto(self.site_url, wait_until="networkidle", timeout=60_000)
            if resp is not None and resp.status >= 400:
                raise RuntimeError(f"공고 목록 페이지 HTTP {resp.status}: {self.site_url}")
            page.wait_for_timeout(1500)
            # 페이지네이션: 숫자 버튼을 순서대로 눌러 나머지 페이지 JSON도 받는다
            for n in range(2, total_pages["n"] + 1):
                btn = page.locator(f"nav li[role='button'][aria-label='{n}페이지']")
                if btn.count() == 0:
                    btn = page.get_by_role("button", name=str(n), exact=True)
                if btn.count() == 0:
                    btn = page.get_by_text(str(n), exact=True)
                if btn.count() == 0:
                    break
                f.wait(self.site_url)
                btn.first.click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(1000)
            if not captured:
                # JSON을 못 받았으면 DOM의 링크로 최소 정보만 수집한다
                anchors = page.eval_on_selector_all(
                    "a[href^='/career/jobs/']",
                    "els => els.map(e => [e.getAttribute('href'), e.innerText.split('\\n')[0].trim()])",
                )
                for href, title in anchors:
                    sn = href.rsplit("/", 1)[-1]
                    if sn.isdigit():
                        captured[int(sn)] = {"positionSn": int(sn), "title": title}
        finally:
            page.close()
        return parse_items(list(captured.values()), self.subdomain, self.key, self.company, self.title_companies)

    def fetch_detail(self, f: Fetcher, posting: Posting) -> str | None:
        page = f.browser.new_page()
        try:
            f.wait(posting.url)
            page.goto(posting.url, wait_until="networkidle", timeout=60_000)
            page.wait_for_timeout(800)
            text = page.locator("main, body").first.inner_text()
        finally:
            page.close()
        return pick_location_lines(text)
