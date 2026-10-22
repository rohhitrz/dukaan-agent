"""SQLite access. One file, created from data/seed.sql on first run."""

import logging
import sqlite3

from app.config import settings

log = logging.getLogger(__name__)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    # Rows come back as mappings instead of tuples, so queries read like dicts.
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(force: bool = False) -> None:
    """Create the DB from the seed file if it doesn't exist (or if force=True)."""
    if settings.db_path.exists() and not force:
        log.info("db already present at %s", settings.db_path)
        return

    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    sql = settings.seed_path.read_text()
    with connect() as conn:
        conn.executescript(sql)
    log.info("seeded db at %s", settings.db_path)
