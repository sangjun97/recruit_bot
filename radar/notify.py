from __future__ import annotations

import html
import sqlite3

import httpx

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
MAX_MESSAGE_LEN = 3800  # 텔레그램 한도 4096자보다 여유 있게


class TelegramError(RuntimeError):
    pass


def send_telegram(token: str, chat_id: str, text: str) -> None:
    resp = httpx.post(
        TELEGRAM_API.format(token=token, method="sendMessage"),
        data={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": "true"},
        timeout=30,
    )
    # 오류 메시지에 토큰이 들어간 URL이 찍히지 않도록 직접 처리한다
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.status_code != 200 or not body.get("ok"):
        desc = body.get("description", f"HTTP {resp.status_code}")
        hint = ""
        if "chat not found" in desc:
            hint = " → 텔레그램에서 봇을 열고 '시작(Start)'을 한 번 눌러야 봇이 메시지를 보낼 수 있습니다."
        raise TelegramError(f"텔레그램 전송 실패: {desc}{hint}")


def format_posting(row: sqlite3.Row | dict) -> str:
    r = dict(row)
    regions = r.get("regions")
    if regions is None:
        import json
        regions = json.loads(r.get("regions_json") or "[]")
    region_txt = ", ".join(f"{x['sido']} {x.get('sigungu') or ''}".strip() for x in regions) or "근무지 미확인"
    period = ""
    if r.get("start_at") or r.get("end_at"):
        s = (r.get("start_at") or "")[:10]
        e = (r.get("end_at") or "").replace("T", " ")[:16]
        period = f"\n   📅 {s} ~ {e}"
    meta = " · ".join(x for x in [r.get("career_type"), r.get("employment_type"), r.get("status")] if x)
    meta = f"\n   {html.escape(meta)}" if meta else ""
    return (
        f"<b>{html.escape(r['company'])}</b> | <a href=\"{html.escape(r['url'])}\">{html.escape(r['title'])}</a>"
        f"\n   📍 {html.escape(region_txt)}{period}{meta}"
    )


def build_messages(rows: list) -> list[str]:
    """공고 목록을 텔레그램 길이 한도에 맞게 여러 메시지로 나눈다."""
    if not rows:
        return []
    header = f"🔔 새 채용 공고 {len(rows)}건\n\n"
    messages, current = [], header
    for row in rows:
        chunk = format_posting(row) + "\n\n"
        if len(current) + len(chunk) > MAX_MESSAGE_LEN:
            messages.append(current.rstrip())
            current = ""
        current += chunk
    if current.strip():
        messages.append(current.rstrip())
    return messages
