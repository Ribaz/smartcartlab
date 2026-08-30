from __future__ import annotations

import os
import sqlite3

from config.settings import DB_PATH, SOCIAL_DB_PATH

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _open_connection(path: str) -> sqlite3.Connection:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_connection() -> sqlite3.Connection:
    """Open and return a connection to the primary SQLite database."""
    return _open_connection(DB_PATH)


def get_social_connection() -> sqlite3.Connection:
    """Open and return a connection to the Social Manager SQLite database."""
    return _open_connection(SOCIAL_DB_PATH)