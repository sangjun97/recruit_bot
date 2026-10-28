from radar.db import Database
from radar.models import Posting, Region
from radar.notify import build_messages, format_posting


def make(i, **kw):
    kw.setdefault("title", f"공고 {i}")
    return Posting(source="t", external_id=str(i), company="테스트사", url=f"https://x/{i}", **kw)


def test_upsert_detects_new_and_keeps_regions(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    assert db.upsert(make(1)) is True
    assert db.upsert(make(1, status="접수마감")) is False
    db.set_regions("t:1", "근무지: 이천", [Region(sido="경기도", sigungu="이천시", method="rule")])
    db.upsert(make(1, status="접수마감"))  # regions 없는 재수집이 기존 regions 를 지우지 않아야 한다
    rows = db.all_postings()
    assert rows[0]["status"] == "접수마감" and rows[0]["regions"][0]["sigungu"] == "이천시"
    assert len(db.unnotified()) == 1
    db.mark_notified(["t:1"])
    assert db.unnotified() == []


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
