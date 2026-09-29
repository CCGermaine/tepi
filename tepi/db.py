import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE progress (
    word_id TEXT PRIMARY KEY,
    introduced_on TEXT NOT NULL,
    due TEXT,
    interval_index INTEGER NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('in_play', 'settled')),
    deck_index INTEGER NOT NULL
);
CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    day TEXT NOT NULL,
    word_id TEXT NOT NULL REFERENCES progress(word_id),
    kind TEXT NOT NULL CHECK (kind IN ('introduced', 'revealed', 'known', 'fuzzy', 'missed'))
);
CREATE TABLE plans (
    day TEXT PRIMARY KEY,
    reviews TEXT NOT NULL,
    introduced TEXT NOT NULL
);
CREATE INDEX events_day ON events(day);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version == 0 and _empty(conn):
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
    elif version not in (0, 1):
        raise sqlite3.DatabaseError(f"This log uses schema {version}, which this Tepi does not read.")
    elif version == 0:
        raise sqlite3.DatabaseError(f"The log at {path} is not a Tepi database.")
    return conn


def _empty(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchone()
    return row[0] == 0
