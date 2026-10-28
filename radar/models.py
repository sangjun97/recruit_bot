from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class Region(BaseModel):
    sido: str                      # 예: 서울특별시, 경기도
    sigungu: str | None = None     # 예: 영등포구, 용인시, 이천시 (시·군·구 단위)
    method: str                    # rule | alias | llm | none

    def label(self) -> str:
        return f"{self.sido} {self.sigungu}".strip() if self.sigungu else self.sido


class Posting(BaseModel):
    """한 소스에서 수집한 공고 하나. id는 '<source>:<external_id>'로 전역 고유."""

    source: str
    external_id: str
    company: str
    title: str
    url: str
    start_at: datetime | None = None
    end_at: datetime | None = None
    career_type: str | None = None       # 신입 / 경력 / 인턴 등
    employment_type: str | None = None   # 정규 / 계약 등
    status: str | None = None            # 접수중 / 접수마감 등 (소스 표기 그대로)
    location_raw: str | None = None      # 공고 본문에서 근무지로 보이는 원문 조각
    regions: list[Region] = Field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.source}:{self.external_id}"
