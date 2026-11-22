from radar.categories import categorize_row
from radar.sources.sk_careers import location_text, parse_detail, parse_list

LIST = {"success": True, "totalCount": 3, "list": [
    {"jobNoticeNo": 6867, "noticeID": "R262415", "title": " 제조 AI · Data 분야 [Data Engineer / DevOps(k8s)] 전문가 영입 ",
     "jobRole": "Tech R&D/Data Engineering", "recruitType": "경력", "workingType": "정규", "workingArea": "경기/인천",
     "remainDay": 33, "corpName": "SK주식회사(AX)", "start": "2026년 11월 04일(수)", "end": "2026년 12월 25일(금)"},
    {"noticeID": "R262252", "title": "전사 통합 Image 솔루션 제공 플랫폼 Application PL 모집", "corpName": "SK주식회사(AX)",
     "jobRole": "IT/구축/운영/최적화 • Tech R&D/ML/DL 개발", "recruitType": "경력", "workingType": "계약",
     "workingArea": "서울", "remainDay": 5, "start": "2026년 11월 10일(화)", "end": "2026년 11월 27일(금)"},
    {"noticeID": "R262353", "title": "[SK케미칼] 의약품 생산공정관리 담당자 경력 모집", "corpName": "SK케미칼(LS)",
     "jobRole": "제조/생산관리", "recruitType": "경력", "workingType": "정규", "workingArea": "충청", "remainDay": 0,
     "start": "2026년 11월 09일(월)", "end": "2026년 11월 22일(일)"},
    {"title": "id 없음"},
]}

DETAIL = """
<div class="floating-box"><div class="box-inner"><h2 class="box-title">제목</h2><div class="box-detail">
 <div class="box-detail-item"><div class="label">지원 기간</div><div class="value"> 2026년 08월 20일(목)~2026년 08월 26일(수) </div></div>
 <div class="box-detail-item"><div class="label">마감 시간</div><div class="value"> 17:00 </div></div>
 <div class="box-detail-item"><div class="label">
직무   </div><div class="value">Tech R&amp;D - 설계</div></div>
 <div class="box-detail-item"><div class="label"></div><div class="value">Tech R&amp;D - AI Model</div></div>
 <div class="box-detail-item"><div class="label">지역</div><div class="value">경기/인천 - 이천/분당/서울</div></div>
 <div class="box-detail-item"><div class="label"></div><div class="value">충청 - 청주</div></div>
</div></div></div>
<div class="detail-content-box"><p>담당 업무는 다음과 같습니다.</p><p>우대 사항</p></div>
"""


def test_parse_list():
    ps = parse_list(LIST, "sk")
    assert [p.external_id for p in ps] == ["R262415", "R262252", "R262353"]
    p = ps[0]
    assert p.company == "SK주식회사(AX)" and p.title.startswith("제조 AI") and not p.title.endswith(" ")
    assert p.url == "https://www.skcareers.com/Recruit/Detail/R262415"
    assert (p.start_at.month, p.start_at.day) == (11, 4) and (p.end_at.day, p.end_at.hour, p.end_at.minute) == (25, 23, 59)
    assert p.end_date_only and p.career_type == "경력" and p.employment_type == "정규" and p.status == "접수중"
    assert p.job_text == "Tech R&D/Data Engineering" and p.location_raw == "경기/인천"
    # 제목에 키워드가 없어도 직무 분류로 AI·데이터 공고를 가린다
    assert ps[1].job_text == "IT/구축/운영/최적화\nTech R&D/ML/DL 개발"
    assert categorize_row(ps[1]) == ["ai"] and categorize_row(ps[2]) == []


def test_parse_detail_and_location():
    d = parse_detail(DETAIL)
    assert d["fields"]["마감 시간"] == ["17:00"]
    assert d["fields"]["직무"] == ["Tech R&D - 설계", "Tech R&D - AI Model"]
    assert d["fields"]["지역"] == ["경기/인천 - 이천/분당/서울", "충청 - 청주"]
    assert d["location_lines"] == []
    # 세부 지명이 있으면 넓은 권역 표기('경기/인천')는 넣지 않는다 → '인천'이 근무지로 잡히지 않는다
    assert location_text("경기/인천", d) == "이천/분당/서울\n청주"


def test_location_falls_back_to_broad_area():
    broad_only = {"fields": {"지역": ["경기/인천"]}, "location_lines": []}
    assert location_text("경기/인천", broad_only) == "경기/인천"
    with_body = {"fields": {"지역": ["경기/인천"]}, "location_lines": ["※ 근무지 : 경기도 분당"]}
    assert location_text("경기/인천", with_body) == "※ 근무지 : 경기도 분당"
    useless_body = {"fields": {"지역": ["서울"]}, "location_lines": ["근무지 우선순위를 선택해 주세요."]}
    assert location_text("서울", useless_body) == "서울\n근무지 우선순위를 선택해 주세요."
    assert location_text(None, {"fields": {}, "location_lines": []}) is None
