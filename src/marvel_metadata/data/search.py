"""FTS5 full-text search setup."""

import sqlite3


def setup_fts(conn: sqlite3.Connection, rebuild: bool = False) -> bool:
    """Create or rebuild the issues_fts FTS5 virtual table.

    Returns True if the table was created/rebuilt, False if already existed.
    """
    if rebuild:
        conn.execute("DROP TABLE IF EXISTS issues_fts")

    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='issues_fts'"
    ).fetchone()

    if exists and not rebuild:
        return False

    conn.executescript("""
        CREATE VIRTUAL TABLE IF NOT EXISTS issues_fts USING fts5(
            title,
            content=issues,
            content_rowid=id
        );

        INSERT INTO issues_fts(issues_fts) VALUES('rebuild');
    """)
    conn.commit()
    return True
