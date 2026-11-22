"""2026-11-22 에 추가한 수집기들의 파서 테스트. 조사 때 받은 실제 응답을 줄인 것을 쓴다."""
import json
from datetime import datetime

from radar.categories import categorize_row
from radar.sources import PENDING_SOURCES, SOURCES, get_sources
from radar.sources import careerlink, cj, greeting, hanwha, hd_hyundai, hmg, kakao, kt, lotte, naver, shinsegae


def test_registry_keys_are_unique_and_have_site_urls():
    every = SOURCES + PENDING_SOURCES
    keys = [s.key for s in every]
    assert len(keys) == len(set(keys))
    assert all(s.site_url.startswith("https://") and s.company for s in every)


def test_get_sources_by_key():
    assert get_sources() is SOURCES
    assert [s.key for s in get_sources(["hanwha", "kbcard"])] == ["kbcard", "hanwha"]   # 등록 순서대로
    # 승인 대기 소스는 기본 실행에 들어가지 않는다(지금은 비어 있다)
    assert not {s.key for s in PENDING_SOURCES} & {s.key for s in get_sources()}


# --- 신한카드 (화면에 그려진 표를 읽는다) -------------------------------------------
def test_shinhancard_rows():
    from radar.sources import shinhancard

    now = datetime(2026, 11, 22, 16, 0)
    notice = [
        {"cells": ["정기채용", "2026년 신한카드 신입사원 채용 공고", "2026.11.09", "2026.11.16 새글", "서류심사중"],
         "title": "2026년 신한카드 신입사원 채용 공고", "click": "goDetail('1','HPD')"},
        {"cells": ["{{hmpBsnDtlTxt}}", "{{sbjtNm}}"], "title": "{{sbjtNm}}", "click": "goDetail('{{ancGdSeqN}}','{{hmpBlbBsnCCd}}')"},
    ]
    ps = shinhancard.parse_rows(notice, "shinhancard", "notice", now)
    assert len(ps) == 1   # 값이 채워지지 않은 틀 행은 건너뛴다
    p = ps[0]
    assert p.external_id == "HPD-1-20261109" and p.company == "신한카드" and p.status == "접수마감"
    assert p.url == "https://www.shinhancard.com/mob/MOBFMCOMN/MOBFMCOM02.shc?ancGdSeqN=1&hmpBlbBsnCCd=HPD"
    assert p.start_at == datetime(2026, 11, 9) and p.end_at == datetime(2026, 11, 16, 23, 59) and p.employment_type == "정기채용"
    career = [{"cells": ["데이터 분석 경력직", "2026.11.20 ~ 2026.12.05"], "title": "데이터 분석 경력직", "click": "goApply('A12')"}]
    q = shinhancard.parse_rows(career, "shinhancard", "career", now)[0]
    assert q.status == "접수중" and q.career_type == "경력" and q.url.endswith("MOBFMCOM03.shc") and q.external_id.startswith("career-")
    assert categorize_row(q) == ["ai", "card"]


# --- NH농협카드 --------------------------------------------------------------------
NH_LIST = """
<table class="table"><tbody>
<tr><td><i class="icon_txt">일반계약직</i></td>
 <td class="t_left"><div><a href="#" onclick="javascript:fn_jbnfDtl('91049')">NH농협은행 NH카드분사(카드가맹점사업팀) 일반계약직직원 채용</a></div></td>
 <td>NH농협은행</td><td>본부 NH카드분사</td><td><div><span>NH농협카드</span></div></td><td class="date">2026-11-20 ~ 2026-12-01</td></tr>
<tr><td><i>파트타임</i></td>
 <td><a href="#" onclick="javascript:fn_jbnfDtl('91232')">NH농협은행 안동시지부 사무지원직 채용 (체크카드 업무)</a></td>
 <td>NH농협은행</td><td>경북 안동시</td><td><span>안동시지부</span></td><td class="date">2026-11-12 ~ 2026-11-30</td></tr>
<tr><td><i>전문직</i></td>
 <td><a href="#" onclick="javascript:fn_jbnfDtl('90647')">NH농협은행 NH카드분사 카드마케팅2팀 전문계약직 직원 채용공고</a></td>
 <td>NH농협은행</td><td>본부 NH카드분사</td><td><span>NH농협카드</span></td><td class="date">2026-10-26 ~ 2026-11-15</td></tr>
</tbody></table>"""


