"""수집 소스 레지스트리.

새 기업을 추가할 때는 먼저 robots.txt·이용약관·공고 제공 방식을 조사해 research/sources.md 에 기록한다.
관심 분야는 두 가지다(radar/categories.py): 카드사는 전체 공고, 그 밖의 대기업은 AI·데이터 직무 공고만 남긴다.
그룹 통합 사이트에서 어느 계열사까지 남길지는 radar/companies.py 에 있다.

추가 기준(2026-11-22 사용자 결정):
- 공고 목록 경로가 robots.txt 로 금지된 사이트는 추가하지 않는다.
- 이용약관이 개인적인 이용까지 금지하는 회사는 제외한다. 영리 이용·제3자 제공만 금지하는 약관은 괜찮다.
- 공고 페이지가 허용돼 있으면, 데이터가 다른(금지된) 경로에서 오더라도 페이지를 브라우저로 열어 화면을 읽는다.
"""
from __future__ import annotations

from .base import Source
from .careerlink import CareerlinkSource
from .cj import CJSource
from .doosan import DoosanSource
from .greeting import GreetingSource
from .hanwha import HanwhaSource
from .hd_hyundai import HDHyundaiSource
from .hmg import HyundaiMotorGroupSource
from .kakao import KakaoSource
from .kt import KTSource
from .lg_careers import LGCareersSource
from .lotte import LotteSource
from .naver import NaverSource
from .nonghyup import NonghyupCardSource
from .recruiter_co_kr import RecruiterCoKrSource
from .samsung_careers import SamsungCareersSource
from .shinhancard import ShinhanCardSource
from .shinsegae import ShinsegaeSource
from .sk_careers import SkCareersSource

SOURCES: list[Source] = [
    # --- 카드사 (전체 공고) ----------------------------------------------------
    # 현대카드와 현대커머셜이 한 사이트를 쓴다. 제목 머리말로 회사를 가려, 현대커머셜 단독 공고는 AI 직무일 때만 남긴다.
    RecruiterCoKrSource(
        key="hyundaicard", company="현대카드/현대커머셜", subdomain="careerhyundai",
        title_companies={"현대카드": "현대카드", "현대커머셜": "현대커머셜", "현대카드/커머셜": "현대카드/현대커머셜"},
    ),
    CareerlinkSource(key="kbcard", company="KB국민카드", site="https://kbcard.careerlink.kr", co_no="CO202407240379"),
    ShinhanCardSource(key="shinhancard"),
    # 우리카드 경력·계약직 수시채용. robots.txt 가 AI 학습 이용을 거절하는 사이트라 근무지 문장을 LLM 에 보내지 않는다
    GreetingSource(
        key="wooricard", company="우리카드", base="https://wooricard.career.greetinghr.com",
        list_path="/ko/open-positions", llm_ok=False,
    ),
    # 우리카드 신입 공채는 별도 사이트(careerlink)에 올라온다
    CareerlinkSource(key="wooricard_open", company="우리카드 (공채)", site="https://wooricard.careerlink.kr", co_no="CO202409050397"),
    NonghyupCardSource(key="nhcard"),
    # 삼성카드는 아래 삼성커리어스에, BC카드는 KT그룹 채용에 함께 올라온다.

    # --- 대기업 (AI·데이터 직무만) ----------------------------------------------
    SamsungCareersSource(key="samsung"),
    LGCareersSource(key="lg"),
    SkCareersSource(key="sk"),
    HyundaiMotorGroupSource(
        key="hyundai", company="현대자동차", base="https://talent.hyundai.com", hgr_cd="1", service="HM", view_ext="hc",
    ),
    HyundaiMotorGroupSource(
        key="kia", company="기아", base="https://career.kia.com", hgr_cd="2", service="KM", view_ext="kc",
    ),
    # robots.txt 가 AI 학습 이용을 거절하는 사이트라 근무지 문장을 LLM 에 보내지 않는다
    GreetingSource(key="autoever", company="현대오토에버", base="https://career.hyundai-autoever.com", llm_ok=False),
    CareerlinkSource(key="hyundaicapital", company="현대캐피탈", site="https://career.hyundaicapital.com", co_no="CO202602134662"),
    # 브라우저로 여는 jobflex 사이트. 급하지 않으므로 2시간에 한 번만 연다
    RecruiterCoKrSource(key="glovis", company="현대글로비스", subdomain="glovis", list_path="/career/apply", min_interval_min=120),
    NaverSource(key="naver"),
    KakaoSource(key="kakao"),
    KTSource(key="kt"),
    LotteSource(key="lotte"),
    HanwhaSource(key="hanwha"),
    CJSource(key="cj"),
    ShinsegaeSource(key="shinsegae"),
    HDHyundaiSource(key="hd"),
    DoosanSource(key="doosan"),
    CareerlinkSource(key="kbstar", company="KB국민은행", site="https://kbstar.careerlink.kr", co_no="CO202507252710"),
    RecruiterCoKrSource(key="shinhanbank", company="신한은행", subdomain="shinhan", list_path="/career/jobs", min_interval_min=120),
    RecruiterCoKrSource(
        key="shinhanbank_ict", company="신한은행", subdomain="shinhandigital", list_path="/career/jobs", min_interval_min=120,
    ),
]

# 수집기는 만들었지만 사용자 승인을 기다리는 소스. 기본 실행에는 들어가지 않고, --sources 로 이름을 주면 실행된다.
PENDING_SOURCES: list[Source] = []


def get_sources(keys: list[str] | None = None) -> list[Source]:
    """수집할 소스. 키를 주지 않으면 SOURCES 전부, 키를 주면 승인 대기 소스에서도 찾는다."""
    if not keys:
        return SOURCES
    wanted = set(keys)
    known = SOURCES + PENDING_SOURCES
    picked = [s for s in known if s.key in wanted]
    missing = wanted - {s.key for s in picked}
    if missing:
        raise SystemExit(f"알 수 없는 소스: {', '.join(sorted(missing))}. 사용 가능: {', '.join(s.key for s in known)}")
    return picked
