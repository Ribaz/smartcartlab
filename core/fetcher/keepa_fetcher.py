# fetcher/keepa_fetcher.py
# Fetches daily deals from the Keepa API for Amazon.it.
#
# Flow:
# 1. For each target category, search the category ID dynamically
# 2. Fetch deals for that category (max 150 per request)
# 3. For each ASIN returned, query full product details (price history, reviews)
# 4. Normalize into the standard product dict format for the scorer

from typing import Dict, List

import keepa

from config.settings import KEEPA_API_KEY

# Target categories to scan — names used to search Keepa dynamically
TARGET_CATEGORIES = [
    "Elettronica",
    "Informatica",
    "Casa e cucina",
    "Giochi e giocattoli",
    "Sport e attività all'aperto",
]

# Number of deals to fetch per category
DEALS_PER_CATEGORY = 150  # max allowed by Keepa per single request

# Keepa domain for Amazon Italy
DOMAIN = "IT"


class KeepaFetcher:

    def __init__(self):
        self.api = keepa.Keepa(KEEPA_API_KEY)

    def fetch(self) -> List[Dict]:
        """
        Fetch deals from Keepa for all target categories on Amazon.it.
        Returns a list of normalized product dicts ready for the scorer.
        """
        all_products = []

        for category_name in TARGET_CATEGORIES:
            print(f"Fetching deals for category: {category_name}")
            try:
                asins = self._fetch_asins_for_category(category_name)
                if not asins:
                    print(f"  No ASINs found for {category_name}, skipping.")
                    continue

                products = self._fetch_product_details(asins)
                all_products.extend(products)
                print(f"  Got {len(products)} products.")

            except Exception as e:
                print(f"  Error fetching {category_name}: {e}")
                continue

        print(f"Total products fetched: {len(all_products)}")
        return all_products

    def _fetch_asins_for_category(self, category_name: str) -> List[str]:
        """
        Search for category ID by name, then fetch deal ASINs for that category.
        Returns a list of ASINs.
        """
        # Step 1: find category ID
        categories = self.api.search_for_categories(category_name, domain=DOMAIN)
        if not categories:
            return []

        # Take the first matching category
        category_id = list(categories.keys())[0]

        # Step 2: fetch deals for this category
        deal_params = {
            "page": 0,
            "domainId": 8,          # 8 = Amazon Italy
            "excludeCategories": [],
            "includeCategories": [category_id],
        }
        result = self.api.deals(deal_params, domain=DOMAIN)

        if not result or "asinList" not in result:
            return []

        return result["asinList"][:DEALS_PER_CATEGORY]

    def _fetch_product_details(self, asins: List[str]) -> List[Dict]:
        """
        Query Keepa for full product details for a list of ASINs.
        Returns normalized product dicts.
        """
        if not asins:
            return []

        # Query in bulk — Keepa handles batches internally
        raw_products = self.api.query(asins, domain=DOMAIN, history=True)

        normalized = []
        for p in raw_products:
            try:
                normalized.append(self._normalize(p))
            except Exception as e:
                print(f"  Error normalizing ASIN {p.get('asin', '?')}: {e}")
                continue

        return normalized

    def _normalize(self, raw: dict) -> Dict:
        """
        Convert a raw Keepa product dict into our standard format.
        Keepa stores prices as integers (e.g. 1099 = 10.99€).
        """
        def to_eur(keepa_price) -> float | None:
            """Convert Keepa integer price to euros."""
            if keepa_price is None or keepa_price < 0:
                return None
            return round(keepa_price / 100, 2)

        def avg_price(price_array) -> float | None:
            """Calculate average from a Keepa price history array, ignoring negatives."""
            if price_array is None:
                return None
            valid = [p for p in price_array if p > 0]
            if not valid:
                return None
            return round(sum(valid) / len(valid) / 100, 2)

        data = raw.get("data", {})

        # Current price: prefer Amazon price, fallback to NEW
        current_raw = data.get("AMAZON", [None])[-1] or data.get("NEW", [None])[-1]

        # Price history arrays
        new_history = data.get("NEW", [])

        # Split history into 90d and 1y windows (approximate — Keepa timestamps)
        # Full history used for 1y avg, last quarter for 90d avg
        quarter = max(1, len(new_history) // 4)
        history_90d = new_history[-quarter:]
        history_1y = new_history

        # Reviews — Keepa stores rating as 0-50 integer (45 = 4.5 stars)
        rating_raw = data.get("RATING", [None])[-1]
        review_count_raw = data.get("COUNT_REVIEWS", [None])[-1]

        category_tree = raw.get("categoryTree") or []
        category = category_tree[-1].get("name") if category_tree else None

        review_count = (
            review_count_raw
            if review_count_raw and review_count_raw > 0
            else None
        )

        image_url = None
        if raw.get("imagesCSV"):
            first_image = raw["imagesCSV"].split(",")[0]
            image_url = (
                f"https://images-na.ssl-images-amazon.com/images/I/{first_image}"
            )

        return {
            "asin":          raw.get("asin"),
            "title":         raw.get("title"),
            "category":      category,
            "current_price": to_eur(current_raw),
            "avg_price_90d": avg_price(history_90d),
            "avg_price_1y":  avg_price(history_1y),
            "review_score":  round(rating_raw / 10, 1) if rating_raw else None,
            "review_count":  review_count,
            "image_url":     image_url,
            "product_link":  f"https://www.amazon.it/dp/{raw.get('asin')}",
            "final_score":   None,  # filled by scorer
        }
