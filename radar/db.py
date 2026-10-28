from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Posting, Region

SCHEMA = """
CREATE TABLE IF NOT EXISTS postings (
    id            TEXT PRIMARY KEY,   -- '<source>:<external_id>'
    source        TEXT NOT NULL,
    external_id   TEXT NOT NULL,
    company       TEXT NOT NULL,
    title         TEXT NOT NULL,
    url           TEXT NOT NULL,
    start_at      TEXT,
    end_at        TEXT,
    career_type   TEXT,
    employment_type TEXT,
    status        TEXT,
    location_raw  TEXT,
    regions_json  TEXT NOT NULL DEFAULT '[]',
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL,
    notified_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_postings_source ON postings(source);
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    source      TEXT NOT NULL,
    fetched     INTEGER NOT NULL DEFAULT 0,
    new_count   INTEGER NOT NULL DEFAULT 0,
    error       TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # --- postings -----------------------------------------------------------
    def known_ids(self, source: str) -> set[str]:
        rows = self.conn.execute("SELECT id FROM postings WHERE source = ?", (source,))
        return {r["id"] for r in rows}

    def upsert(self, p: Posting) -> bool:
        """공고를 저장한다. 처음 보는 공고면 True를 돌려준다."""
        now = _now()
        exists = self.conn.execute("SELECT 1 FROM postings WHERE id = ?", (p.id,)).fetchone()
        regions_json = json.dumps([r.model_dump() for r in p.regions], ensure_ascii=False)
        if exists:
            self.conn.execute(
                """UPDATE postings SET title=?, url=?, start_at=?, end_at=?, career_type=?,
                   employment_type=?, status=?, last_seen=?,
                   location_raw=COALESCE(?, location_raw),
                   regions_json=CASE WHEN ? = '[]' THEN regions_json ELSE ? END
                   WHERE id=?""",
                (p.title, p.url, _iso(p.start_at), _iso(p.end_at), p.career_type,
                 p.employment_type, p.status, now, p.location_raw, regions_json, regions_json, p.id),
            )
            return False
        self.conn.execute(
            """INSERT INTO postings (id, source, external_id, company, title, url, start_at, end_at,
               career_type, employment_type, status, location_raw, regions_json, first_seen, last_seen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (p.id, p.source, p.external_id, p.company, p.title, p.url, _iso(p.start_at), _iso(p.end_at),
             p.career_type, p.employment_type, p.status, p.location_raw, regions_json, now, now),
        )
        return True

    def set_regions(self, posting_id: str, location_raw: str | None, regions: list[Region]) -> None:
        self.conn.execute(
            "UPDATE postings SET location_raw=?, regions_json=? WHERE id=?",
            (location_raw, json.dumps([r.model_dump() for r in regions], ensure_ascii=False), posting_id),
        )

    def unnotified(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM postings WHERE notified_at IS NULL ORDER BY first_seen, company, title"
        ).fetchall()

    def mark_notified(self, ids: list[str]) -> None:
        now = _now()
        self.conn.executemany("UPDATE postings SET notified_at=? WHERE id=?", [(now, i) for i in ids])

    def mark_all_notified(self) -> int:
        """첫 실행 등에서 기존 공고를 알림 없이 '이미 본 것'으로 처리할 때 사용."""
        cur = self.conn.execute("UPDATE postings SET notified_at=? WHERE notified_at IS NULL", (_now(),))
        return cur.rowcount

    def all_postings(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM postings ORDER BY first_seen DESC, company, title").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["regions"] = json.loads(d.pop("regions_json") or "[]")
            out.append(d)
        return out

    # --- runs ---------------------------------------------------------------
    def start_run(self, source: str) -> int:
        cur = self.conn.execute("INSERT INTO runs (started_at, source) VALUES (?, ?)", (_now(), source))
        return int(cur.lastrowid)

    def finish_run(self, run_id: int, fetched: int, new_count: int, error: str | None = None) -> None:
        self.conn.execute(
            "UPDATE runs SET finished_at=?, fetched=?, new_count=?, error=? WHERE id=?",
            (_now(), fetched, new_count, error, run_id),
        )

    def commit(self) -> None:
        self.conn.commit()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="minutes") if dt else None
