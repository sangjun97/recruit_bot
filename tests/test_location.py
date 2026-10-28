from radar.location import load_region_dict, pick_location_lines


def ext(text):
    return sorted((r.sido, r.sigungu, r.method) for r in load_region_dict().extract(text))


def test_alias_station():
    assert ext("근무 장소 : 현대카드 본사 (국회의사당역 현대카드 빌딩)") == [("서울특별시", "영등포구", "alias")]


def test_sido_sigungu_plain():
    assert ext("근무지: 경기도 이천시") == [("경기도", "이천시", "rule")]


def test_multiple_sites():
    got = ext("근무지: 평택/화성/기흥 중 배치")
    assert ("경기도", "평택시", "rule") in got or ("경기도", "평택시", "alias") in got
    assert ("경기도", "화성시", "rule") in got
    assert ("경기도", "용인시", "alias") in got


def test_ambiguous_gu_needs_hint():
    # 중구는 여러 시·도에 있으므로 힌트 없이는 추출하지 않는다
    assert ext("근무지: 중구") == []
    assert ext("근무지: 대전 중구") == [("대전광역시", "중구", "rule")]


def test_gwangju_disambiguation():
    assert ext("근무지: 경기 광주시") == [("경기도", "광주시", "rule")]
    assert ext("근무지: 광주광역시 광산구") == [("광주광역시", "광산구", "rule")]


def test_longest_match_wins():
    assert ext("서울 강남구 테헤란로") == [("서울특별시", "강남구", "alias")] or ext("서울 강남구") == [("서울특별시", "강남구", "rule")]


def test_sido_only():
    assert ext("근무지: 서울 본사") == [("서울특별시", None, "rule")]


def test_no_false_positive_on_university():
    assert ext("서울대학교 출신 우대") == []


def test_pick_location_lines():
    text = "[주요 업무]\n- 모델 개발\n\n[근무 조건]\n- 고용 형태 : 정규직\n- 근무 장소 : 현대카드 본사\n[혜택]\n- 의료비"
    assert pick_location_lines(text) == "- 근무 장소 : 현대카드 본사"
    assert pick_location_lines("아무 내용 없음") is None
