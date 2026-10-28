"""수집 소스 레지스트리. 새 기업을 추가할 때는 CLAUDE.md의 조사 절차(robots.txt·약관·제공 방식)를 먼저 거친다."""
from __future__ import annotations

from .base import Source
from .recruiter_co_kr import RecruiterCoKrSource
from .samsung_careers import SamsungCareersSource
from .lg_careers import LGCareersSource

SOURCES: list[Source] = [
    RecruiterCoKrSource(key="hyundaicard", company="현대카드/현대커머셜", subdomain="careerhyundai"),
    # 삼성 관계사 전체. 삼성전자만 보려면 companies={"삼성전자 DX부문", "삼성전자 DS부문"}
    SamsungCareersSource(key="samsung"),
    # LG 계열사 전체(LG전자·화학·에너지솔루션·이노텍·유플러스·CNS 등). 일부만 보려면 companies={"LG전자", ...}
    LGCareersSource(key="lg"),
]


def get_sources(keys: list[str] | None = None) -> list[Source]:
    if not keys:
        return SOURCES
    wanted = set(keys)
    picked = [s for s in SOURCES if s.key in wanted]
    missing = wanted - {s.key for s in picked}
    if missing:
        raise SystemExit(f"알 수 없는 소스: {', '.join(sorted(missing))}. 사용 가능: {', '.join(s.key for s in SOURCES)}")
    return picked
