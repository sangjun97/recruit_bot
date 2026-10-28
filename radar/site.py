"""수집한 공고를 정적 HTML 한 장으로 만든다. 지역·회사·상태 필터는 브라우저 측 JS가 처리한다."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .db import Database

TEMPLATES = Path(__file__).parent / "templates"
KST = timezone(timedelta(hours=9))


def build_site(db: Database, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    postings = db.all_postings()
    now = datetime.now(KST).replace(tzinfo=None).isoformat(timespec="minutes")
    for p in postings:
        # 목록에서 사라진 뒤에도 DB에는 남으므로, 마감일이 지난 공고는 화면에서 마감으로 표시한다
        if p.get("end_at") and p["end_at"] < now and p.get("status") in (None, "접수중", "접수예정"):
            p["status"] = "접수마감"
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
