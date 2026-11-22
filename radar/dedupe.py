"""같은 공고가 공식 사이트와 채용 포털, 또는 포털 두 곳에 함께 올라온 경우 하나만 남긴다.

포털은 공식 사이트를 읽을 수 없는 회사를 보완하려고 쓴다. 그래서 겹치면 공식 사이트 것을 남기고,
포털끼리 겹치면 소스 목록에서 앞에 있는 쪽(마감일 정보가 있는 사람인)을 남긴다.
같은 공고인지는 회사 이름과 제목으로 판단한다(공백·기호·대소문자는 무시).
"""
from __future__ import annotations

import re

_CORP_MARK_RE = re.compile(r"\(주\)|㈜|주식회사")
_NOISE_RE = re.compile(r"[\s\W_]+", re.UNICODE)


def posting_key(company: str | None, title: str | None) -> tuple[str, str]:
    comp = _NOISE_RE.sub("", _CORP_MARK_RE.sub("", company or "")).casefold()
    return comp, _NOISE_RE.sub("", title or "").casefold()


def drop_portal_duplicates(rows: list[dict], source_order: list[str], portal_keys: set[str]) -> tuple[list[dict], list[dict]]:
    """rows 에서 포털 중복을 뺀다. (남긴 행, 뺀 행)을 돌려준다. 남긴 행의 순서는 입력 그대로다."""
    if not portal_keys:
        return rows, []
    rank = {key: i for i, key in enumerate(source_order)}

    def priority(row: dict) -> tuple[int, int, int]:
        # 접수 중인 쪽을 먼저, 그다음 공식 사이트, 그다음 소스 목록 순서
        src = row.get("source")
        return (0 if row.get("_open", True) else 1, 1 if src in portal_keys else 0, rank.get(src, len(rank)))

    best: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = posting_key(row.get("company"), row.get("title"))
        if key not in best or priority(row) < priority(best[key]):
            best[key] = row
    kept, dropped = [], []
    for row in rows:
        key = posting_key(row.get("company"), row.get("title"))
        if row.get("source") in portal_keys and best[key] is not row:
            dropped.append(row)
        else:
            kept.append(row)
    return kept, dropped
