"""채용 포털(사람인·잡코리아) 보완 수집기와 포털 중복 제거."""
from datetime import datetime

from radar.categories import categorize_row
from radar.dedupe import drop_portal_duplicates, posting_key
from radar.sources import SOURCES, jobkorea, saramin

NOW = datetime(2026, 11, 22, 19, 0)

SARAMIN = """
<div id="rec-55342364" class="list_item"><div class="box_item">
  <div class="col notification_info"><div class="job_tit">
    <a class="str_tit " title="2026 하나카드 애플리케이션 아키텍트 경력직 채용" href="/zf_user/jobs/relay/view?view_type=list&amp;rec_idx=55342364"><span>2026 하나카드 애플리케이션 아키텍트 경력직 채용</span></a>
  </div><div class="job_meta"><span class="job_sector"><span>아키텍쳐</span></span></div></div>
  <div class="col recruit_info"><ul><li><p class="work_place">인천 서해구</p></li><li><p class="career">경력 7년↑ · 정규직</p></li><li><p class="education">학력무관</p></li></ul></div>
  <div class="col support_info"><a class="sri_btn_md" href="/zf_user/jobs/relay/view?view_type=list&amp;rec_idx=55342364"><span>홈페이지 지원</span></a>
    <p class="support_detail"><span class="date">채용시</span><span class="deadlines">33일 전 등록</span></p></div>
</div></div>
<div id="rec-55191896" class="list_item"><div class="box_item">
  <div class="job_tit"><a class="str_tit" title="AI Agent 및 AI 서비스 개발 Product Engineer 경력직 채용" href="/zf_user/jobs/relay/view?view_type=list&amp;rec_idx=55191896"><span>AI Agent …</span></a></div>
  <div class="job_meta"><span class="job_sector"><span>AI(인공지능)</span></span></div>
  <div class="col recruit_info"><ul><li><p class="work_place">인천 서해구</p></li><li><p class="career">경력 1년↑</p></li></ul></div>
  <div class="col support_info"><span class="sri_btn_md">접수마감</span><p class="support_detail"><span class="date">~10.14(수)</span><span class="deadlines">51일 전 등록</span></p></div>
</div></div>
<div id="rec-1" class="list_item"><div class="box_item">
  <div class="job_tit"><a class="str_tit" title="[신한카드] 발급실- 공카드,봉입 업무" href="/zf_user/jobs/relay/view?rec_idx=777"><span>x</span></a></div>
  <div class="col recruit_info"><ul><li><p class="work_place">서울 중구</p></li><li><p class="career">경력무관 · 계약직</p></li></ul></div>
  <div class="col support_info"><p class="support_detail"><span class="date">~12.03(목)</span><span class="deadlines">5일 전 등록</span></p></div>
</div></div>
"""


def test_saramin_company_list():
    ps = saramin.parse_list(SARAMIN, "saramin_hanacard", "하나카드", NOW)
    assert [p.external_id for p in ps] == ["55342364", "55191896", "777"]
    p = ps[0]
    assert p.company == "하나카드" and p.status == "접수중" and p.end_at is None           # '채용시' 는 마감일 없음
    assert p.url == "https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=55342364"
    assert p.start_at == datetime(2026, 10, 20) and p.career_type == "경력" and p.employment_type == "정규직"
    assert p.job_text == "아키텍쳐" and p.location_raw == "인천 서해구" and categorize_row(p) == ["card"]
    assert ps[1].status == "접수마감" and ps[1].end_at == datetime(2026, 10, 14, 23, 59)
    assert categorize_row(ps[1]) == ["ai", "card"]                                       # 직무 분류 'AI(인공지능)'
    assert ps[2].end_at == datetime(2026, 12, 3, 23, 59) and ps[2].career_type == "신입/경력" and ps[2].employment_type == "계약직"


def test_saramin_deadline_without_year_rolls_into_next_year():
    december = datetime(2026, 12, 20)
    assert saramin._end_date("~01.18(월)", december) == datetime(2027, 1, 18, 23, 59)
    assert saramin._end_date("~12.25(금)", december) == datetime(2026, 12, 25, 23, 59)
    assert saramin._end_date("오늘마감", december) == datetime(2026, 12, 20, 23, 59)
    assert saramin._end_date("내일마감", december) == datetime(2026, 12, 21, 23, 59)
    assert saramin._end_date("상시채용", december) is None


def _jk_card(gid: str, title: str, corp: str, rest: str) -> str:
    href = f"https://www.jobkorea.co.kr/Recruit/GI_Read/{gid}?Oem_Code=C1&amp;logpath=1"
    return (f'<div class="flex w-full gap-5 p-7"><div><a href="{href}"><img alt="{corp} 로고" src="x.png"></a></div><div class="w-full">'
            f'<div><span>믿고보는 대기업</span><button><span class="sr-only">스크랩</span></button></div>'
            f'<div><a href="{href}" data-sentry-component="Title"><span>{title}</span></a></div>'
            f'<span><a href="{href}"><span>{corp}</span></a></span>{rest}</div></div>')


