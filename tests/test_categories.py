import pytest

from radar.categories import ai_keywords, ai_roles, categorize, is_card_company
from radar.companies import LG_MAJOR, SAMSUNG_MAJOR, in_group

AI_TITLES = [
    "[현대카드] AI Engineer_Agentic AI",
    "[현대카드] ML Engineer",
    "[현대카드] Data Scientist - LLM/Agentic AI R&D",
    "[현대카드] AI/ML Data Scientist",
    "[CTO] Speech AI 경력 채용",
    "[CDO] AI/빅데이터 경력 상시 모집",
    "[정보보안센터] AI보안 담당자 경력채용",
    "[LG CNS] Global 해외 석박사 AX 인재 상시 등록 공고",
    "데이터 엔지니어",
    "AI서비스 개발",
    "SW/AI/Automation",
    "머신러닝 엔지니어 (추천 시스템)",
    "MLOps Engineer",
    "Marketing Analytics Manager",
    "생성형 AI 서비스 기획",
]

NOT_AI_TITLES = [
    "[현대카드] 개인정보보호 기획 및 운영",
    "[현대커머셜] 부동산금융 (주선 및 Sell-Down)",
    "[LG CNS] 클라우드 데이터센터 구축/운영 분야 모집(경력)",
    "[비즈테크아이] 데이터베이스 담당자 모집 (경력)",
    "경력사원 채용(보건관리자)",
    "Retail Sales Manager",          # RETAIL 안의 AI
    "Email Marketing / HTML 퍼블리셔",  # EMAIL, HTML
    "Tax Accounting 담당",            # TAX 안의 AX
    "[SK AX] 재무 담당자 채용",         # 회사명의 AX
    "Main Frame 운영",
    "삼성전자 DS부문 설비 엔지니어",
]


@pytest.mark.parametrize("title", AI_TITLES)
def test_ai_titles_match(title):
    assert ai_keywords(title), title


@pytest.mark.parametrize("title", NOT_AI_TITLES)
def test_non_ai_titles_do_not_match(title):
    assert ai_keywords(title) == [], (title, ai_keywords(title))


def test_bundle_posting_matches_through_roles():
    job_text = "설계\n재료/소자/공정\nSW/AI/Automation\n품질/분석\nAI Data Engineer"
    assert ai_roles(job_text) == ["SW/AI/Automation", "AI Data Engineer"]
    assert categorize("삼성디스플레이", "경력사원 채용(연구개발, 제조기술)", job_text) == ["ai"]
    assert categorize("삼성중공업", "경력사원 채용(보건관리자)", "보건관리자") == []


def test_card_company_keeps_every_posting():
    assert categorize("현대카드", "[현대카드] 대손 충당금 관리") == ["card"]
    assert categorize("현대카드", "[현대카드] AI Engineer") == ["ai", "card"]
    assert categorize("현대커머셜", "[현대커머셜] 부동산금융") == []
    assert is_card_company("KB국민카드") and is_card_company("BC카드") and not is_card_company("삼성화재")


def test_major_affiliates_only():
    assert in_group("삼성전자 DX부문", SAMSUNG_MAJOR)
    assert in_group("삼성물산 건설부문", SAMSUNG_MAJOR)
    assert not in_group("삼성전자서비스", SAMSUNG_MAJOR)
    assert not in_group("삼성문화재단", SAMSUNG_MAJOR)
    assert in_group("LG CNS", LG_MAJOR) and in_group("LG유플러스", LG_MAJOR)
    assert not in_group("비즈테크아이", LG_MAJOR) and not in_group("하이엠솔루텍", LG_MAJOR)


def test_group_name_matching_ignores_case_and_corporate_marks():
    from radar.companies import HANWHA_MAJOR, KT_MAJOR, SK_MAJOR

    assert in_group("(주)한화 글로벌부문", HANWHA_MAJOR) and in_group("한화오션(주)", HANWHA_MAJOR)
    assert in_group("한화시스템/ICT", HANWHA_MAJOR) and not in_group("한화커넥트", HANWHA_MAJOR)
    assert in_group("SK주식회사(AX)", SK_MAJOR) and in_group("SK케미칼(LS)", SK_MAJOR)
    assert not in_group("SK picglobal", SK_MAJOR) and not in_group("SK네트웍스서비스", SK_MAJOR)
    assert in_group("kt cloud", KT_MAJOR) and in_group("KT", KT_MAJOR) and not in_group("kt netcore", KT_MAJOR)


def test_abbreviations_are_case_sensitive_and_facility_jobs_are_not_ai():
    assert ai_keywords("생수 500ml 영업 담당") == []
    assert ai_keywords("AI 데이터센터 전력설비 구축 분야 전문가 영입") == []
    assert ai_keywords("(주)이마트 AI컨텍센터 고객상담 스태프 사원 모집") == []
    assert ai_keywords("KT클라우드안산AIDC신축공사 현장 채용") == []
    assert ai_keywords("AI 데이터센터 운영 및 AI 모델 서빙 엔지니어") == ["AI"]