def test_nonghyup_keeps_only_card_division_rows():
    from radar.sources import nonghyup

    ps = nonghyup.parse_list(NH_LIST, "nhcard", datetime(2026, 11, 22, 16, 0))
    assert [p.external_id for p in ps] == ["91049", "90647"]   # 지점의 '체크카드' 공고는 카드 부문이 아니다
    p = ps[0]
    assert p.company == "NH농협카드" and p.status == "접수중" and p.employment_type == "일반계약직"
    assert p.url == "https://with.nonghyup.com/jbnf/jbnfDtl.do?jbnfSqno=91049"
    assert p.end_at == datetime(2026, 12, 1, 23, 59) and p.end_date_only and categorize_row(p) == ["card"]
    assert ps[1].status == "접수마감"
    detail = "<html><body><p>- 근 무 지 : 서울시 종로구 통일로 134, NH농협타워</p><p>- 담당업무 : 가맹점 관리</p></body></html>"
    assert nonghyup.location_text_from_detail(detail) == "- 근무지 : 서울시 종로구 통일로 134, NH농협타워"


# --- 두산 -------------------------------------------------------------------------
DOOSAN_LIST = """
<ul class="list-cont">
 <li><a href="javascript:void(0);" onclick="goDetail('1000367001', 'C_REC_MGT_04', 'C_REC_TYPE_05', '30000000');" class="list-tit">
   <div class="company"> 두산로보틱스 <span class="badge-type">  경력  </span></div>
   <strong>Physical AI Engineer</strong>
   <div class="deadline"><span class="badge-day"> D-39 </span> 2026-10-08 ~ 2026-12-31 </div></a></li>
 <li><a href="javascript:void(0);" onclick="goDetail('1000367274', 'C_REC_MGT_04', 'C_REC_TYPE_05', '30000000');" class="list-tit">
   <div class="company"> 두산연강재단 <span class="badge-type"> 전문/생산/계약직 </span></div>
   <strong>두산아트센터(DAC) 홍보마케팅 매니저 채용 (계약직)</strong>
   <div class="deadline"><span class="badge-day">D-2</span> 2026-11-10 ~ 2026-11-24 </div></a></li>
</ul>"""


def test_doosan_parse_list_and_scope():
    from radar.companies import DOOSAN_MAJOR, in_group
    from radar.sources import doosan

    ps = doosan.parse_list(DOOSAN_LIST, "doosan")
    p = ps[0]
    assert p.external_id == "1000367001" and p.company == "두산로보틱스" and p.title == "Physical AI Engineer"
    assert p.career_type == "경력" and p.start_at == datetime(2026, 10, 8) and p.end_at == datetime(2026, 12, 31, 23, 59)
    assert p.url == "https://career.doosan.com/dsp/sa/RecList.jsp" and categorize_row(p) == ["ai"]
    assert ps[1].company == "두산연강재단" and ps[1].employment_type == "전문/생산/계약직" and ps[1].career_type is None
    assert in_group("(주)두산-전자", DOOSAN_MAJOR) and in_group("두산밥캣(주)", DOOSAN_MAJOR) and not in_group("두산연강재단", DOOSAN_MAJOR)


# --- 현대자동차·기아 ---------------------------------------------------------------
HMG = {"data": {"listCnt": 2, "list": [
    {"recuYy": "2026", "recuType": "N2", "recuCls": 413, "recuNoticeNm": " [ICT] Backend Developer - MLOps 개발 ",
     "applyStartDt": "20261116", "applyStartTm": "0900", "applyEndDt": "20261130", "applyEndTm": "1705",
     "secCodeNm": "IT", "fldCodeNm": "SW Development", "workPlaceCodeNm": "양재본사", "channelCodeNm": "경력", "logoNm": "현대"},
    {"recuYy": "2026", "recuType": "N5", "recuCls": 86, "recuNoticeNm": "[계약직] 서비스센터 고객안내요원 (대구)",
     "applyStartDt": "20260814", "applyStartTm": "1300", "applyEndDt": "20261231", "applyEndTm": "2359",
     "fldCodeNm": "직무별 상이", "workPlaceCodeNm": "기타지역", "channelCodeNm": "계약직"},
    {"recuNoticeNm": "식별자 없음"},
]}}


