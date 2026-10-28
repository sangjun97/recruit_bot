from __future__ import annotations

from abc import ABC, abstractmethod

from playwright.sync_api import BrowserContext

from ..models import Posting


class Source(ABC):
    key: str          # 소스 식별자. Posting.source 로 저장된다.
    company: str      # 표시용 회사명

    @abstractmethod
    def fetch_list(self, ctx: BrowserContext) -> list[Posting]:
        """공고 목록 페이지를 열어 현재 게시된 공고를 모두 돌려준다."""

    @abstractmethod
    def fetch_location_text(self, ctx: BrowserContext, posting: Posting) -> str | None:
        """공고 상세에서 근무지 판단에 필요한 텍스트 조각만 돌려준다. 본문 전체를 저장하지 않는다."""
