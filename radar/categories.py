"""공고 분류: 어떤 공고를 보여주고 알릴지 정한다.

관심 분야는 두 가지다.
- card: 카드사 공고. 직무와 상관없이 전부 보여준다.
- ai:   대기업의 AI·데이터 직무 공고. 제목과 직무명에 키워드가 있을 때만 보여준다.

분류는 저장된 필드(회사명·제목·직무 텍스트)만으로 계산한다. DB 에 결과를 저장하지 않으므로
키워드를 고치면 다음 실행부터 기존 공고에도 바로 적용된다.
"""
from __future__ import annotations

import re

CATEGORY_LABELS = {"ai": "AI·데이터", "card": "카드사"}

# --- 카드사 -------------------------------------------------------------------
# 회사명에 '카드'가 들어가면 카드사로 본다 (현대카드, 삼성카드, 신한카드, KB국민카드, 롯데카드, 우리카드, 하나카드, BC카드 ...).
CARD_NAME_RE = re.compile(r"카드")


def is_card_company(company: str | None) -> bool:
    return bool(company and CARD_NAME_RE.search(company))


# --- AI·데이터 직무 ------------------------------------------------------------
# 약어는 영문자에 붙어 있지 않을 때만 잡는다 (MAIN, EMAIL, HTML, TAX 오탐 방지).
# 한글·숫자·기호에는 붙어 있어도 된다 (AI서비스, AI/ML, AI보안).
def _abbr(*words: str) -> str:
    # 약어는 대문자 표기만 본다('500ml', 'rag' 같은 소문자 낱말 오탐 방지)
    return r"(?-i:(?<![A-Za-z])(?:" + "|".join(words) + r")(?![A-Za-z]))"


_AI_PATTERNS = [
    _abbr("AI", "GenAI", "ML", "LLMs?", "sLLM", "VLM", "NLP", "NLU", "RAG", "AGI", "AX"),
    r"MLOps|LLMOps|AIOps",
    r"인공\s*지능|머신\s*러닝|딥\s*러닝|기계\s*학습|강화\s*학습|생성형|언어\s*모델|자연어|프롬프트",
    r"음성\s*(?:인식|합성)|컴퓨터\s*비전|영상\s*(?:인식|분석)|추천\s*(?:시스템|모델|알고리즘|엔진)",
    r"Machine\s*Learning|Deep\s*Learning|Reinforcement\s*Learning|Computer\s*Vision|Generative|Agentic",
    r"Prompt\s*Engineer|Applied\s*Scientist",
    r"Data\s*Scien|Data\s*Analy|Data\s*Engineer|Data\s*Platform|Data\s*(?:분석|사이언|엔지니어)|Analytics|Big\s*Data",
    r"데이터\s*(?:사이언|과학|분석|엔지니어|마이닝|모델링|플랫폼)|빅\s*데이터",
]
AI_RE = re.compile("|".join(f"(?:{p})" for p in _AI_PATTERNS), re.IGNORECASE)

# 키워드가 들어 있지만 AI·데이터 직무가 아닌 표기. 매칭 전에 지운다.
# - 회사·조직 이름: 'SK AX', 'AI연구원'
# - 시설·상담 업무: 'AI 데이터센터 전력설비 구축', 'AI컨택센터 고객상담'
_COMPANY_NOISE_RE = re.compile(
    r"SK\s*AX|LG\s*AI\s*연구원|AI\s*연구원|AI\s*(?:데이터\s*센터|컨[택텍]\s*센터|콜\s*센터|고객\s*센터)", re.IGNORECASE
)


def ai_keywords(text: str | None) -> list[str]:
    """text 에서 찾은 AI·데이터 키워드(중복 제거, 등장 순)."""
    if not text:
        return []
    cleaned = _COMPANY_NOISE_RE.sub(" ", text)
    return list(dict.fromkeys(m.group(0) for m in AI_RE.finditer(cleaned)))


def ai_roles(job_text: str | None, limit: int = 8) -> list[str]:
    """직무 텍스트(줄 단위 직무명) 중 AI·데이터에 해당하는 직무명만 고른다. 여러 직무를 묶은 공고에서 쓴다."""
    out: list[str] = []
    for line in (job_text or "").splitlines():
        line = line.strip()
        if line and ai_keywords(line) and line not in out:
            out.append(line)
    return out[:limit]


def is_ai_posting(title: str | None, job_text: str | None) -> bool:
    return bool(ai_keywords(title) or ai_roles(job_text, limit=1))


def categorize(company: str | None, title: str | None, job_text: str | None = None) -> list[str]:
    """공고가 속하는 관심 분야 목록. 비어 있으면 보여주지도 알리지도 않는다."""
    cats: list[str] = []
    if is_ai_posting(title, job_text):
        cats.append("ai")
    if is_card_company(company):
        cats.append("card")
    return cats


def _field(row, key: str):
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[key]                 # sqlite3.Row
    except (KeyError, IndexError, TypeError):
        return getattr(row, key, None)  # Posting


def categorize_row(row) -> list[str]:
    """DB 행(dict·sqlite3.Row)이나 Posting 을 받아 분류한다."""
    return categorize(_field(row, "company"), _field(row, "title"), _field(row, "job_text"))
