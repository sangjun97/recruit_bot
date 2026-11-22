from datetime import datetime

from radar.db import Database
from radar.models import Posting, Region
from radar.notify import build_messages, format_posting


def make(i, **kw):
    kw.setdefault("title", f"공고 {i}")
    return Posting(source="t", external_id=str(i), company="테스트사", url=f"https://x/{i}", **kw)


def test_upsert_detects_new_and_keeps_detail_fields(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    first = make(1, job_text="AI Engineer", location_raw="근무지: 이천",
                 regions=[Region(sido="경기도", sigungu="이천시", method="rule")], start_at=datetime(2026, 11, 1, 9, 0))
    assert db.upsert(first) is True
    # 목록만 다시 본 재수집(상세 필드 없음)이 상세에서 받은 값을 지우지 않아야 한다
    assert db.upsert(make(1, status="접수마감")) is False
    row = db.all_postings()[0]
    assert row["status"] == "접수마감" and row["regions"][0]["sigungu"] == "이천시"
    assert row["job_text"] == "AI Engineer" and row["location_raw"] == "근무지: 이천" and row["start_at"] == "2026-11-01T09:00"
    assert len(db.unnotified()) == 1
    db.mark_notified(["t:1"])
    assert db.unnotified() == []


def test_date_only_list_does_not_overwrite_precise_deadline(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    db.upsert(make(1, end_at=datetime(2026, 11, 30, 17, 0)))                           # 상세에서 받은 실제 마감 17:00
    db.upsert(make(1, end_at=datetime(2026, 11, 30, 23, 59), end_date_only=True))      # 목록은 날짜만 → 23:59 추정
    assert db.all_postings()[0]["end_at"] == "2026-11-30T17:00"
    db.upsert(make(1, end_at=datetime(2026, 12, 7, 23, 59), end_date_only=True))       # 마감일이 연장되면 반영
    assert db.all_postings()[0]["end_at"] == "2026-12-07T23:59"


def test_migrates_old_database(tmp_path):
    import sqlite3
    path = tmp_path / "old.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE postings (id TEXT PRIMARY KEY, source TEXT NOT NULL, external_id TEXT NOT NULL,
        company TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL, start_at TEXT, end_at TEXT, career_type TEXT,
        employment_type TEXT, status TEXT, location_raw TEXT, regions_json TEXT NOT NULL DEFAULT '[]',
        first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, notified_at TEXT)""")
    conn.execute("INSERT INTO postings (id, source, external_id, company, title, url, first_seen, last_seen) "
                 "VALUES ('t:1','t','1','c','제목','u','2026-10-28T00:00:00+00:00','2026-10-28T00:00:00+00:00')")
    conn.commit()
    conn.close()
    db = Database(path)
    assert db.known("t")["t:1"]["job_text"] is None
    assert db.all_postings()[0]["title"] == "제목"


def test_runs_and_meta(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    assert db.has_successful_run("a") is False
    rid = db.start_run("a")
    db.finish_run(rid, 3, 1, error="Boom")
    assert db.has_successful_run("a") is False and db.last_runs()["a"]["error"] == "Boom"
    rid = db.start_run("a")
    db.finish_run(rid, 5, 0)
    last = db.last_runs()["a"]
    assert db.has_successful_run("a") and last["fetched"] == 5 and last["error"] is None and last["last_ok"]
    for _ in range(10):
        db.finish_run(db.start_run("b"), 0, 0)
    db.prune_runs(keep=4)
    assert db.conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 4
    assert db.get_meta("k") is None
    db.set_meta("k", "v1")
    db.set_meta("k", "v2")
    assert db.get_meta("k") == "v2"


def test_build_messages_splits_long_lists(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    for i in range(60):
        db.upsert(make(i, title="아주 긴 제목 " * 10))
    msgs = build_messages(db.unnotified())
    assert len(msgs) >= 2
    assert all(len(m) <= 4096 for m in msgs)
    assert msgs[0].startswith("🔔 새 채용 공고 60건")


def test_format_posting_escapes_html():
    txt = format_posting({"company": "A<B", "title": "x & y", "url": "https://x/1", "regions": []})
    assert "A&lt;B" in txt and "x &amp; y" in txt and "근무지 미확인" in txt


def test_format_posting_shows_category_and_bundle_roles():
    row = {"company": "삼성카드", "title": "경력사원 채용(IT, 마케팅)", "url": "https://x/1",
           "job_text": "AI Data Engineer\n마케팅 기획", "regions": [{"sido": "서울특별시", "sigungu": "중구"}]}
    txt = format_posting(row)
    assert txt.startswith("[AI·데이터] [카드사] <b>삼성카드</b>")
    assert "🤖 AI Data Engineer" in txt and "마케팅 기획" not in txt and "서울특별시 중구" in txt
    many = [{"sido": "경기도", "sigungu": s} for s in ("수원시", "용인시", "화성시", "평택시", "이천시")]
    assert "📍 경기도\n" in format_posting({"company": "c", "title": "AI", "url": "u", "regions": many, "end_at": "2026-12-01T10:00"})
