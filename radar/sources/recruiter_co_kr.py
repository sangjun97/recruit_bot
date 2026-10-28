"""recruiter.co.kr(리크루터) 채용 솔루션을 쓰는 기업용 수집기.

현대카드(careerhyundai) 등 여러 기업이 같은 솔루션을 쓴다.
공고 목록 페이지(/career/recruit)를 브라우저로 열고, 페이지가 스스로 불러오는 목록 JSON 응답을 가로채서 읽는다.
현대카드 기준 robots.txt 는 /career/* 를 허용하고 첨부파일·게시판만 금지한다. 기업별로 다시 확인할 것.
"""
from __future__ import annotations

import time
from datetime import datetime

from playwright.sync_api import BrowserContext, Response

from ..location import pick_location_lines
from ..models import Posting
from .base import Source

LIST_API_MARK = "/position/v1/jobflex"

CAREER_TYPE = {"CAREER": "경력", "NEW": "신입", "INTERN": "인턴", "ALL": "신입/경력"}
STATUS = {"IN_SUBMISSION": "접수중", "POST_SUBMISSION": "접수마감", "PRE_SUBMISSION": "접수예정"}


def parse_items(items: list[dict], subdomain: str, source_key: str, company: str) -> list[Posting]:
    out: list[Posting] = []
    for it in items:
        sn = it.get("positionSn")
        if sn is None:
            continue
        tags = [t.get("tagName") for t in it.get("tagList", []) if t.get("tagName")]
        career = CAREER_TYPE.get(it.get("careerType") or "") or (tags[0] if tags else None)
        out.append(
            Posting(
                source=source_key,
                external_id=str(sn),
                company=company,
                title=(it.get("title") or "").strip(),
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
    def __init__(self, key: str, company: str, subdomain: str, delay_sec: float = 1.5):
        self.key = key
        self.company = company
        self.subdomain = subdomain
        self.delay_sec = delay_sec
        self.base = f"https://{subdomain}.recruiter.co.kr"

    def fetch_list(self, ctx: BrowserContext) -> list[Posting]:
        captured: dict[int, dict] = {}
        total_pages = {"n": 1}

        def on_response(resp: Response) -> None:
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

        page = ctx.new_page()
        page.on("response", on_response)
        try:
            page.goto(f"{self.base}/career/recruit", wait_until="networkidle", timeout=60_000)
            page.wait_for_timeout(1500)
            # 페이지네이션: 숫자 버튼을 순서대로 눌러 나머지 페이지 JSON도 받는다
            for n in range(2, total_pages["n"] + 1):
                btn = page.get_by_role("button", name=str(n), exact=True)
                if btn.count() == 0:
                    btn = page.get_by_text(str(n), exact=True)
                if btn.count() == 0:
                    break
                time.sleep(self.delay_sec)
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
        return parse_items(list(captured.values()), self.subdomain, self.key, self.company)

    def fetch_location_text(self, ctx: BrowserContext, posting: Posting) -> str | None:
        page = ctx.new_page()
        try:
            time.sleep(self.delay_sec)
            page.goto(posting.url, wait_until="networkidle", timeout=60_000)
            page.wait_for_timeout(800)
            text = page.locator("main, body").first.inner_text()
        finally:
            page.close()
        return pick_location_lines(text)