def test_hmg_parse_list():
    ps, total = hmg.parse_list(HMG, "hyundai", "현대자동차", "https://talent.hyundai.com", "hc")
    assert total == 2 and [p.external_id for p in ps] == ["2026-N2-413", "2026-N5-86"]
    p = ps[0]
    assert p.company == "현대자동차" and p.title == "[ICT] Backend Developer - MLOps 개발"
    assert p.url == "https://talent.hyundai.com/apply/applyView.hc?recuYy=2026&recuType=N2&recuCls=413"
    assert p.start_at == datetime(2026, 11, 16, 9, 0) and p.end_at == datetime(2026, 11, 30, 17, 5)
    assert p.career_type == "경력" and p.job_text == "SW Development" and p.location_raw == "양재본사"
    assert categorize_row(p) == ["ai"]
    assert ps[1].job_text == "" and categorize_row(ps[1]) == []


# --- 그리팅(현대오토에버) ----------------------------------------------------------
OPENINGS = [
    {"openingId": 210263, "title": "[Tech] AI Engineer - LLM 엔지니어",
     "workspaceDivision": {"id": 69, "division": "Core Tech(AI/DATA/Cloud/보안)"},
     "openDate": "2026-11-04T01:26:50Z", "dueDate": "2026-11-26T14:59:59Z",
     "openingJobPosition": {"openingJobPositions": [{
         "workspaceOccupation": {"id": 524, "occupation": "Data/AI(인공지능)"},
         "workspacePlace": {"location": "서울/경기", "place": "서울특별시 강남구 대치동"},
         "jobPositionCareer": {"careerType": "EXPERIENCED"}, "jobPositionEmployment": {"employmentType": "FULL_TIME_WORKER"}}]},
     "group": {"name": "현대오토에버"}},
    {"openingId": 245051, "title": "[Tech] Infra Security Engineer - 퍼블릭클라우드 보안",
     "workspaceDivision": {"id": 69, "division": "Core Tech(AI/DATA/Cloud/보안)"},
     "openDate": "2026-11-10T00:00:00Z", "dueDate": None,
     "openingJobPosition": {"openingJobPositions": [{"workspaceOccupation": {"occupation": "Security"}, "workspacePlace": None,
                                                    "jobPositionCareer": None, "jobPositionEmployment": None}]}},
]


def test_greeting_reads_next_data_and_converts_utc_to_kst():
    page = {"props": {"pageProps": {"dehydratedState": {"queries": [
        {"queryKey": ["career", "getOpeningFilters"], "state": {"data": {}}},
        {"queryKey": ["openings"], "state": {"data": OPENINGS}},
    ]}}}}
    html = f'<html><body><script id="__NEXT_DATA__" type="application/json">{json.dumps(page)}</script></body></html>'
    ps = greeting.parse_openings(greeting.openings_from_html(html), "autoever", "현대오토에버", "https://career.hyundai-autoever.com")
    p = ps[0]
    assert p.url == "https://career.hyundai-autoever.com/ko/o/210263"
    assert p.end_at == datetime(2026, 11, 26, 23, 59, 59) and p.start_at == datetime(2026, 11, 4, 10, 26, 50)
    assert p.career_type == "경력" and p.employment_type == "정규" and p.location_raw == "서울특별시 강남구 대치동"
    assert p.job_text == "Data/AI(인공지능)" and categorize_row(p) == ["ai"]
    # 사업부 이름('Core Tech(AI/DATA/...)')은 분류에 쓰지 않으므로 보안 직무는 AI 로 잡히지 않는다
    assert ps[1].end_at is None and ps[1].location_raw is None and categorize_row(ps[1]) == []


# --- 롯데 -------------------------------------------------------------------------
LOTTE_LIST = """
<ul class="job-card-list">
 <li><div class="job-card-group"><p class="bage-group"><span class="ico-bage-anncmtype">경력</span></p>
  <div class="cmp-name">롯데이노베이트</div>
  <div class="card-tit"><a class="line-clamp" href="/apply/announcement/detail/22004347">2026년 11월 롯데이노베이트 월드IS팀 JA Grade채용</a></div>
  <div class="card-foot clfix"><p class="date">2026.11.10 ~ 2026.11.23</p><p class="dday d-7">D-1</p></div></div></li>
 <li><div class="job-card-group"><div class="cmp-name">캐논코리아</div>
  <div class="card-tit"><a href="/apply/announcement/detail/22001111">영업 경력 채용</a></div></div></li>
</ul>"""
LOTTE_DETAIL = """
<div class="board-body"><table>
 <tr><th>모집분야</th><th><strong>근무지</strong></th><th>자격요건</th></tr>
 <tr><td>IS 운영</td><td>경상남도 김해</td><td>경력 3년 이상</td></tr>
 <tr><td>IS 개발</td><td>서울 송파구</td><td>경력 5년 이상</td></tr>
</table></div>"""


