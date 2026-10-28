"""실행 진입점.

  python -m radar run [--sources hyundaicard,...] [--no-notify] [--bootstrap] [--no-site]
  python -m radar build-site
  python -m radar notify-test
  python -m radar extract "근무지: 경기도 이천시 ..."
"""
from __future__ import annotations

import argparse
import sys
import traceback

from playwright.sync_api import sync_playwright

from .config import load_settings
from .db import Database
from .location import extract_regions
from .notify import build_messages, send_telegram, format_posting
from .site import build_site
from .sources import get_sources


def cmd_run(args: argparse.Namespace) -> int:
    settings = load_settings()
    db = Database(settings.db_path)
    sources = get_sources(args.sources.split(",") if args.sources else None)
    had_error = False

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(user_agent=settings.user_agent, locale="ko-KR")
        for src in sources:
            run_id = db.start_run(src.key)
            new_count = fetched = 0
            try:
                postings = src.fetch_list(ctx)
                fetched = len(postings)
                print(f"[{src.key}] 목록 {fetched}건")
                for p in postings:
                    is_new = db.upsert(p)
                    if is_new:
                        new_count += 1
                        loc_text = src.fetch_location_text(ctx, p)
                        db.upsert(p)  # 상세 조회 중 채워진 필드(시작일 등)를 반영
                        regions = extract_regions(loc_text, settings)
                        db.set_regions(p.id, loc_text, regions)
                        label = ", ".join(r.label() for r in regions) or "근무지 미확인"
                        print(f"  + {p.title}  →  {label}")
                db.commit()
                db.finish_run(run_id, fetched, new_count)
            except Exception as e:  # 한 소스의 실패가 다른 소스를 막지 않게 한다
                had_error = True
                traceback.print_exc()
                db.finish_run(run_id, fetched, new_count, error=f"{type(e).__name__}: {e}")
            db.commit()
        browser.close()

    pending = db.unnotified()
    if args.bootstrap:
        n = db.mark_all_notified()
        print(f"[bootstrap] 기존 공고 {n}건을 알림 없이 확인 처리")
    elif pending and not args.no_notify:
        if not (settings.telegram_token and settings.telegram_chat_id):
            print("[notify] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 없어 알림을 건너뜀")
        else:
            for msg in build_messages(pending):
                send_telegram(settings.telegram_token, settings.telegram_chat_id, msg)
            db.mark_notified([r["id"] for r in pending])
            print(f"[notify] {len(pending)}건 알림 전송")
    elif pending:
        print(f"[notify] 미알림 {len(pending)}건 (--no-notify)")
    db.commit()

    purged = db.purge_closed(settings.purge_after_days)
    if purged:
        print(f"[purge] 마감 후 {settings.purge_after_days}일 지난 공고 {purged}건 삭제")
    db.commit()

    if not args.no_site:
        out = build_site(db, settings.site_dir, settings.hide_closed_after_days)
        print(f"[site] {out}")
    db.close()
    return 1 if had_error else 0


def cmd_build_site(args: argparse.Namespace) -> int:
    settings = load_settings()
    db = Database(settings.db_path)
    print(build_site(db, settings.site_dir, settings.hide_closed_after_days))
    return 0


def cmd_notify_test(args: argparse.Namespace) -> int:
    settings = load_settings()
    if not (settings.telegram_token and settings.telegram_chat_id):
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 를 .env 에 설정하세요")
        return 2
    db = Database(settings.db_path)
    rows = db.all_postings()[:3]
    body = "\n\n".join(format_posting(r) for r in rows) if rows else "(저장된 공고가 없습니다)"
    send_telegram(settings.telegram_token, settings.telegram_chat_id, "🧪 채용 레이더 테스트 메시지\n\n" + body)
    print("전송 완료")
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
    r = sub.add_parser("run", help="수집 → 근무지 추출 → 알림 → 사이트 생성")
    r.add_argument("--sources", help="쉼표로 구분한 소스 키. 생략하면 전부")
    r.add_argument("--no-notify", action="store_true")
    r.add_argument("--bootstrap", action="store_true", help="첫 실행: 기존 공고를 알림 없이 확인 처리")
    r.add_argument("--no-site", action="store_true")
    r.set_defaults(func=cmd_run)
    sub.add_parser("build-site").set_defaults(func=cmd_build_site)
    sub.add_parser("notify-test").set_defaults(func=cmd_notify_test)
    e = sub.add_parser("extract")
    e.add_argument("text")
    e.set_defaults(func=cmd_extract)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
