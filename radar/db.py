from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Posting

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
    notified_at   TEXT,
    job_text      TEXT                -- 직무 분류·모집 직무명(줄 단위). NULL 은 상세를 아직 못 본 상태
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
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

KEEP_RUNS = 600   # runs 테이블에 남길 최근 기록 수. DB 파일이 계속 커지지 않게 한다


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(postings)")}
        if "job_text" not in cols:
            self.conn.execute("ALTER TABLE postings ADD COLUMN job_text TEXT")

    def close(self) -> None:
        self.conn.close()

    # --- postings -----------------------------------------------------------
    def known(self, source: str) -> dict[str, sqlite3.Row]:
        """소스의 저장된 공고. id → 행(job_text 포함)."""
        rows = self.conn.execute("SELECT id, job_text, location_raw FROM postings WHERE source = ?", (source,))
        return {r["id"]: r for r in rows}

    def upsert(self, p: Posting) -> bool:
        """공고를 저장한다. 처음 보는 공고면 True를 돌려준다."""
        now = _now()
        old = self.conn.execute("SELECT start_at, end_at FROM postings WHERE id = ?", (p.id,)).fetchone()
        regions_json = json.dumps([r.model_dump() for r in p.regions], ensure_ascii=False)
        start, end = _iso(p.start_at), _iso(p.end_at)
        if old:
            # 목록에 날짜만 있는 소스: 상세에서 받은 정확한 시각이 같은 날짜로 이미 있으면 그대로 둔다
            if p.end_date_only:
                if end and old["end_at"] and old["end_at"][:10] == end[:10]:
                    end = old["end_at"]
                if start and old["start_at"] and old["start_at"][:10] == start[:10]:
                    start = old["start_at"]
            self.conn.execute(
                """UPDATE postings SET company=?, title=?, url=?,
                   start_at=COALESCE(?, start_at), end_at=COALESCE(?, end_at),
                   career_type=COALESCE(?, career_type), employment_type=COALESCE(?, employment_type),
                   status=?, last_seen=?,
                   job_text=COALESCE(?, job_text),
                   location_raw=COALESCE(?, location_raw),
                   regions_json=CASE WHEN ? = '[]' THEN regions_json ELSE ? END
                   WHERE id=?""",
                (p.company, p.title, p.url, start, end, p.career_type, p.employment_type, p.status, now,
                 p.job_text, p.location_raw, regions_json, regions_json, p.id),
            )
            return False
        self.conn.execute(
            """INSERT INTO postings (id, source, external_id, company, title, url, start_at, end_at,
               career_type, employment_type, status, job_text, location_raw, regions_json, first_seen, last_seen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (p.id, p.source, p.external_id, p.company, p.title, p.url, start, end,
             p.career_type, p.employment_type, p.status, p.job_text, p.location_raw, regions_json, now, now),
        )
        return True

    def unnotified(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM postings WHERE notified_at IS NULL ORDER BY first_seen, company, title"
        ).fetchall()

    def mark_notified(self, ids: list[str]) -> None:
        now = _now()
        self.conn.executemany("UPDATE postings SET notified_at=? WHERE id=?", [(now, i) for i in ids])

    def all_postings(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM postings ORDER BY first_seen DESC, company, title").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["regions"] = json.loads(d.pop("regions_json") or "[]")
            out.append(d)
        return out

    def purge_closed(self, older_than_days: int) -> int:
        """마감일(없으면 마지막으로 목록에서 본 날)이 older_than_days 보다 오래된 공고를 지운다."""
        now_utc = datetime.now(timezone.utc)
        cutoff_seen = (now_utc - timedelta(days=older_than_days)).isoformat(timespec="seconds")
        # end_at 은 사이트 기준(KST) 자연 시각이라 KST 로 비교한다
        cutoff_end = (
            (now_utc + timedelta(hours=9) - timedelta(days=older_than_days))
            .replace(tzinfo=None)
            .isoformat(timespec="minutes")
        )
        cur = self.conn.execute(
            """DELETE FROM postings
               WHERE (end_at IS NOT NULL AND end_at < ?)
                  OR (end_at IS NULL AND last_seen < ?)""",
            (cutoff_end, cutoff_seen),
        )
        return cur.rowcount

    # --- runs ---------------------------------------------------------------
    def start_run(self, source: str) -> int:
        cur = self.conn.execute("INSERT INTO runs (started_at, source) VALUES (?, ?)", (_now(), source))
        return int(cur.lastrowid)

    def finish_run(self, run_id: int, fetched: int, new_count: int, error: str | None = None) -> None:
        self.conn.execute(
            "UPDATE runs SET finished_at=?, fetched=?, new_count=?, error=? WHERE id=?",
            (_now(), fetched, new_count, error, run_id),
        )

    def has_successful_run(self, source: str) -> bool:
        """이 소스를 한 번이라도 끝까지 수집한 적이 있는지. 없으면 새로 추가된 소스다."""
        row = self.conn.execute(
            "SELECT 1 FROM runs WHERE source=? AND finished_at IS NOT NULL AND error IS NULL LIMIT 1", (source,)
        ).fetchone()
        return row is not None

    def last_runs(self) -> dict[str, dict]:
        """소스별 최근 실행(시각·건수·오류)과 최근 성공 시각."""
        rows = self.conn.execute(
            """SELECT r.source, r.started_at, r.fetched, r.error,
                      (SELECT MAX(s.started_at) FROM runs s
                        WHERE s.source = r.source AND s.error IS NULL AND s.finished_at IS NOT NULL) AS last_ok
               FROM runs r WHERE r.id IN (SELECT MAX(id) FROM runs GROUP BY source)"""
        )
        return {r["source"]: dict(r) for r in rows}

    def prune_runs(self, keep: int = KEEP_RUNS) -> None:
        self.conn.execute("DELETE FROM runs WHERE id <= (SELECT MAX(id) FROM runs) - ?", (keep,))

    # --- meta ---------------------------------------------------------------
    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str | None) -> None:
        self.conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def commit(self) -> None:
        self.conn.commit()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="minutes") if dt else None
