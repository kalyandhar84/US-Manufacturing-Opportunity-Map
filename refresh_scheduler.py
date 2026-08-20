"""7-day background refresh for hosted App Service.

Runs as a sibling process to Streamlit (started by startup.sh). Does not
refresh on restart when the last successful run is younger than 7 days.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "moi.sqlite"
STAMP_PATH = ROOT / "data" / "last_refresh.txt"
REFRESH_SCRIPT = ROOT / "refresh_data.py"

INTERVAL = timedelta(days=7)
ERROR_RETRY = timedelta(hours=6)
SLEEP_CHUNK_SEC = 3600
REFRESH_TIMEOUT_SEC = 3600
SUCCESS_STATUSES = ("ok", "partial")


def log(message: str) -> None:
    print(f"[refresh-scheduler] {message}", flush=True)


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def last_success_from_sqlite() -> datetime | None:
    if not DB_PATH.exists():
        return None
    uri = f"file:{DB_PATH.resolve().as_posix()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=30)
        try:
            row = conn.execute(
                """
                SELECT finished_at
                FROM refresh_runs
                WHERE status IN (?, ?) AND finished_at IS NOT NULL
                ORDER BY finished_at DESC
                LIMIT 1
                """,
                SUCCESS_STATUSES,
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        log(f"could not read refresh_runs: {exc}")
        return None
    if not row:
        return None
    return parse_iso(row[0])


def last_success_from_stamp() -> datetime | None:
    if not STAMP_PATH.exists():
        return None
    try:
        return parse_iso(STAMP_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        log(f"could not read {STAMP_PATH.name}: {exc}")
        return None


def last_success() -> datetime | None:
    return last_success_from_sqlite() or last_success_from_stamp()


def write_stamp(when: datetime) -> None:
    STAMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    STAMP_PATH.write_text(when.replace(microsecond=0).isoformat(), encoding="utf-8")


def sleep_until(deadline: datetime) -> None:
    while True:
        remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0:
            return
        chunk = min(SLEEP_CHUNK_SEC, remaining)
        log(f"next wake in {remaining / 3600:.1f}h; sleeping {chunk / 60:.0f}m")
        time.sleep(chunk)


def run_refresh() -> bool:
    log("starting python refresh_data.py (full refresh, not --seed-only)")
    try:
        completed = subprocess.run(
            [sys.executable, str(REFRESH_SCRIPT)],
            cwd=str(ROOT),
            timeout=REFRESH_TIMEOUT_SEC,
            check=False,
        )
    except subprocess.TimeoutExpired:
        log(f"refresh timed out after {REFRESH_TIMEOUT_SEC // 60} minutes")
        return False
    except OSError as exc:
        log(f"refresh failed to start: {exc}")
        return False
    if completed.returncode != 0:
        log(f"refresh exited {completed.returncode}")
        return False
    when = last_success_from_sqlite() or datetime.now(timezone.utc)
    write_stamp(when)
    log(f"refresh succeeded at {when.isoformat()}")
    return True


def main() -> int:
    log("started; 7-day cadence; skip if last success is younger than 7 days")
    while True:
        last = last_success()
        now = datetime.now(timezone.utc)
        if last is not None and now - last < INTERVAL:
            due = last + INTERVAL
            log(f"last success {last.isoformat()}; next due {due.isoformat()}")
            sleep_until(due)
        elif last is None:
            log("no successful refresh on this host; running now")
        else:
            log(f"last success {last.isoformat()} is >= 7 days; running now")

        if run_refresh():
            continue
        retry_at = datetime.now(timezone.utc) + ERROR_RETRY
        log(f"refresh failed; retry at {retry_at.isoformat()}")
        sleep_until(retry_at)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        log("stopped")
        raise SystemExit(0)
