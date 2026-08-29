from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from database.connections import get_connection


# ---------------------------------------------------------------------------
# SmartCartLab Core DB
# ---------------------------------------------------------------------------


def initialize_db():
    """Create primary tables if they do not exist."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                asin           TEXT NOT NULL,
                title          TEXT,
                category       TEXT,
                current_price  REAL,
                avg_price_90d  REAL,
                avg_price_1y   REAL,
                review_score   REAL,
                review_count   INTEGER,
                final_score    REAL,
                analyzed_at    TEXT
            )
            """
        )