def test_lotte_list_and_detail():
    ps = lotte.parse_list(LOTTE_LIST, "lotte")
    assert [p.external_id for p in ps] == ["22004347", "22001111"]
    p = ps[0]
    assert p.company == "롯데이노베이트" and p.career_type == "경력" and p.end_date_only
    assert p.url == "https://recruit.lotte.co.kr/apply/announcement/detail/22004347"
    assert p.start_at == datetime(2026, 11, 10) and p.end_at == datetime(2026, 11, 23, 23, 59)
    assert ps[1].end_at is None
    assert lotte.location_text_from_detail(LOTTE_DETAIL) == "경상남도 김해\n서울 송파구"
    assert lotte.parse_list('<ul class="job-card-list"><li>채용중인 공고가 없습니다.</li></ul>', "lotte") == []


def test_lotte_challenge_page_is_an_error_not_an_empty_list():
    try:
        lotte.parse_list("<html><script src='/_Incapsula_Resource'></script></html>", "lotte")
    except lotte.BlockedError:
        return
    raise AssertionError("차단 페이지를 공고 0건으로 읽으면 안 된다")


# --- CJ ---------------------------------------------------------------------------
CJ = {"ErrorCode": 0, "ds_newRecruitList": [
    {"zz_jo_num": "J20261120040642", "gubun": "2", "zz_title": "[CJ ENM] 애널리틱스 엔지니어_경력채용", "compnm": "CJ ENM",
     "zz_target_1": "B", "zz_jo_type": "A", "job_cd_nm": "데이터분석", "location_cd_nm": "서울",
     "zz_str_dt_str": "2026.11.20", "zz_str_hh": "11", "zz_str_mi": "25",
     "zz_end_dt_str": "2026.12.06", "zz_end_hh": "23", "zz_end_mi": "00", "zz_till_hire": "N", "zz_close_yn": "N"},
    {"zz_jo_num": "8852", "gubun": "1", "zz_title": "2026년 하반기<BR>CJ올리브네트웍스 신입사원 모집", "compnm": "CJ올리브네트웍스",
     "zz_target_1": "A", "job_cd_nm": "직군별", "zz_till_hire": "Y", "zz_end_dt_str": None, "zz_close_yn": "Y"},
]}


def test_cj_parse_list():
    ps = cj.parse_list(CJ, "cj")
    p = ps[0]
    assert p.external_id == "J20261120040642" and p.company == "CJ ENM" and p.status == "접수중"
    assert p.url.endswith("/bestDetail.fo?direct=N&zz_jo_num=J20261120040642")
    assert p.start_at == datetime(2026, 11, 20, 11, 25) and p.end_at == datetime(2026, 12, 6, 23, 0)
    assert p.career_type == "경력" and p.employment_type == "정규" and p.job_text == "데이터분석" and p.location_raw == "서울"
    assert categorize_row(p) == ["ai"]
    q = ps[1]
    assert q.url.endswith("/detail.fo?zz_jo_num=8852") and q.title == "2026년 하반기 CJ올리브네트웍스 신입사원 모집"
    assert q.status == "접수마감" and q.end_at is None and q.job_text == ""


# --- 신세계 -----------------------------------------------------------------------
SSG = {"resultCode": "0000", "body": [
    {"pbancBscNo": 5255, "coNm": "신세계아이앤씨", "rcrutSeNm": "경력",
     "pbancNm": "[신세계아이앤씨] AI서비스개발 직무 인재모집(채용 시 마감)", "rcptBgngDt": "2026-10-01", "rcptEndDt": "2026-12-31 16:46",
     "dutySeCd": [{"dutySeCd": "AA00", "dutyNm": "IT/디지털"}], "delYn": "N", "rgtrIpAddr": "10.0.0.1"},
    {"pbancBscNo": 5263, "coNm": "이마트", "rcrutSeNm": "신입", "pbancNm": "(주)이마트 AI컨텍센터 고객상담 스태프 사원 모집",
     "rcptBgngDt": "2026-11-20", "rcptEndDt": "2026-11-29 23:59", "dutySeCd": [{"dutyNm": "매장/서비스"}], "delYn": "N"},
]}


