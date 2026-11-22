"""실행 흐름(collect·notify) 테스트. 네트워크 없이 가짜 소스로 돌린다."""
import argparse
import dataclasses
from datetime import datetime, timezone

from radar import __main__ as main
from radar.config import load_settings
from radar.db import Database
from radar.models import Posting
from radar.sources.base import Source

NOW = datetime.now(timezone.utc)
FAR = datetime(2999, 1, 1)


class FakeSource(Source):
    key, company, site_url = "fake", "가짜", "https://example.com"

    def __init__(self, postings, detail_for_classify=False, details=None):
        self.postings = postings
        self.detail_for_classify = detail_for_classify
        self.details = details or {}
        self.detail_calls = []

    def fetch_list(self, f):
        return [p.model_copy() for p in self.postings]

    def fetch_detail(self, f, posting):
        self.detail_calls.append(posting.external_id)
        job_text, location = self.details.get(posting.external_id, (None, None))
        if job_text is not None:
            posting.job_text = job_text
        return location


def P(i, company, title, **kw):
    kw.setdefault("end_at", FAR)
    kw.setdefault("status", "접수중")
    return Posting(source="fake", external_id=str(i), company=company, title=title, url=f"https://x/{i}", **kw)


def ids(db):
    return {r["external_id"] for r in db.all_postings()}


def with_telegram():
    return dataclasses.replace(load_settings(), telegram_token="T", telegram_chat_id="C")


def test_only_relevant_open_postings_are_stored(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    src = FakeSource([
        P(1, "네이버", "AI Research Engineer"),
        P(2, "네이버", "총무 담당"),                                      # 관심 분야 아님 → 저장 안 함
        P(3, "롯데카드", "채권 관리"),                                    # 카드사는 전부
        P(4, "네이버", "ML Engineer", end_at=datetime(2020, 1, 1)),      # 처음 봤는데 이미 마감 → 저장 안 함
        P(5, "네이버", "Data Scientist", status="접수마감"),
    ], details={"1": (None, "근무지: 경기도 성남시")})
    fetched, new = main.collect(src, None, db, load_settings(), NOW)
    assert (fetched, new) == (5, 2) and ids(db) == {"1", "3"}
    assert src.detail_calls == ["1", "3"]                               # 저장할 공고만 상세 조회
    row = next(r for r in db.all_postings() if r["external_id"] == "1")
    assert row["regions"][0]["sigungu"] == "성남시"


def test_new_source_does_not_alert_existing_postings(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    src = FakeSource([P(1, "네이버", "AI Engineer")])
    rid = db.start_run(src.key)
    main.collect(src, None, db, load_settings(), NOW)                   # 첫 수집: 이미 올라와 있던 공고
    db.finish_run(rid, 1, 1)
    assert db.unnotified() == []
    src.postings.append(P(2, "네이버", "LLM Engineer"))
    main.collect(src, None, db, load_settings(), NOW)                   # 두 번째 수집부터는 새 공고만 알림 대상
    assert [r["external_id"] for r in db.unnotified()] == ["2"]
    assert src.detail_calls == ["1", "2"]                               # 아는 공고는 상세를 다시 조회하지 않는다


def test_bundle_source_classifies_from_detail_and_backfills(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    details = {"1": ("AI Data Engineer\n경영기획", "서울 서초구"), "2": ("보건관리자", "경기 성남시")}
    src = FakeSource([P(1, "삼성화재", "경력사원 채용(IT, 경영기획)"), P(2, "삼성중공업", "경력사원 채용(보건관리자)")],
                     detail_for_classify=True, details=details)
    db.finish_run(db.start_run(src.key), 0, 0)                          # 기존 소스로 취급
    _, new = main.collect(src, None, db, load_settings(), NOW)
    assert new == 1 and ids(db) == {"1", "2"}                           # 관심 밖 공고도 저장해 상세 재조회를 막는다
    main.collect(src, None, db, load_settings(), NOW)
    assert src.detail_calls == ["1", "2"]
    # 직무명을 모르는 예전 행(job_text NULL)은 다음 수집에서 한 번 보충한다
    db.conn.execute("UPDATE postings SET job_text = NULL WHERE external_id = '2'")
    main.collect(src, None, db, load_settings(), NOW)
    main.collect(src, None, db, load_settings(), NOW)
    assert src.detail_calls == ["1", "2", "2"]


def test_list_level_location_does_not_overwrite_detail_location(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    src = FakeSource([P(1, "LG전자", "AI Engineer", location_raw="서울특별시")], details={"1": (None, "서울특별시\n마곡")})
    main.collect(src, None, db, load_settings(), NOW)
    main.collect(src, None, db, load_settings(), NOW)                   # 두 번째 수집은 목록의 시·도만 들고 온다
    assert db.all_postings()[0]["location_raw"] == "서울특별시\n마곡"


def test_detail_failure_does_not_lose_the_posting(tmp_path):
    db = Database(tmp_path / "t.sqlite")

    class Broken(FakeSource):
        def fetch_detail(self, f, posting):
            raise RuntimeError("상세 페이지 오류")

    src = Broken([P(1, "네이버", "AI Engineer")])
    fetched, new = main.collect(src, None, db, load_settings(), NOW)
    assert (fetched, new) == (1, 1) and ids(db) == {"1"}


def test_notify_sends_only_relevant_open_rows(tmp_path, monkeypatch):
    db = Database(tmp_path / "t.sqlite")
    db.upsert(P(1, "네이버", "AI Engineer"))
    db.upsert(P(2, "삼성중공업", "경력사원 채용(보건관리자)", job_text="보건관리자"))   # 관심 밖: 보내지 않고 남겨 둔다
    db.upsert(P(3, "롯데카드", "채권 관리", end_at=datetime(2020, 1, 1)))              # 이미 마감: 보내지 않고 확인 처리
    sent = []
    monkeypatch.setattr(main, "check_telegram", lambda token, chat: None)
    monkeypatch.setattr(main, "send_telegram", lambda token, chat, text: sent.append(text))
    args = argparse.Namespace(bootstrap=False, no_notify=False)
    assert main.notify(db, with_telegram(), args, NOW) is True
    assert len(sent) == 1 and "AI Engineer" in sent[0] and "보건관리자" not in sent[0] and "채권" not in sent[0]
    assert [r["external_id"] for r in db.unnotified()] == ["2"]


def test_notify_failure_is_reported_not_raised(tmp_path, monkeypatch):
    db = Database(tmp_path / "t.sqlite")
    db.upsert(P(1, "네이버", "AI Engineer"))

    def must_not_send(*a):
        raise AssertionError("설정이 틀렸으면 보내지 않는다")

    monkeypatch.setattr(main, "check_telegram", lambda token, chat: "Unauthorized → 봇 토큰이 틀렸습니다.")
    monkeypatch.setattr(main, "send_telegram", must_not_send)
    assert main.notify(db, with_telegram(), argparse.Namespace(bootstrap=False, no_notify=False), NOW) is False
    assert "Unauthorized" in db.get_meta("telegram")
    assert len(db.unnotified()) == 1                                    # 다음 실행에서 다시 시도한다
