from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter

from ..categories import is_card_company
from ..companies import in_group
from ..fetch import Fetcher
from ..models import Posting


class Source(ABC):
    key: str             # 소스 식별자. Posting.source 로 저장된다.
    company: str         # 수집 현황에 표시할 이름 (회사 또는 그룹)
    site_url: str = ""   # 사람이 여는 채용 사이트 주소

    # 목록만으로는 직무를 알 수 없어(여러 직무를 묶은 공고) 상세를 봐야 AI 직무인지 판별할 수 있는 소스.
    # True 면 관심 분야가 아닌 공고도 저장해 두어 같은 상세를 매번 다시 조회하지 않게 한다.
    detail_for_classify: bool = False

    # 이 간격(분)보다 자주 수집하지 않는다. 응답이 크거나 브라우저를 띄워야 해서 사이트에 부담이 되는 소스에 쓴다.
    min_interval_min: int = 0

    # 채용 포털(사람인·잡코리아)을 거쳐 읽는 보완용 소스인지. 같은 공고가 공식 사이트나 다른 포털에도 있으면 포털 쪽을 숨긴다.
    portal: bool = False
    portal_name: str = ""   # 카드에 '○○ 경유'로 표시할 포털 이름

    # 근무지 문장을 LLM 에 보내도 되는지. robots.txt 가 AI 입력을 꺼리는 사이트는 False 로 두고 규칙으로만 추출한다.
    llm_ok: bool = True

    @abstractmethod
    def fetch_list(self, f: Fetcher) -> list[Posting]:
        """현재 게시된 공고를 모두 돌려준다. 제목·기간·전형 구분 등 목록에서 알 수 있는 것만 채운다."""

    def fetch_detail(self, f: Fetcher, posting: Posting) -> str | None:
        """공고 상세에서 근무지 판단에 필요한 텍스트 조각만 돌려준다. 본문 전체를 저장하지 않는다.

        상세에서만 알 수 있는 값(정확한 접수 기간, 모집 직무명 job_text)은 posting 에 직접 채운다.
        새로 저장할 공고에 대해서만 호출된다.
        """
        return posting.location_raw

    # --- 계열사 범위 ------------------------------------------------------------
    def scope(self, postings: list[Posting], majors: set[str] | None) -> list[Posting]:
        """그룹 통합 사이트에서 주력 계열사(majors)와 카드사 공고만 남긴다. majors 가 None 이면 전부 남긴다.

        빠진 회사명은 skipped_companies 에 모아 실행 로그에 찍는다(목록에 넣어야 할 회사가 빠졌는지 확인용).
        """
        self.skipped_companies: Counter = Counter()
        if majors is None:
            return postings
        kept = []
        for p in postings:
            if in_group(p.company, majors) or is_card_company(p.company):
                kept.append(p)
            else:
                self.skipped_companies[p.company] += 1
        return kept
