"""
VoxFox user tracking — records every unique user who has interacted with the bot.
"""

import logging
import sqlite3
import time
from pathlib import Path

log = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent / "stats.db"


def _db():
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init() -> None:
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                first_seen REAL NOT NULL
            )
        """)
    log.info("Stats DB initialised at %s", _DB_PATH)


def record_user(user_id: int | None) -> None:
    """Record a user interaction. Silently ignores None (e.g. channel posts)."""
    if user_id is None:
        return
    try:
        with _db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, first_seen) VALUES (?, ?)",
                (user_id, time.time()),
            )
    except Exception:
        log.exception("stats.record_user failed")


def user_count() -> int:
    with _db() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
