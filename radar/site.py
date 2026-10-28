"""수집한 공고를 정적 HTML 한 장으로 만든다. 지역·회사·상태 필터는 브라우저 측 JS가 처리한다."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .db import Database

TEMPLATES = Path(__file__).parent / "templates"
KST = timezone(timedelta(hours=9))


OPEN_STATUSES = (None, "접수중", "접수예정")


def visible_postings(postings: list[dict], now_utc: datetime, hide_after_days: int) -> list[dict]:
    """마감 상태를 계산하고, 마감 후 hide_after_days 가 지난 공고는 뺀다. 입력 dict 의 status 를 갱신한다."""
    now_kst = (now_utc.astimezone(KST)).replace(tzinfo=None)
    hide_cut_end = (now_kst - timedelta(days=hide_after_days)).isoformat(timespec="minutes")
    hide_cut_seen = (now_utc - timedelta(days=hide_after_days)).isoformat(timespec="seconds")
    vanished_cut = (now_utc - timedelta(days=1)).isoformat(timespec="seconds")
    now_iso = now_kst.isoformat(timespec="minutes")
    out = []
    for p in postings:
        end_at, last_seen = p.get("end_at"), p.get("last_seen") or ""
        # 마감일이 지났거나, 하루 넘게 공고 목록에서 사라졌으면 마감으로 본다
        if p.get("status") in OPEN_STATUSES and ((end_at and end_at < now_iso) or (last_seen and last_seen < vanished_cut)):
            p["status"] = "접수마감"
        if end_at:
            if end_at < hide_cut_end:
                continue
        elif last_seen and last_seen < hide_cut_seen:
            continue
        out.append(p)
    return out


def build_site(db: Database, out_dir: Path, hide_after_days: int = 7) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    postings = visible_postings(db.all_postings(), datetime.now(timezone.utc), hide_after_days)
    # 사이트에는 공고 본문을 싣지 않는다. 제목·기간·근무지·원문 링크만 담는다.
    public = [
        {
            "id": p["id"], "company": p["company"], "title": p["title"], "url": p["url"],
            "start_at": p["start_at"], "end_at": p["end_at"], "career_type": p["career_type"],
            "employment_type": p["employment_type"], "status": p["status"],
            "regions": [{"sido": r["sido"], "sigungu": r.get("sigungu")} for r in p["regions"]],
            "first_seen": p["first_seen"],
        }
        for p in postings
    ]
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
    tpl = env.get_template("index.html")
    html = tpl.render(
        postings_json=json.dumps(public, ensure_ascii=False).replace("</", "<\\/"),
        generated_at=datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        count=len(public),
    )
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / "postings.json").write_text(json.dumps(public, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    return out_dir / "index.html"
