from radar.sources.lg_careers import location_text_from_detail, parse_list

LIST = {"data": {"jobNoticeList": [
    {"jobNoticeId": 1001889, "careerTypeName": "경력", "recruitTypeName": "수시", "companyName": "LG유플러스",
     "jobNoticeName": "[정보보안센터] AI보안 담당자 경력채용", "recEndDateTime": "2026.11.08 23:00",
     "noticeStatus": "POSTING", "recAvail": 1, "workLocationName": "서울특별시"},
    {"jobNoticeId": 2, "companyName": "LG전자", "jobNoticeName": "저장됨", "noticeStatus": "SAVED", "recAvail": 1},
]}}


def test_parse_list():
    ps = parse_list(LIST, "lg")
    assert len(ps) == 1
    p = ps[0]
    assert p.id == "lg:1001889" and p.url == "https://careers.lg.com/apply/detail?id=1001889"
    assert p.end_at.day == 8 and p.end_at.hour == 23 and p.status == "접수중"
    assert p.career_type == "경력" and p.employment_type == "수시" and p.location_raw == "서울특별시"


def test_location_text_from_detail():
    detail = {"data": {"jobNoticesDetail": {
        "jobNoticesDetail": {"workLocation": "가산, 창원, 마곡"},
        "recList": [{"orgName": "CTO", "jobGroupName": "BMS SW", "locationName": "대전"}, {"orgName": "X", "locationName": ""}],
    }}}
    assert location_text_from_detail("경기도", detail) == "경기도\n가산, 창원, 마곡\nBMS SW: 대전"
    assert location_text_from_detail(None, {"data": {}}) is None
