"""실행 진입점.

  python -m radar run [--sources hyundaicard,...] [--no-notify] [--bootstrap] [--no-site]
  python -m radar build-site
  python -m radar notify-test
  python -m radar sources
  python -m radar extract "근무지: 경기도 이천시 ..."
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import traceback
from datetime import datetime, timedelta, timezone

from .categories import CATEGORY_LABELS, categorize_row
from .config import Settings, load_settings
from .db import Database
from .fetch import Fetcher
from .location import extract_regions
from .models import Posting
from .notify import TelegramError, build_messages, check_telegram, format_posting, send_telegram
from .site import build_site
from .sources import SOURCES, get_sources
from .sources.base import Source
from .status import OPEN_STATUSES, is_open, kst_naive


def _posting_open(p: Posting, now_utc: datetime) -> bool:
    if p.status not in OPEN_STATUSES:
        return False
    return not (p.end_at and p.end_at < kst_naive(now_utc))


def _load_detail(src: Source, f: Fetcher, p: Posting, settings: Settings) -> bool:
    """상세를 읽어 근무지·직무명·정확한 기간을 채운다. 한 공고의 실패가 소스 전체를 막지 않게 한다."""
    list_location = p.location_raw
    try:
        loc_text = src.fetch_detail(f, p)
    except Exception as e:
        print(f"  ! 상세 조회 실패 {p.id}: {type(e).__name__}: {e}")
        p.location_raw = list_location
        loc_text = list_location
        ok = False
    else:
        ok = True
        if p.job_text is None and src.detail_for_classify:
            p.job_text = ""   # 상세를 봤지만 직무명이 없는 공고. 다음 실행에서 다시 조회하지 않게 표시
    p.location_raw = loc_text
    # LLM 보조 추출을 허용하지 않는 소스는 API 키를 빼고 넘겨 규칙으로만 추출한다
    llm_settings = settings if src.llm_ok else dataclasses.replace(settings, anthropic_api_key=None)
    p.regions = extract_regions(loc_text, llm_settings) if loc_text else []
    return ok


def _due(src: Source, db: Database, now_utc: datetime) -> bool:
    """수집 간격(min_interval_min)이 정해진 소스가 이번 실행에서 수집할 차례인지."""
    if not src.min_interval_min:
        return True
    last_ok = (db.last_runs().get(src.key) or {}).get("last_ok")
    if not last_ok:
        return True
    return now_utc - datetime.fromisoformat(last_ok) >= timedelta(minutes=src.min_interval_min)


def collect(src: Source, f: Fetcher, db: Database, settings: Settings, now_utc: datetime) -> tuple[int, int]:
    """한 소스를 수집해 DB 에 반영한다. (목록 건수, 새로 저장한 관심 공고 수)를 돌려준다."""
    first_time = not db.has_successful_run(src.key)   # 새로 추가된 소스: 이미 올라와 있던 공고는 알리지 않는다
    known = db.known(src.key)
    postings = src.fetch_list(f)
    new_count = 0
    for p in postings:
        row = known.get(p.id)
        if row is not None:
            if src.detail_for_classify and row["job_text"] is None and _posting_open(p, now_utc):
                _load_detail(src, f, p, settings)   # 예전에 저장한 공고: 직무명·정확한 기간을 보충한다
            else:
                p.location_raw = None               # 목록 수준 근무지가 저장된 상세 근무지를 덮어쓰지 않게
            db.upsert(p)
            continue
        if not _posting_open(p, now_utc):
            continue   # 처음 봤는데 이미 마감된 공고는 저장하지 않는다
        if not (src.detail_for_classify or categorize_row(p)):
            continue   # 관심 분야(AI·데이터, 카드사)가 아닌 공고는 저장하지 않는다
        _load_detail(src, f, p, settings)
        db.upsert(p)
        cats = categorize_row(p)
        if first_time:
            db.mark_notified([p.id])
        if cats:
            new_count += 1
            label = ", ".join(r.label() for r in p.regions) or "근무지 미확인"
            tag = "/".join(CATEGORY_LABELS[c] for c in cats)
            print(f"  + [{tag}] {p.company} | {p.title}  →  {label}")
    if first_time and new_count:
        print(f"  (새 소스: 기존 공고 {new_count}건은 알림 없이 등록)")
    skipped = getattr(src, "skipped_companies", None)
    if skipped:
        names = ", ".join(f"{name} {n}" for name, n in skipped.most_common(12))
        print(f"  (범위 밖 계열사 {sum(skipped.values())}건 제외: {names})")
    return len(postings), new_count


def notify(db: Database, settings: Settings, args: argparse.Namespace, now_utc: datetime) -> bool:
    """아직 알리지 않은 관심 공고를 텔레그램으로 보낸다. 전송에 실패하면 False."""
    send_rows, closed_ids = [], []
    for r in db.unnotified():
        row = dict(r)
        if not categorize_row(row):
            continue                      # 관심 분야가 아님. 분류 기준이 바뀌어 해당되면 그때 알린다
        if not is_open(row, now_utc):
            closed_ids.append(row["id"])  # 알리기 전에 마감된 공고는 보내지 않고 확인 처리
            continue
        send_rows.append(row)
    db.mark_notified(closed_ids)

    has_creds = bool(settings.telegram_token and settings.telegram_chat_id)
    ok = True
    if has_creds and not args.no_notify:
        # 보낼 공고가 없는 실행에서도 토큰·채팅 ID가 유효한지 확인해 둔다(사이트 하단에 표시)
        problem = check_telegram(settings.telegram_token, settings.telegram_chat_id)
        db.set_meta("telegram", json.dumps({"ok": problem is None, "detail": problem, "at": now_utc.isoformat(timespec="seconds")}, ensure_ascii=False))
        if problem:
            print(f"[notify] 텔레그램 설정 오류: {problem}")
            ok = False

    if args.bootstrap:
        db.mark_notified([r["id"] for r in send_rows])
        print(f"[bootstrap] 관심 공고 {len(send_rows)}건을 알림 없이 확인 처리")
    elif not send_rows:
        print("[notify] 새로 알릴 공고 없음")
    elif args.no_notify:
        print(f"[notify] 미알림 {len(send_rows)}건 (--no-notify)")
    elif not has_creds:
        print("[notify] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 없어 알림을 건너뜀")
    elif ok:
        try:
            for msg in build_messages(send_rows):
                send_telegram(settings.telegram_token, settings.telegram_chat_id, msg)
        except TelegramError as e:
            print(f"[notify] 전송 실패: {e}")
            db.set_meta("telegram", json.dumps({"ok": False, "detail": str(e), "at": now_utc.isoformat(timespec="seconds")}, ensure_ascii=False))
            ok = False
        else:
            db.mark_notified([r["id"] for r in send_rows])
            print(f"[notify] {len(send_rows)}건 알림 전송")
    return ok


def cmd_run(args: argparse.Namespace) -> int:
    settings = load_settings()
    db = Database(settings.db_path)
    sources = get_sources(args.sources.split(",") if args.sources else None)
    now_utc = datetime.now(timezone.utc)
    failed: list[str] = []

    with Fetcher(settings.user_agent, settings.request_delay_sec) as f:
        for src in sources:
            if not args.sources and not _due(src, db, now_utc):
                print(f"[{src.key}] 수집 간격({src.min_interval_min}분)이 지나지 않아 건너뜀")
                continue
            run_id = db.start_run(src.key)
            fetched = new_count = 0
            try:
                fetched, new_count = collect(src, f, db, settings, now_utc)
                print(f"[{src.key}] 목록 {fetched}건, 새 관심 공고 {new_count}건")
                db.finish_run(run_id, fetched, new_count)
            except Exception as e:  # 한 소스의 실패가 다른 소스를 막지 않게 한다
                failed.append(src.key)
                traceback.print_exc()
                db.finish_run(run_id, fetched, new_count, error=f"{type(e).__name__}: {e}"[:300])
            db.commit()

    notify_ok = notify(db, settings, args, now_utc)
    db.commit()

    purged = db.purge_closed(settings.purge_after_days)
    if purged:
        print(f"[purge] 마감 후 {settings.purge_after_days}일 지난 공고 {purged}건 삭제")
    db.prune_runs()
    db.commit()

    # 알림이나 일부 소스가 실패해도 사이트는 항상 다시 만든다
    if not args.no_site:
        out = build_site(db, settings.site_dir, settings.hide_closed_after_days, SOURCES)
        print(f"[site] {out}")
    db.close()
    if failed:
        print(f"[run] 실패한 소스: {', '.join(failed)}")
    return 1 if (failed or not notify_ok) else 0


def cmd_build_site(args: argparse.Namespace) -> int:
    settings = load_settings()
    db = Database(settings.db_path)
    print(build_site(db, settings.site_dir, settings.hide_closed_after_days, SOURCES))
    return 0


def cmd_notify_test(args: argparse.Namespace) -> int:
    settings = load_settings()
    if not (settings.telegram_token and settings.telegram_chat_id):
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 를 .env 에 설정하세요")
        return 2
    db = Database(settings.db_path)
    rows = [r for r in db.all_postings() if categorize_row(r)][:3]
    body = "\n\n".join(format_posting(r) for r in rows) if rows else "(저장된 공고가 없습니다)"
    try:
        send_telegram(settings.telegram_token, settings.telegram_chat_id, "🧪 채용 레이더 테스트 메시지\n\n" + body)
    except TelegramError as e:
        print(f"전송 실패: {e}")
        return 1
    print("전송 완료")
    return 0


def cmd_sources(args: argparse.Namespace) -> int:
    settings = load_settings()
    db = Database(settings.db_path)
    runs = db.last_runs()
    for s in SOURCES:
        r = runs.get(s.key) or {}
        state = "미실행" if not r else ("오류: " + r["error"] if r.get("error") else f"{r['fetched']}건")
        print(f"{s.key:16} {s.company:28} {state:14} {s.site_url}")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    settings = load_settings()
    regions = extract_regions(args.text, settings)
    for r in regions:
        print(f"{r.label()}  ({r.method})")
    if not regions:
        print("(추출 결과 없음)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="radar")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="수집 → 분류 → 근무지 추출 → 알림 → 사이트 생성")
    r.add_argument("--sources", help="쉼표로 구분한 소스 키. 생략하면 전부")
    r.add_argument("--no-notify", action="store_true")
    r.add_argument("--bootstrap", action="store_true", help="쌓여 있는 미알림 공고를 알림 없이 확인 처리")
    r.add_argument("--no-site", action="store_true")
    r.set_defaults(func=cmd_run)
    sub.add_parser("build-site").set_defaults(func=cmd_build_site)
    sub.add_parser("notify-test").set_defaults(func=cmd_notify_test)
    sub.add_parser("sources", help="등록된 소스와 최근 수집 결과").set_defaults(func=cmd_sources)
    e = sub.add_parser("extract")
    e.add_argument("text")
    e.set_defaults(func=cmd_extract)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
