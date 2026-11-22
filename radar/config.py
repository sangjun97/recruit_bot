from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    db_path: Path
    site_dir: Path
    telegram_token: str | None
    telegram_chat_id: str | None
    anthropic_api_key: str | None
    llm_model: str
    user_agent: str
    request_delay_sec: float
    hide_closed_after_days: int   # 마감 후 이 일수가 지나면 사이트에서 숨긴다
    purge_after_days: int         # 마감 후 이 일수가 지나면 DB에서 지운다


def _secret(name: str) -> str | None:
    value = (os.getenv(name) or "").strip().strip("\"'").strip()
    return value or None


# 텔레그램 봇 토큰은 '<봇 번호>:<35자>' 꼴이다
TOKEN_RE = re.compile(r"(?<!\d)\d{6,12}:[A-Za-z0-9_-]{35}")


def telegram_token(raw: str | None) -> str | None:
    """등록된 값에서 봇 토큰만 꺼낸다.

    시크릿에 'TELEGRAM_BOT_TOKEN=…' 줄 전체나 .env 내용을 통째로 붙여넣었거나, 토큰이 줄바꿈으로 끊겨 들어간 경우에도
    토큰 모양을 찾아 쓴다. 못 찾으면 받은 값을 그대로 돌려주고, 알림 단계가 형식 오류로 보고한다.
    """
    if not raw:
        return None
    m = TOKEN_RE.search(re.sub(r"\s+", "", raw))
    return m.group(0) if m else raw


def telegram_chat_id(raw: str | None) -> str | None:
    """등록된 값에서 채팅 ID(숫자)만 꺼낸다."""
    if not raw or re.fullmatch(r"-?\d+", raw):
        return raw
    rest = TOKEN_RE.sub(" ", re.sub(r"[ \t\r\n]+", " ", raw))   # 토큰이 같이 들어 있으면 그 안의 숫자는 빼고 찾는다
    m = re.search(r"(?<![\d:])-?\d{5,}(?![\d:])", rest)
    return m.group(0) if m else raw


def load_settings() -> Settings:
    return Settings(
        db_path=Path(os.getenv("RADAR_DB_PATH", ROOT / "data" / "radar.sqlite")),
        site_dir=Path(os.getenv("RADAR_SITE_DIR", ROOT / "docs")),
        # 붙여넣을 때 섞이기 쉬운 공백·줄바꿈·따옴표·변수 이름은 떼어 낸다(GitHub Secrets 는 입력한 그대로 보관한다)
        telegram_token=telegram_token(_secret("TELEGRAM_BOT_TOKEN")),
        telegram_chat_id=telegram_chat_id(_secret("TELEGRAM_CHAT_ID")),
        anthropic_api_key=_secret("ANTHROPIC_API_KEY"),
        llm_model=os.getenv("RADAR_LLM_MODEL", "claude-haiku-5-5"),
        # 수집기임을 숨기지 않는다. 사이트 운영자가 식별할 수 있도록 프로젝트명을 포함한다.
        user_agent=os.getenv(
            "RADAR_USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0 Safari/537.36 RecruitRadar/0.1 (personal job-alert bot)",
        ),
        request_delay_sec=float(os.getenv("RADAR_REQUEST_DELAY", "1.5")),
        hide_closed_after_days=int(os.getenv("RADAR_HIDE_CLOSED_DAYS", "7")),
        purge_after_days=int(os.getenv("RADAR_PURGE_DAYS", "90")),
    )