def test_shinsegae_parse_list_and_detail():
    ps = shinsegae.parse_list(SSG, "shinsegae")
    p = ps[0]
    assert p.external_id == "5255" and p.url == "https://job.shinsegae.com/rcrut/detail/5255"
    assert p.start_at == datetime(2026, 10, 1) and p.end_at == datetime(2026, 12, 31, 16, 46)
    assert p.career_type == "경력" and p.job_text == "IT/디지털" and categorize_row(p) == ["ai"]
    assert categorize_row(ps[1]) == []   # 'AI컨텍센터 고객상담'은 AI 직무가 아니다
    detail = {"body": {"dutyInfoCn": "<p>담당업무: 서비스 개발</p><p>근무지역 : 본사 및 외부사업장(서울)</p>", "inqplCn": "문의 a@b.c"}}
    assert shinsegae.location_text_from_detail(detail) == "근무지역 : 본사 및 외부사업장(서울)"


# --- HD현대 -----------------------------------------------------------------------
HD = {"data": [
    {"recruitNoticeSn": 271656, "recruitNoticeName": "[HD한국조선해양] 2026년 AIX 경력 채용", "companyCategory": "HD한국조선해양",
     "recruitClassName": "경력", "recruitTypeName": "일반채용", "isInProgress": True,
     "receiveStartDatetime": "2026-11-06 00:00:00", "receiveEndDatetime": "2026-11-30 14:00:59",
     "recruitSectorList": [
         {"companyName": "HD한국조선해양", "job": "AI", "jobDetail": "자율 작업 인지 기술 개발", "area": "분당(GRC)"},
         {"companyName": "HD한국조선해양", "job": "AI", "jobDetail": "자율작업/주행 E2E 학습 알고리즘 개발", "area": "분당(GRC)"}],
     "contents": "<div>본문</div>", "submittedResumeCount": 9},
    {"recruitNoticeSn": 1, "recruitNoticeName": "지난 공고", "companyCategory": "HD현대중공업", "isInProgress": True,
     "receiveStartDatetime": "2024-01-01 00:00:00", "receiveEndDatetime": "2024-02-01 00:00:59", "recruitSectorList": []},
    {"recruitNoticeSn": 2, "recruitNoticeName": "상시 인재풀", "companyCategory": "HD현대마린솔루션", "isInProgress": True,
     "receiveStartDatetime": "2026-01-01 00:00:00", "receiveEndDatetime": "2100-12-31 00:00:59",
     "recruitSectorList": [{"job": "경영지원/IT", "jobDetail": "", "area": "경력"}]},
]}


def test_hd_hyundai_keeps_only_postings_inside_the_application_period():
    ps = hd_hyundai.parse_list(HD, "hd", datetime(2026, 11, 22, 16, 0))
    assert [p.external_id for p in ps] == ["271656", "2"]   # isInProgress 는 전부 true 라 기간으로 가린다
    p = ps[0]
    assert p.url == "https://recruit.hd.com/kr/mainLayout/applyDetail/271656" and p.end_at == datetime(2026, 11, 30, 14, 0, 59)
    assert p.job_text == "AI - 자율 작업 인지 기술 개발\nAI - 자율작업/주행 E2E 학습 알고리즘 개발"
    assert p.location_raw == "분당(GRC)" and categorize_row(p) == ["ai"]
    assert ps[1].end_at is None and ps[1].job_text == "경영지원/IT" and categorize_row(ps[1]) == []


# --- 한화 -------------------------------------------------------------------------
HANWHA_LIST = {"data": {"totalCount": 2, "hasNext": False, "list": [
    {"sdNm": "한화생명", "rtNm": "[한화생명] 데이터전략팀 'Data Scientist' 경력채용 (대리~과장)", "rtSeq": 20213,
     "rtAcptStrtDttm": "2026.11.18 15:00", "rtAcptEndDttm": "2026.12.02 15:00", "tagList": []},
    {"sdNm": "한화시스템/ICT", "rtNm": "[한화시스템/ICT] AI 인재Pool 등록", "rtSeq": 17596,
     "rtAcptStrtDttm": "2026.01.02 09:00", "rtAcptEndDttm": "2029.12.31 00:00"},
]}}
HANWHA_DETAIL = {"data": {"item": {
    "rtNrcrtYn": "N", "rtCarrYn": "Y", "rtIntnYn": "N", "rtPermanentWorkYn": "Y", "rtTempWorkYn": "N",
    "unitDt": [{"ruNm": "Data Scientist", "ruDtlJob": "■ 직무개요 ...", "ruWorkpl": "본사(서울 63빌딩)", "ruInqr": "문의처"}]}}}


