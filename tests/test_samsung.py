from radar.sources.samsung_careers import SamsungCareersSource, apply_detail, location_text_from_detail, parse_list_html

LIST_HTML = """
<input type="hidden" class="divCnt" data-value="4" data-max="2">
<li><div><div>
  <a href="/#none" data-value="23,386">
    <p class="company">  삼성E&amp;A</p>
    <h3 class="title">경력사원 채용(연구개발, 분석) </h3>
    <p class="info"><span> 경력 </span><span class="period"> 2026.10.28 ~ 2026.11.10 </span></p>
  </a></div></div></li>
<li><a href="/#none" data-value="23,364"><p class="company">에스원</p><h3 class="title">경력사원 채용(안전관리자)</h3><p class="info"><span>경력</span></p></a></li>
"""


def test_parse_list_html():
    ps, pages = parse_list_html(LIST_HTML, "samsung")
    assert pages == 2 and len(ps) == 2
    p = ps[0]
    assert p.id == "samsung:23386" and p.company == "삼성E&A" and p.url.endswith("/hr/?no=23386")
    assert p.title == "경력사원 채용(연구개발, 분석)" and p.career_type == "경력" and p.status == "접수중"
    assert p.start_at.month == 10 and p.end_at.day == 10 and p.end_at.hour == 23 and p.end_date_only
    assert ps[1].start_at is None and ps[1].career_type == "경력"


def test_location_text_from_detail():
    data = {"data": {"items": [
        {"titleKr": "연구개발 (촉매)", "workPlaceKr": "- 서울 강동구 및 당사 연구소"},
        {"titleKr": "안전관리자(수원/고창)", "workPlaceKr": "<p>수원, 고창</p>"},
        {"titleKr": "빈 직무", "workPlaceKr": ""},
    ], "result": {}}}
    assert location_text_from_detail(data) == "연구개발 (촉매): - 서울 강동구 및 당사 연구소\n안전관리자(수원/고창): 수원, 고창"
    fallback = {"data": {"items": [], "result": {"etcKr": "<p>지원 안내</p><p>근무지: 경기 평택</p>"}}}
    assert location_text_from_detail(fallback) == "근무지: 경기 평택"
    assert location_text_from_detail({"data": {"items": [], "result": {}}}) is None


def test_apply_detail_sets_precise_period_and_job_names():
    ps, _ = parse_list_html(LIST_HTML, "samsung")
    p = ps[0]
    apply_detail(p, {"data": {"result": {"startdate": "202610280900", "enddate": "202611101700"}, "items": [
        {"titleKr": "AI Data Engineer"}, {"titleKr": " 경영기획 "}, {"titleKr": "AI Data Engineer"}, {"titleKr": ""}]}})
    assert p.end_at.hour == 17 and p.end_at.minute == 0 and not p.end_date_only and p.start_at.hour == 9
    assert p.job_text == "AI Data Engineer\n경영기획"


def test_company_scope_keeps_majors_and_card_company():
    from radar.models import Posting

    src = SamsungCareersSource()
    names = ["삼성전자 DX부문", "삼성카드", "삼성E&A", "삼성문화재단", "삼성전자서비스"]
    ps = [Posting(source="samsung", external_id=str(i), company=n, title="t", url="u") for i, n in enumerate(names)]
    kept = src.scope(ps, src.companies)
    assert [p.company for p in kept] == ["삼성전자 DX부문", "삼성카드", "삼성E&A"]
    assert dict(src.skipped_companies) == {"삼성문화재단": 1, "삼성전자서비스": 1}
