import json
import re
from datetime import datetime, timezone

from radar.db import Database
from radar.models import Posting, Region
from radar.site import build_site, public_posting, visible_postings
from radar.status import effective_status, is_open

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


def test_effective_status_uses_kst_deadline():
    # NOW 는 KST 12:00. 같은 날 11:59 마감은 지났고 12:01 마감은 아직이다
    assert effective_status(row(end_at="2026-10-29T11:59"), NOW) == "접수마감"
    assert is_open(row(end_at="2026-10-29T12:01"), NOW)
    assert not is_open(row(status="접수마감", end_at="2026-12-01T00:00"), NOW)


def test_purge_closed(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    db.upsert(Posting(source="t", external_id="old", company="c", title="t", url="u", end_at=datetime(2020, 1, 1)))
    db.upsert(Posting(source="t", external_id="new", company="c", title="t", url="u", end_at=datetime(2999, 1, 1)))
    db.upsert(Posting(source="t", external_id="noend", company="c", title="t", url="u"))
    assert db.purge_closed(90) == 1
    assert {r["external_id"] for r in db.all_postings()} == {"new", "noend"}


def test_public_posting_categories_and_roles():
    base = {"id": "s:1", "url": "u", "start_at": None, "end_at": None, "career_type": "경력", "employment_type": None,
            "status": "접수중", "regions": [], "first_seen": "2026-10-28T00:00:00+00:00"}
    bundle = public_posting({**base, "company": "삼성화재", "title": "경력사원 채용(AI, IT, 경영기획)",
                             "job_text": "AI Data Engineer\n경영기획"})
    assert bundle["cats"] == ["ai"] and bundle["roles"] == [] and bundle["open"] is True   # 제목에 이미 AI 가 있으면 직무명 생략
    hidden = public_posting({**base, "company": "삼성디스플레이", "title": "경력사원 채용(연구개발, 품질)",
                             "job_text": "설계\nSW/AI/Automation"})
    assert hidden["cats"] == ["ai"] and hidden["roles"] == ["SW/AI/Automation"]
    assert public_posting({**base, "company": "삼성중공업", "title": "경력사원 채용(보건관리자)", "job_text": "보건관리자"})["cats"] == []


class FakeSource:
    key, company, site_url = "t", "테스트 채용", "https://example.com/jobs"


def test_build_site_lists_only_relevant_postings(tmp_path):
    db = Database(tmp_path / "t.sqlite")
    far = datetime(2999, 1, 1)
    db.upsert(Posting(source="t", external_id="1", company="현대카드", title="[현대카드] 대손 충당금 관리", url="u1", end_at=far,
                      regions=[Region(sido="서울특별시", sigungu="영등포구", method="rule")]))
    db.upsert(Posting(source="t", external_id="2", company="LG전자", title="[CTO부문] AI Security 전문가 채용", url="u2", end_at=far))
    db.upsert(Posting(source="t", external_id="3", company="LG전자", title="구매 담당자 채용", url="u3", end_at=far))
    db.finish_run(db.start_run("t"), 3, 2)
    db.set_meta("telegram", json.dumps({"ok": False, "detail": "Unauthorized"}))
    out = build_site(db, tmp_path / "site", 7, [FakeSource()])
    html = out.read_text(encoding="utf-8")
    data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))
    assert {d["id"]: d["cats"] for d in data} == {"t:1": ["card"], "t:2": ["ai"]}
    assert "테스트 채용" in html and "3건" in html and "Unauthorized" in html
    assert "sigungu" in html and 'id="sigungu"' not in html   # 시·군·구 필터는 없앴다(표시용 데이터만 남김)
