"""SQLite schema management for Marvel metadata."""

import sqlite3
from pathlib import Path


CURRENT_VERSION = 2

_DDL_V1 = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS series (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS issues (
    id INTEGER PRIMARY KEY,
    digital_id INTEGER,
    title TEXT NOT NULL,
    issue_number TEXT,
    description TEXT,
    modified TEXT,
    page_count INTEGER,
    detail_url TEXT NOT NULL,
    series_id INTEGER REFERENCES series(id),
    series_name TEXT,
    on_sale_date TEXT,
    unlimited_date TEXT,
    year_page INTEGER,
    cover_path TEXT,
    cover_extension TEXT
);

CREATE INDEX IF NOT EXISTS idx_issues_series_id ON issues(series_id);
CREATE INDEX IF NOT EXISTS idx_issues_year_page ON issues(year_page);
CREATE INDEX IF NOT EXISTS idx_issues_on_sale_date ON issues(on_sale_date);

CREATE TABLE IF NOT EXISTS creators (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS issue_creators (
    issue_id INTEGER NOT NULL REFERENCES issues(id),
    creator_id INTEGER NOT NULL REFERENCES creators(id),
    role TEXT NOT NULL,
    PRIMARY KEY (issue_id, creator_id, role)
);

CREATE INDEX IF NOT EXISTS idx_issue_creators_creator ON issue_creators(creator_id);
"""

_DDL_V2 = """
CREATE TABLE IF NOT EXISTS reading_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    is_curated INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reading_order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reading_order_id INTEGER NOT NULL REFERENCES reading_orders(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    issue_id INTEGER REFERENCES issues(id),
    issue_title TEXT NOT NULL,
    note TEXT DEFAULT '',
    UNIQUE(reading_order_id, position)
);

CREATE INDEX IF NOT EXISTS idx_roi_order ON reading_order_items(reading_order_id, position);
"""


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    conn.executescript(_DDL_V1)
    conn.executescript(_DDL_V2)
    _ensure_version(conn, CURRENT_VERSION)
    conn.commit()
    return conn


def _ensure_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO schema_version(version) VALUES(?)", (version,)
    )


class SchemaManager:
    CURRENT_VERSION = CURRENT_VERSION

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_version(self) -> int:
        try:
            row = self._conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
            return row[0] or 0
        except sqlite3.OperationalError:
            return 0

    def migrate(self, target_version: int | None = None) -> None:
        target = target_version or self.CURRENT_VERSION
        current = self.get_version()
        if current < 1:
            self._conn.executescript(_DDL_V1)
            _ensure_version(self._conn, 1)
        if current < 2 <= target:
            self._conn.executescript(_DDL_V2)
            _ensure_version(self._conn, 2)
        self._conn.commit()
