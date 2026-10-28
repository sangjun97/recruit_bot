from datetime import datetime, timezone

from radar.db import Database
from radar.models import Posting
from radar.site import visible_postings

NOW = datetime(2026, 10, 29, 3, 0, tzinfo=timezone.utc)  # KST 12:00


def row(**kw):
    base = {"status": "접수중", "end_at": None, "last_seen": "2026-10-29T02:50:00+00:00"}
    base.update(kw)
    return base


def test_expired_marked_closed_but_still_visible_within_window():
    rows = [row(end_at="2026-10-27T18:00")]
    out = visible_postings(rows, NOW, hide_after_days=7)
    assert len(out) == 1 and out[0]["status"] == "접수마감"


def test_hidden_after_window():
    rows = [row(end_at="2026-10-20T18:00"), row(end_at="2026-10-23T12:00")]
    out = visible_postings(rows, NOW, hide_after_days=7)
    assert [r["end_at"] for r in out] == ["2026-10-23T12:00"]


def test_vanished_posting_without_end_date():
    fresh = row(last_seen="2026-10-28T20:00:00+00:00")           # 7시간 전에 봄 → 접수중 유지
    gone = row(last_seen="2026-10-27T00:00:00+00:00")            # 이틀 전 → 마감 표시
    old = row(last_seen="2026-10-10T00:00:00+00:00")             # 19일 전 → 숨김
    out = visible_postings([fresh, gone, old], NOW, hide_after_days=7)
    assert [r["status"] for r in out] == ["접수중", "접수마감"]


def test_purge_closed(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    db.upsert(Posting(source="t", external_id="old", company="c", title="t", url="u", end_at=datetime(2020, 1, 1)))
    db.upsert(Posting(source="t", external_id="new", company="c", title="t", url="u", end_at=datetime(2999, 1, 1)))
    db.upsert(Posting(source="t", external_id="noend", company="c", title="t", url="u"))
    assert db.purge_closed(90) == 1
    assert {r["external_id"] for r in db.all_postings()} == {"new", "noend"}
