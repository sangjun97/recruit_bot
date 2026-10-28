from radar.sources.recruiter_co_kr import parse_items

SAMPLE = [
    {"positionSn": 131472, "title": "[현대카드] AI Engineer_개인화", "submissionStatus": "IN_SUBMISSION",
     "startDateTime": "2026-10-16T12:00:00", "endDateTime": "2026-10-30T12:00:59",
     "tagList": [{"tagSn": 7622, "tagName": "경력"}], "careerType": "CAREER", "classificationCode": "경력"},
    {"positionSn": 1, "title": "신입", "submissionStatus": "POST_SUBMISSION", "careerType": "NEW", "tagList": []},
    {"title": "sn 없음"},
]


def test_parse_items():
    ps = parse_items(SAMPLE, "careerhyundai", "hyundaicard", "현대카드")
    assert len(ps) == 2
    p = ps[0]
    assert p.id == "hyundaicard:131472"
    assert p.url == "https://careerhyundai.recruiter.co.kr/career/jobs/131472"
    assert p.status == "접수중" and p.career_type == "경력" and p.employment_type == "경력"
    assert p.start_at.year == 2026 and p.end_at.hour == 12
    assert ps[1].status == "접수마감" and ps[1].career_type == "신입" and ps[1].start_at is None
