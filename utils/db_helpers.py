# utils/db_helpers.py
# Shared database utilities.
# All database access goes through these functions.

import sqlite3
import os
from typing import List, Dict

DB_PATH = os.getenv("DB_PATH", "data/smartcartlab.db")


def get_connection() -> sqlite3.Connection:
    """Open and return a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db():
    """Create all tables if they do not exist."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            asin          TEXT NOT NULL,
            title         TEXT,
            category      TEXT,
            current_price REAL,
            avg_price_90d REAL,
            avg_price_1y  REAL,
            review_score  REAL,
            review_count  INTEGER,
            final_score   REAL,
            analyzed_at   TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_products(products: List[Dict]):
    """
    Insert a list of scored products into the products table.
    Each product dict must already contain final_score.
    """
    conn = get_connection()
    conn.executemany("""
        INSERT INTO products
            (asin, title, category, current_price, avg_price_90d,
             avg_price_1y, review_score, review_count, final_score, analyzed_at)
        VALUES
            (:asin, :title, :category, :current_price, :avg_price_90d,
             :avg_price_1y, :review_score, :review_count, :final_score, datetime('now'))
    """, products)
    conn.commit()
    conn.close()
