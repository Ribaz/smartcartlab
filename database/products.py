from typing import Dict, List

from database.connections import get_connection


def save_products(products: List[Dict]):
    """Insert scored products into the products table."""
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO products
                (asin, title, category, current_price, avg_price_90d,
                 avg_price_1y, review_score, review_count, final_score, analyzed_at)
            VALUES
                (:asin, :title, :category, :current_price, :avg_price_90d,
                 :avg_price_1y, :review_score, :review_count, :final_score, datetime('now'))
            """,
            products,
        )