"""careerlink(인에이치알, inHR) 채용 솔루션을 쓰는 기업용 수집기. KB국민카드·KB국민은행 등이 쓴다.

- 기업마다 <이름>.careerlink.kr (또는 자체 도메인)에 채용 사이트를 연다. robots.txt 는 /jobs 와 /jobs/<공고번호> 를 허용하고
  /admin, /my-page, /policy, /login 등만 금지한다. 등록되지 않은 하위 도메인은 `Disallow: /` 로 답하므로
  기업을 추가할 때마다 그 도메인의 robots.txt 를 확인할 것.
- 공고 데이터는 api.inhr.co.kr 에서 온다. 이 호스트에는 robots.txt 가 없다(404).
- 이용약관 페이지는 없다. 사이트 아래쪽에는 개인정보처리방침(/policy, robots 금지 경로라 열지 않음)만 있다.
- 목록을 받으려면 사이트가 방문자마다 하는 것처럼 대기열 입장표를 먼저 받는다(POST /v1/vwr/enter → ticket).
  인증이 아니라 혼잡 제어다. 대기 상태로 답하면 이번 실행은 건너뛰고 다음에 다시 시도한다.
- 목록: POST /v1/recruit/jd/list {"coNo": 기업번호}. 한 번에 전체. 오류도 HTTP 200 으로 오므로 code 를 본다.
  접수가 끝난 공고도 게시 기간 동안 목록에 남는다(rcrtStatGbcd 03).
- 직무 분류(rcrtJobInfList[].jobNmPath, 예: 'AI/데이터 > LLMOps 기획 및 개발')와 근무지(etcInf1, 예: '서울 종로구 근무')가
  목록에 있어 상세를 보지 않는다. 공고 본문(rcrtCntn)은 읽지도 저장하지도 않는다.
- 공고 링크: <사이트>/jobs/<rcrtNo>
"""
from __future__ import annotations

from datetime import datetime

from ..fetch import Fetcher
from ..models import Posting
from .base import Source

API = "https://api.inhr.co.kr"
STATUS = {"01": "접수예정", "02": "접수중", "03": "접수마감"}


def _dt(s: str | None) -> datetime | None:
    try:
        return datetime.strptime((s or "").strip()[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def parse_list(data: dict, source_key: str, company: str, site: str) -> list[Posting]:
    out: list[Posting] = []
    for it in (data.get("data") or {}).get("rcrtList") or []:
        no = (it.get("rcrtNo") or "").strip()
        if not no:
            continue
        jobs = [(j.get("jobNmPath") or j.get("jobNm") or "").strip() for j in it.get("rcrtJobInfList") or []]
        status = STATUS.get(it.get("rcrtStatGbcd") or "")
        if status is None:
            status = "접수중" if it.get("apltPossYn") == "Y" else "접수마감"
        out.append(
            Posting(
                source=source_key,
                external_id=no,
                company=(it.get("coNm") or company).strip(),
                title=" ".join((it.get("rcrtNm") or "").split()),
                url=f"{site}/jobs/{no}",
                start_at=_dt(it.get("rcrtAcptStrtDtm")),
                end_at=_dt(it.get("rcrtAcptEndDtm")),
                career_type=(it.get("carrTypeGbcdNm") or "").strip() or None,
                employment_type=(it.get("hireTypeGbcdNm") or "").strip() or None,
                status=status,
                job_text="\n".join(dict.fromkeys(j for j in jobs if j)),
                location_raw=(it.get("etcInf1") or "").strip() or None,
            )
        )
    return out


class CareerlinkSource(Source):
    def __init__(self, key: str, company: str, site: str, co_no: str):
        self.key = key
        self.company = company
        self.site = site.rstrip("/")      # 예: https://kbcard.careerlink.kr
        self.co_no = co_no                # 기업번호. 사이트 __NEXT_DATA__ 의 coInf.coNo
        self.site_url = f"{self.site}/jobs"

    def fetch_list(self, f: Fetcher) -> list[Posting]:
        headers = {"Origin": self.site, "Referer": f"{self.site}/", "x-vwr-target": self.co_no}
        enter = f.post(f"{API}/v1/vwr/enter", headers={**headers, "Content-Type": "application/x-www-form-urlencoded"}).json()
        ticket = (enter.get("data") or {}).get("ticket")
        if enter.get("code") != "0000" or (enter.get("data") or {}).get("status") != "enter" or not ticket:
            raise RuntimeError(f"careerlink 대기열: {enter.get('message')} / {(enter.get('data') or {}).get('status')}")
        data = f.post(f"{API}/v1/recruit/jd/list", json={"coNo": self.co_no}, headers={**headers, "x-vwr-ticket": ticket}).json()
        if data.get("code") != "0000":
            raise RuntimeError(f"careerlink 목록 오류: {data.get('code')} {data.get('message')}")
        return parse_list(data, self.key, self.company, self.site)