def test_hanwha_list_and_detail():
    ps, has_next = hanwha.parse_list(HANWHA_LIST, "hanwha")
    assert not has_next and [p.external_id for p in ps] == ["20213", "17596"]
    p = ps[0]
    assert p.company == "한화생명" and p.url == "https://www.hanwhain.com/portal/apply/recruit/detail?rtSeq=20213"
    assert p.end_at == datetime(2026, 12, 2, 15, 0) and categorize_row(p) == ["ai"]
    assert ps[1].end_at is None   # 인재풀 공고의 먼 마감일은 '상시'로 본다
    assert hanwha.apply_detail(p, HANWHA_DETAIL) == "Data Scientist: 본사(서울 63빌딩)"
    assert p.career_type == "경력" and p.employment_type == "정규" and p.job_text == "Data Scientist"


# --- 네이버 -----------------------------------------------------------------------
NAVER = {"result": "Y", "totalSize": 37, "list": [
    {"annoId": 30005739, "sysCompanyCdNm": "NAVER WEBTOON", "annoSubject": "[네이버웹툰] AI Engineer (체험형 인턴)",
     "entTypeCdNm": "신입", "empTypeCdNm": "인턴", "workAreaCd": "0010", "staYmdTime": "2026.11.20 10:00:00",
     "endYmdTime": "2026.12.13 23:59:00", "classCdNm": "Service & Business", "subJobCdNm": "Product Development"},
    {"annoId": 30005455, "sysCompanyCdNm": "NAVER", "annoSubject": "[NAVER] 네이버쇼핑 부문별 운영 담당자 (계약)",
     "entTypeCdNm": "무관", "empTypeCdNm": "계약", "workAreaCd": "0020", "staYmdTime": "2026.11.01 10:00:00",
     "endYmdTime": "2999.12.31 23:59:00", "subJobCdNm": "Business Development"},
]}


def test_naver_parse_list():
    ps, total = naver.parse_list(NAVER, "naver")
    assert total == 37
    p = ps[0]
    assert p.company == "네이버웹툰" and p.external_id == "30005739" and p.url.endswith("view.do?annoId=30005739&lang=ko")
    assert p.end_at == datetime(2026, 12, 13, 23, 59) and p.career_type == "신입" and p.employment_type == "인턴"
    assert p.location_raw == "분당" and categorize_row(p) == ["ai"]
    assert ps[1].company == "네이버" and ps[1].end_at is None and ps[1].location_raw == "서울"


# --- 카카오 -----------------------------------------------------------------------
KAKAO = {"totalJobCount": 2, "totalPage": 3, "jobList": [
    {"realId": "P-14324", "jobOfferTitle": "Data Scientist (경력)", "regDate": "2025-12-04T19:11:36", "endDate": None,
     "closeFlag": False, "introduction": "본문은 읽지 않는다", "companyName": "카카오", "locationName": "판교",
     "employeeTypeName": "정규직", "skillSetList": [{"skillSetType": "Algorithm_ML", "skillSetName": "Algorithm/ML"}]},
    {"realId": "S-4788", "jobOfferTitle": "[공동체] 카카오페이 데이터 엔지니어 - 데이터 플랫폼 &amp; 분석", "regDate": "2026-10-01T10:00:00",
     "endDate": "2026-12-01T18:00:00", "closeFlag": False, "companyName": "카카오페이", "locationName": "", "skillSetList": []},
]}


def test_kakao_parse_list():
    ps, pages = kakao.parse_list(KAKAO, "kakao")
    assert pages == 3
    p = ps[0]
    assert p.external_id == "P-14324" and p.url == "https://careers.kakao.com/jobs/P-14324"
    assert p.career_type == "경력" and p.employment_type == "정규직" and p.location_raw == "판교" and p.end_at is None
    assert p.start_at == datetime(2025, 12, 4, 19, 11, 36) and categorize_row(p) == ["ai"]
    q = ps[1]
    assert q.company == "카카오페이" and q.title.endswith("데이터 플랫폼 & 분석") and q.end_at == datetime(2026, 12, 1, 18, 0)
    assert q.location_raw is None and categorize_row(q) == ["ai"]


