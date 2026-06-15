# fetcher/fake_fetcher.py
# Fake data fetcher for development and testing purposes.
# Generates realistic but completely fictional product data.
# No API keys or internet connection required.
#
# To use instead of KeepaFetcher, change one line in main.py:
#   from fetcher.fake_fetcher import FakeFetcher as Fetcher

import random
from typing import List, Dict


# Fake product pool — realistic names and categories
PRODUCTS = [
    ("Logitech MX Master 3S", "Informatica"),
    ("Samsung Galaxy Buds2 Pro", "Elettronica"),
    ("Philips Airfryer XL", "Casa e cucina"),
    ("Sony WH-1000XM5", "Elettronica"),
    ("Bosch Trapano a Percussione", "Fai da te"),
    ("Kindle Paperwhite 2023", "Elettronica"),
    ("De'Longhi Nespresso Vertuo", "Casa e cucina"),
    ("Razer DeathAdder V3", "Informatica"),
    ("iRobot Roomba i5", "Casa e cucina"),
    ("Jabra Evolve2 55", "Elettronica"),
    ("Apple AirTag 4 Pack", "Elettronica"),
    ("Lego Technic Ferrari", "Giochi e giocattoli"),
    ("Garmin Forerunner 265", "Sport"),
    ("Tefal Bistecchiera OptiGrill", "Casa e cucina"),
    ("Kingston NV2 SSD 1TB", "Informatica"),
    ("Oral-B iO Series 7", "Salute"),
    ("Corsair K70 RGB", "Informatica"),
    ("Instant Pot Duo 7-in-1", "Casa e cucina"),
    ("GoPro Hero12 Black", "Elettronica"),
    ("Fitbit Charge 6", "Sport"),
]

NUM_PRODUCTS = random.randint(50, 100)


class FakeFetcher:

    def fetch(self) -> List[Dict]:
        """
        Generate a list of fake products that mimics the output of KeepaFetcher.
        Returns between 50 and 100 fictional products.
        """
        products = [self._generate_product() for _ in range(NUM_PRODUCTS)]
        print(f"FakeFetcher: generated {len(products)} fake products.")
        return products

    def _generate_product(self) -> Dict:
        """Generate a single fake product with realistic price and review data."""
        name, category = random.choice(PRODUCTS)

        # Generate a realistic price history
        base_price  = round(random.uniform(20.0, 400.0), 2)
        avg_1y      = round(base_price * random.uniform(0.9, 1.4), 2)
        avg_90d     = round(avg_1y * random.uniform(0.85, 1.15), 2)

        # Current price: sometimes a real deal, sometimes not
        current_price = round(avg_90d * random.uniform(0.5, 1.05), 2)

        # Reviews: mix of good and mediocre products
        review_score = round(random.uniform(2.5, 5.0), 1)
        review_count = random.randint(5, 8000)

        # Unique suffix to simulate different products from the same brand
        asin = f"B{random.randint(10000000, 99999999):08d}"

        return {
            "asin":          asin,
            "title":         f"{name} [{asin[-4:]}]",
            "category":      category,
            "current_price": current_price,
            "avg_price_90d": avg_90d,
            "avg_price_1y":  avg_1y,
            "review_score":  review_score,
            "review_count":  review_count,
            "image_url":     None,
            "product_link":  f"https://www.amazon.it/dp/{asin}",
            "final_score":   None,
        }
