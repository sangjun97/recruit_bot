from __future__ import annotations

import html
import json
import re
import sqlite3

import httpx

from .categories import CATEGORY_LABELS, ai_keywords, ai_roles, categorize_row
from .config import TOKEN_RE

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
MAX_MESSAGE_LEN = 3800  # 텔레그램 한도 4096자보다 여유 있게
MAX_REGIONS = 4         # 근무지가 이보다 많으면 시·도만 적는다


class TelegramError(RuntimeError):
    pass


def _call(token: str, method: str, **params) -> dict:
    """텔레그램 API 호출. 실패 사유만 담은 TelegramError 를 낸다(오류 메시지에 토큰이 든 URL이 섞이지 않게)."""
    try:
        resp = httpx.post(TELEGRAM_API.format(token=token, method=method), data=params, timeout=30)
    except httpx.HTTPError as e:
        raise TelegramError(f"텔레그램 연결 실패: {type(e).__name__}") from None
    except Exception as e:
        # 토큰에 공백·줄바꿈·한글 같은 글자가 섞이면 주소를 만드는 단계에서 실패한다(httpx.InvalidURL 등)
        raise TelegramError(
            f"요청을 만들 수 없음({type(e).__name__}) → 봇 토큰에 공백이나 다른 글자가 섞였습니다. TELEGRAM_BOT_TOKEN 값을 다시 등록하세요."
        ) from None
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.status_code != 200 or not body.get("ok"):
        desc = str(body.get("description", f"HTTP {resp.status_code}"))
        hint = ""
        if "chat not found" in desc:
            hint = " → 채팅 ID가 틀렸거나, 텔레그램에서 봇을 열고 '시작(Start)'을 누르지 않았습니다."
        elif "Unauthorized" in desc or resp.status_code in (401, 404):
            hint = " → 봇 토큰이 틀렸습니다. TELEGRAM_BOT_TOKEN 값을 다시 등록하세요."
        raise TelegramError(f"{desc}{hint}".replace(token, "***"))
    return body


def send_telegram(token: str, chat_id: str, text: str) -> None:
    _call(token, "sendMessage", chat_id=chat_id, text=text, parse_mode="HTML", disable_web_page_preview="true")


def check_telegram(token: str, chat_id: str) -> str | None:
    """메시지를 보내지 않고 토큰과 채팅 ID가 유효한지 확인한다. 문제가 있으면 사유를, 없으면 None 을 돌려준다."""
    if not TOKEN_RE.fullmatch(token):
        # 값 자체는 남기지 않고 모양만 알려 준다(공개 페이지에 표시되는 문구다)
        return (
            f"봇 토큰 형식이 아닙니다(등록된 값: {len(token)}자, {token.count(chr(10)) + 1}줄). "
            "BotFather 가 준 '숫자:영문자' 한 줄만 TELEGRAM_BOT_TOKEN 에 등록하세요."
        )
    if not re.fullmatch(r"-?\d+", chat_id):
        return f"채팅 ID 형식이 아닙니다(등록된 값: {len(chat_id)}자). 숫자만 TELEGRAM_CHAT_ID 에 등록하세요."
    try:
        _call(token, "getMe")
        _call(token, "getChat", chat_id=chat_id)
    except TelegramError as e:
        return str(e)
    return None


def _region_text(regions: list[dict]) -> str:
    if not regions:
        return "근무지 미확인"
    if len(regions) > MAX_REGIONS:
        return ", ".join(dict.fromkeys(x["sido"] for x in regions))
    return ", ".join(f"{x['sido']} {x.get('sigungu') or ''}".strip() for x in regions)


def format_posting(row: sqlite3.Row | dict) -> str:
    r = dict(row)
    regions = r.get("regions")
    if regions is None:
        regions = json.loads(r.get("regions_json") or "[]")
    cats = categorize_row(r)
    tags = "".join(f"[{CATEGORY_LABELS[c]}] " for c in cats)
    period = ""
    if r.get("start_at") or r.get("end_at"):
        s = (r.get("start_at") or "")[:10]
        e = (r.get("end_at") or "").replace("T", " ")[:16]
        period = f"\n   📅 {s} ~ {e}"
    meta = " · ".join(x for x in [r.get("career_type"), r.get("employment_type")] if x)
    meta = f"\n   {html.escape(meta)}" if meta else ""
    roles = ""
    if "ai" in cats and not ai_keywords(r.get("title")):
        # 여러 직무를 묶은 공고: 어떤 직무 때문에 AI 로 분류됐는지 보여준다
        names = ai_roles(r.get("job_text"), limit=5)
        if names:
            roles = f"\n   🤖 {html.escape(', '.join(names))}"
    return (
        f"{html.escape(tags)}<b>{html.escape(r['company'])}</b> | "
        f"<a href=\"{html.escape(r['url'])}\">{html.escape(r['title'])}</a>"
        f"{roles}\n   📍 {html.escape(_region_text(regions))}{period}{meta}"
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
