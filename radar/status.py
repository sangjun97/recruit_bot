"""공고가 지금 접수 중인지 판단하는 규칙. 사이트 생성과 알림이 같은 규칙을 쓴다."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
OPEN_STATUSES = (None, "", "접수중", "접수예정", "상시")
CLOSED = "접수마감"
VANISHED_AFTER = timedelta(days=1)   # 공고 목록에서 이만큼 안 보이면 내려간 것으로 본다


def kst_naive(now_utc: datetime) -> datetime:
    return now_utc.astimezone(KST).replace(tzinfo=None)


def effective_status(row: dict, now_utc: datetime) -> str | None:
    """저장된 상태에 마감일·목록 이탈을 반영한 현재 상태. end_at 은 KST 자연 시각 문자열이다."""
    status = row.get("status")
    if status not in OPEN_STATUSES:
        return status
    end_at, last_seen = row.get("end_at"), row.get("last_seen") or ""
    if end_at and end_at < kst_naive(now_utc).isoformat(timespec="minutes"):
        return CLOSED
    if last_seen and last_seen < (now_utc - VANISHED_AFTER).isoformat(timespec="seconds"):
        return CLOSED
    return status


def is_open(row: dict, now_utc: datetime) -> bool:
    return effective_status(row, now_utc) in OPEN_STATUSES
