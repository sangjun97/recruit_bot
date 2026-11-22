"""수집한 공고를 정적 HTML 한 장으로 만든다. 분야(AI·데이터 / 카드사) 전환과 필터는 브라우저 측 JS가 처리한다."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .brands import brand_for, brand_table
from .categories import CATEGORY_LABELS, ai_keywords, ai_roles, categorize_row
from .db import Database
from .logos import existing_logos
from .status import KST, OPEN_STATUSES, effective_status, kst_naive

TEMPLATES = Path(__file__).parent / "templates"


def visible_postings(postings: list[dict], now_utc: datetime, hide_after_days: int) -> list[dict]:
    """마감 상태를 계산하고, 마감 후 hide_after_days 가 지난 공고는 뺀다. 입력 dict 의 status 를 갱신한다."""
    hide_cut_end = (kst_naive(now_utc) - timedelta(days=hide_after_days)).isoformat(timespec="minutes")
    hide_cut_seen = (now_utc - timedelta(days=hide_after_days)).isoformat(timespec="seconds")
    out = []
    for p in postings:
        end_at, last_seen = p.get("end_at"), p.get("last_seen") or ""
        # 마감일이 지났거나, 하루 넘게 공고 목록에서 사라졌으면 마감으로 본다
        p["status"] = effective_status(p, now_utc)
        if end_at:
            if end_at < hide_cut_end:
                continue
        elif last_seen and last_seen < hide_cut_seen:
            continue
        out.append(p)
    return out


def public_posting(p: dict) -> dict:
    """사이트에 싣는 필드만 고른다. 공고 본문은 싣지 않는다(제목·기간·직무명·근무지·원문 링크만)."""
    cats = categorize_row(p)
    roles: list[str] = []
    if "ai" in cats and not ai_keywords(p.get("title")):
        roles = ai_roles(p.get("job_text"))   # 여러 직무를 묶은 공고: AI 로 분류된 근거가 된 직무명
    brand = brand_for(p["company"])
    fallback = {} if brand.key else {"bm": brand.mono, "bc": brand.color}   # 규칙에 없는 회사는 글자 타일 정보를 직접 싣는다
    return {
        **fallback,
        "b": brand.key,
        "id": p["id"], "company": p["company"], "title": p["title"], "url": p["url"],
        "start_at": p["start_at"], "end_at": p["end_at"], "career_type": p["career_type"],
        "employment_type": p["employment_type"], "status": p["status"],
        "open": p["status"] in OPEN_STATUSES,
        "cats": cats, "roles": roles,
        "regions": [{"sido": r["sido"], "sigungu": r.get("sigungu")} for r in p["regions"]],
        # 게시 시각(KST): 접수 시작일이 있으면 그것, 없으면 처음 수집한 시각. 최신순 정렬과 NEW 표시에 쓴다.
        # 새 소스를 추가하면 기존 공고가 한꺼번에 '처음 수집'되므로 시작일을 우선한다.
        "posted": p["start_at"] or _kst_naive_iso(p["first_seen"]),
    }


def source_status(db: Database, sources: list) -> list[dict]:
    """수집 대상별 최근 수집 결과. 사이트 하단 '수집 현황'에 쓴다."""
    runs = db.last_runs()
    out = []
    for s in sources:
        r = runs.get(s.key) or {}
        out.append({
            "name": s.company, "url": s.site_url,
            "fetched": r.get("fetched"), "error": bool(r.get("error")),
            "last_ok": _kst_label(r.get("last_ok")),
        })
    return out


def _kst_naive_iso(iso_utc: str) -> str:
    return datetime.fromisoformat(iso_utc).astimezone(KST).replace(tzinfo=None).isoformat(timespec="minutes")


def _kst_label(iso_utc: str | None) -> str | None:
    if not iso_utc:
        return None
    return datetime.fromisoformat(iso_utc).astimezone(KST).strftime("%m-%d %H:%M")


def build_site(db: Database, out_dir: Path, hide_after_days: int = 7, sources: list | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    postings = visible_postings(db.all_postings(), datetime.now(timezone.utc), hide_after_days)
    public = [d for d in (public_posting(p) for p in postings) if d["cats"]]   # 관심 분야 공고만 싣는다
    telegram = json.loads(db.get_meta("telegram") or "null")
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
    tpl = env.get_template("index.html")
    html = tpl.render(
        postings_json=json.dumps(public, ensure_ascii=False).replace("</", "<\\/"),
        labels_json=json.dumps(CATEGORY_LABELS, ensure_ascii=False),
        brands_json=json.dumps(brand_table(existing_logos(out_dir)), ensure_ascii=False),
        generated_at=datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        count=len(public),
        sources=source_status(db, sources or []),
        telegram=telegram,
    )
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / "postings.json").write_text(json.dumps(public, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    return out_dir / "index.html"