# --- KT ---------------------------------------------------------------------------
KT = {"isSuccess": True, "data": [
    {"recruitNoticeSn": 259303, "company": "kt netcore", "title": "경력직 상시 인재풀(선로운용/AI서비스개발)",
     "recruitSectorList": [{"recruitSectorName": "선로운용-서울"}, {"recruitSectorName": "AI서비스개발-서울(수서)"}],
     "recruitTypeName": "상시", "recruitClassName": "경력", "receiveStartDatetime": "2026-08-21 16:00:00",
     "receiveEndDatetime": "2027-12-31 23:59:59", "isInTime": True, "isTimeBefore": False, "submittedResumeCount": 143},
    {"recruitNoticeSn": 1, "company": "KT", "title": "접수가 끝나고 전형 중인 공고", "recruitSectorList": [],
     "receiveEndDatetime": "2026-11-01 23:59:59", "isInTime": False, "isTimeBefore": False, "isInProgress": True},
    {"recruitNoticeSn": 2, "company": " initech ", "title": "접수 예정 공고", "recruitSectorList": [],
     "receiveStartDatetime": "2026-12-01 09:00:00", "receiveEndDatetime": "2026-12-10 23:59:59", "isInTime": False, "isTimeBefore": True},
]}


def test_kt_parse_list_uses_in_time_not_in_progress():
    ps = kt.parse_list(KT, "kt")
    assert [p.external_id for p in ps] == ["259303", "2"]
    p = ps[0]
    assert p.company == "kt netcore" and p.url == "https://recruit.kt.com/careers/259303" and p.status == "접수중"
    assert p.job_text == "선로운용-서울\nAI서비스개발-서울(수서)" and p.location_raw == p.job_text
    assert categorize_row(p) == ["ai"]
    assert ps[1].company == "initech" and ps[1].status == "접수예정"


# --- careerlink (KB국민카드·KB국민은행) --------------------------------------------
CAREERLINK = {"code": "0000", "data": {"rcrtList": [
    {"rcrtNo": "RC20261103038735", "coNm": "KB국민카드", "rcrtNm": "보훈제한채용(상품판매 모니터링 등 업무지원)",
     "rcrtCntn": "<p><img src='x.png'></p>", "hireTypeGbcdNm": "계약직", "carrTypeGbcdNm": "무관", "rcrtStatGbcd": "02",
     "rcrtAcptStrtDtm": "2026-11-03 13:45:00", "rcrtAcptEndDtm": "2026-11-25 23:59:59", "apltPossYn": "Y",
     "rcrtJobInfList": [{"jobNm": "금융상품 모니터링", "jobNmPath": "업무지원 > 금융상품 모니터링"}], "etcInf1": "서울 종로구 근무"},
    {"rcrtNo": "RC20260828033774", "coNm": "KB국민은행", "rcrtNm": "2026년 하반기 신입행원(L1) 「AI·플랫폼개발」부문 채용",
     "hireTypeGbcdNm": "정규직", "carrTypeGbcdNm": "신입", "rcrtStatGbcd": "03", "rcrtAcptEndDtm": "2026-09-09 18:00:59",
     "rcrtJobInfList": [{"jobNm": "AI·플랫폼개발", "jobNmPath": "L1 > AI·플랫폼개발"}], "etcInf1": ""},
]}}


def test_careerlink_parse_list():
    ps = careerlink.parse_list(CAREERLINK, "kbcard", "KB국민카드", "https://kbcard.careerlink.kr")
    p = ps[0]
    assert p.external_id == "RC20261103038735" and p.url == "https://kbcard.careerlink.kr/jobs/RC20261103038735"
    assert p.status == "접수중" and p.end_at == datetime(2026, 11, 25, 23, 59, 59)
    assert p.career_type == "무관" and p.employment_type == "계약직" and p.location_raw == "서울 종로구 근무"
    assert p.job_text == "업무지원 > 금융상품 모니터링" and categorize_row(p) == ["card"]   # 카드사는 직무와 상관없이 전부
    q = ps[1]
    assert q.status == "접수마감" and q.location_raw is None and categorize_row(q) == ["ai"]