JOBKOREA = "<html><title>'하나카드' 관련 채용공고 | 총 825건의 검색결과</title><body>" + "".join([
    _jk_card("50206712", "2026 하나카드 애플리케이션 아키텍트 경력직 채용", "하나카드㈜",
             "<span>인천 서해구</span><span>증권·보험·카드, 소프트웨어개발자</span><span>홈페이지 지원</span><span>경력7년↑</span>"),
    _jk_card("50384468", "[신입환영] 영업없는 하나카드 인바운드상담사 채용", "제이앤비컨설팅",
             "<span>서울 중구</span><span>고객상담</span><span>즉시지원</span><span>경력무관</span>"),
    _jk_card("50397091", "2026년 하나카드 UX 설계 기획 계약직 수시채용", "하나카드㈜",
             "<span>서울 중구</span><span>UI/UX디자이너</span><span>홈페이지 지원</span><span>경력3년↑</span>"),
]) + "</body></html>"


def test_jobkorea_keeps_only_postings_by_the_company_itself():
    ps, named = jobkorea.parse_search(JOBKOREA, "jobkorea_hanacard", "하나카드", {"하나카드"})
    assert named == 3 and [p.external_id for p in ps] == ["50206712", "50397091"]   # 파견·대행 업체 공고는 뺀다
    p = ps[0]
    assert p.company == "하나카드" and p.url == "https://www.jobkorea.co.kr/Recruit/GI_Read/50206712"
    assert p.title == "2026 하나카드 애플리케이션 아키텍트 경력직 채용" and p.career_type == "경력"
    assert p.location_raw == "인천 서해구" and p.job_text == "증권·보험·카드, 소프트웨어개발자" and p.end_at is None
    assert jobkorea.norm_company("(주) 하나카드") == jobkorea.norm_company("하나카드㈜") == "하나카드"


def test_duplicate_posting_on_two_portals_is_shown_once():
    rows = [
        {"id": "jobkorea_hanacard:1", "source": "jobkorea_hanacard", "company": "하나카드", "title": "2026 하나카드 애플리케이션 아키텍트 경력직 채용"},
        {"id": "saramin_hanacard:9", "source": "saramin_hanacard", "company": "하나카드", "title": "2026 하나카드  애플리케이션 아키텍트 경력직 채용 "},
        {"id": "jobkorea_hanacard:2", "source": "jobkorea_hanacard", "company": "하나카드", "title": "2026년 하나카드 UX 설계 기획 계약직 수시채용"},
    ]
    order = ["saramin_hanacard", "jobkorea_hanacard"]
    kept, dropped = drop_portal_duplicates(rows, order, set(order))
    assert [r["id"] for r in kept] == ["saramin_hanacard:9", "jobkorea_hanacard:2"]   # 소스 목록에서 앞선 사람인 것을 남긴다
    assert [r["id"] for r in dropped] == ["jobkorea_hanacard:1"]


def test_official_posting_wins_over_portal_copy_and_open_wins_over_closed():
    official = {"id": "shinhancard:1", "source": "shinhancard", "company": "신한카드", "title": "데이터 분석 경력직"}
    portal = {"id": "saramin_shinhancard:5", "source": "saramin_shinhancard", "company": "신한카드(주)", "title": "데이터분석 경력직"}
    kept, dropped = drop_portal_duplicates([portal, official], ["shinhancard", "saramin_shinhancard"], {"saramin_shinhancard"})
    assert kept == [official] and dropped == [portal]
    # 공식 사이트 것이 이미 마감됐고 포털 것은 접수 중이면 포털 것을 남긴다
    closed_official = {**official, "_open": False}
    kept, dropped = drop_portal_duplicates([portal, closed_official], ["shinhancard", "saramin_shinhancard"], {"saramin_shinhancard"})
    assert kept == [portal, closed_official] and dropped == []
    assert posting_key("하나카드㈜", "AI Engineer (경력)") == posting_key("(주)하나카드", "ai engineer(경력)")


def test_portal_sources_are_flagged_and_throttled():
    portals = [s for s in SOURCES if s.portal]
    assert {s.key for s in portals} == {"saramin_hanacard", "saramin_lottecard", "saramin_shinhancard", "jobkorea_hanacard", "jobkorea_lottecard"}
    assert all(s.min_interval_min >= 180 and not s.llm_ok for s in portals)
    keys = [s.key for s in SOURCES]
    assert keys.index("saramin_hanacard") < keys.index("jobkorea_hanacard")   # 겹치면 마감일 정보가 있는 사람인을 남긴다
