from __future__ import annotations

import os
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


def load_settings() -> Settings:
    return Settings(
        db_path=Path(os.getenv("RADAR_DB_PATH", ROOT / "data" / "radar.sqlite")),
        site_dir=Path(os.getenv("RADAR_SITE_DIR", ROOT / "docs")),
        telegram_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
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
