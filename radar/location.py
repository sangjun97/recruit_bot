"""근무지 추출: 규칙(사전·별칭) → 실패 시 LLM → 사전으로 검증하는 혼합 방식."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from .config import ROOT, Settings
from .models import Region

REGIONS_PATH = ROOT / "data" / "regions.json"

# 공고 본문에서 근무지 정보를 담고 있을 가능성이 높은 줄을 고르는 패턴
LOCATION_LINE_RE = re.compile(
    r"(근무\s*(지|장소|지역|처)|소재지|사업장|배치\s*지역|근무\s*예정|Location|Work\s*place)", re.IGNORECASE
)
HANGUL = re.compile(r"[가-힣]")


class RegionDict:
    def __init__(self, data: dict):
        self.sido: dict[str, list[str]] = data["sido"]
        self.sido_aliases: dict[str, str] = data.get("sido_aliases", {})
        self.aliases: dict[str, tuple[str, str]] = {k: tuple(v) for k, v in data.get("aliases", {}).items()}
        self.sigungu_to_sido: dict[str, list[str]] = {}
        for sido, lst in self.sido.items():
            for sgg in lst:
                self.sigungu_to_sido.setdefault(sgg, []).append(sido)
        # 긴 이름부터 매칭해 '강남구' 안의 '남구' 같은 부분 일치를 막는다
        self._sgg_names = sorted(self.sigungu_to_sido, key=len, reverse=True)
        self._sido_tokens = sorted(set(self.sido) | set(self.sido_aliases), key=len, reverse=True)
        self._alias_names = sorted(self.aliases, key=len, reverse=True)
        # '평택', '화성'처럼 접미사(시·군·구)를 뗀 이름. 전국에서 유일하고 시·도 이름과 겹치지 않을 때만 쓴다
        stems: dict[str, str] = {}
        counts: dict[str, int] = {}
        for sgg in self.sigungu_to_sido:
            stem = sgg[:-1]
            counts[stem] = counts.get(stem, 0) + len(self.sigungu_to_sido[sgg])
            stems[stem] = sgg
        self.stems: dict[str, str] = {
            st: sgg for st, sgg in stems.items()
            if len(st) >= 2 and counts[st] == 1 and st not in self.sido_aliases and st not in self.sido
        }
        self._stem_names = sorted(self.stems, key=len, reverse=True)

    def canonical_sido(self, token: str) -> str | None:
        if token in self.sido:
            return token
        return self.sido_aliases.get(token)

    def is_valid(self, sido: str, sigungu: str | None) -> bool:
        if sido not in self.sido:
            return False
        return sigungu is None or sigungu in self.sido[sido]

    # --- 규칙 기반 추출 --------------------------------------------------------
    def extract(self, text: str) -> list[Region]:
        found: dict[tuple[str, str | None], Region] = {}
        consumed: list[tuple[int, int]] = []

        def overlaps(s: int, e: int) -> bool:
            return any(s < ce and e > cs for cs, ce in consumed)

        def followed_by_hangul(m: re.Match) -> bool:
            after = text[m.end():m.end() + 1]
            return bool(after) and bool(HANGUL.match(after))

        # 1) 별칭(사업장·역·지명)
        for name in self._alias_names:
            for m in re.finditer(re.escape(name), text):
                if overlaps(*m.span()):
                    continue
                sido, sgg = self.aliases[name]
                found.setdefault((sido, sgg), Region(sido=sido, sigungu=sgg, method="alias"))
                consumed.append(m.span())

        # 2) 시·군·구 이름 (+ 앞쪽의 시·도 힌트로 중복 이름을 해소)
        for name in self._sgg_names:
            for m in re.finditer(re.escape(name), text):
                if overlaps(*m.span()) or followed_by_hangul(m):
                    continue
                before = text[max(0, m.start() - 12):m.start()]
                sido = None
                for tok in self._sido_tokens:
                    if tok in before:
                        cand = self.canonical_sido(tok)
                        if cand and name in self.sido.get(cand, []):
                            sido = cand
                            break
                if sido is None:
                    cands = self.sigungu_to_sido[name]
                    if len(cands) != 1:
                        continue  # 중복 이름인데 힌트가 없으면 LLM 단계로 넘긴다
                    sido = cands[0]
                found.setdefault((sido, name), Region(sido=sido, sigungu=name, method="rule"))
                consumed.append(m.span())

        # 3) 접미사 없는 시·군 이름 (예: '평택/화성/기흥 중 배치'). 뒤에 한글이 이어지면 다른 단어로 본다
        for stem in self._stem_names:
            for m in re.finditer(re.escape(stem), text):
                if overlaps(*m.span()) or followed_by_hangul(m):
                    continue
                sgg = self.stems[stem]
                sido = self.sigungu_to_sido[sgg][0]
                found.setdefault((sido, sgg), Region(sido=sido, sigungu=sgg, method="rule"))
                consumed.append(m.span())

        # 4) 시·도만 언급된 경우 (예: '서울 본사', '세종', '대전광역시'). 이미 그 시·도의 시·군·구가 잡혔으면 생략
        for tok in self._sido_tokens:
            for m in re.finditer(re.escape(tok), text):
                if overlaps(*m.span()):
                    continue
                if followed_by_hangul(m) and tok not in self.sido:
                    continue  # '서울대', '경기장' 같은 오탐 방지
                sido = self.canonical_sido(tok)
                if sido and not any(k[0] == sido for k in found):
                    found.setdefault((sido, None), Region(sido=sido, sigungu=None, method="rule"))
                    consumed.append(m.span())
        return list(found.values())


@lru_cache(maxsize=1)
def load_region_dict(path: Path = REGIONS_PATH) -> RegionDict:
    return RegionDict(json.loads(path.read_text(encoding="utf-8")))


def pick_location_lines(text: str, max_lines: int = 8) -> str | None:
    """공고 본문 전체 중 근무지 관련 줄만 고른다. 본문 전체를 저장하지 않기 위한 장치."""
    lines = [ln.strip() for ln in text.splitlines()]
    picked: list[str] = []
    for i, ln in enumerate(lines):
        if ln and LOCATION_LINE_RE.search(ln):
            picked.append(ln)
            # '근무지 :' 처럼 값이 다음 줄에 있는 경우 한 줄 더 가져온다
            if ln.rstrip().endswith((":", "：")) and i + 1 < len(lines) and lines[i + 1]:
                picked.append(lines[i + 1])
        if len(picked) >= max_lines:
            break
    return "\n".join(dict.fromkeys(picked)) or None


# --- LLM 보조 추출 -----------------------------------------------------------
class _LLMRegion(BaseModel):
    sido: str
    sigungu: str | None


class _LLMResult(BaseModel):
    regions: list[_LLMRegion]
    unspecified: bool


def extract_with_llm(text: str, settings: Settings, rdict: RegionDict) -> list[Region]:
    """규칙으로 못 잡은 경우에만 호출. 결과는 사전으로 검증해 환각을 걸러낸다."""
    if not settings.anthropic_api_key:
        return []
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    sido_list = ", ".join(rdict.sido)
    prompt = (
        "다음은 한국 채용 공고에서 근무지와 관련된 문장입니다. 실제 근무지를 시·도와 시·군·구 단위로 추출하세요.\n"
        "규칙:\n"
        f"- sido는 반드시 다음 중 하나의 정식 명칭으로: {sido_list}\n"
        "- sigungu는 해당 시·도의 시·군·구 정식 명칭(예: 영등포구, 용인시, 이천시). 모르면 null.\n"
        "- 여러 근무지가 가능하면 모두 나열. 근무지가 미정이거나 문장에 없으면 regions를 비우고 unspecified=true.\n"
        "- 본사·사업장 이름은 실제 위치를 확실히 아는 경우에만 지역으로 바꾸고, 확신이 없으면 넣지 마세요.\n\n"
        f"문장:\n{text}"
    )
    try:
        resp = client.messages.parse(
            model=settings.llm_model,
            max_tokens=1024,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}],
            output_format=_LLMResult,
        )
    except anthropic.APIError as e:  # 네트워크·한도 등 실패는 추출 실패로만 처리
        print(f"  [llm] 호출 실패: {e}")
        return []
    parsed = resp.parsed_output
    if parsed is None:
        return []
    out: list[Region] = []
    for r in parsed.regions:
        sido = rdict.canonical_sido(r.sido) or r.sido
        sgg = r.sigungu
        if not rdict.is_valid(sido, sgg):
            if rdict.is_valid(sido, None):
                sgg = None
            else:
                continue
        out.append(Region(sido=sido, sigungu=sgg, method="llm"))
    return out


def extract_regions(location_text: str | None, settings: Settings) -> list[Region]:
    if not location_text:
        return []
    rdict = load_region_dict()
    regions = rdict.extract(location_text)
    if regions:
        return regions
    return extract_with_llm(location_text, settings, rdict)
