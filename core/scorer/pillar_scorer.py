# scorer/pillar_scorer.py
# Scores products using the 5-pillar algorithm defined in CONTEXT.md.
# Each pillar returns a score between 0.0 and 1.0.
# The final score is a weighted average of all pillars.
#
# To swap the algorithm, create a new scorer class with score() and pick_best()
# and change only the import line in main.py.

from typing import Dict, List

from config.settings import MIN_REVIEW_COUNT, MIN_REVIEW_SCORE

# Pillar weights — must sum to 1.0
WEIGHTS = {
    "price": 0.35,       # pillars 1+2: price vs history
    "review": 0.25,      # pillar 3: review quality
    "stability": 0.20,   # pillar 4: offer expected to last the day
    "popularity": 0.20,  # pillar 5: broad mass appeal
}


class PillarScorer:

    def score(self, product: Dict) -> float:
        """
        Score a single product and return its final score (0.0 to 1.0).
        Called for each product individually in main.py.
        """
        price = self._score_price(product)
        review = self._score_reviews(product)
        stability = self._score_stability(product)
        popularity = self._score_popularity(product)

        return (
            price      * WEIGHTS["price"]
            + review   * WEIGHTS["review"]
            + stability * WEIGHTS["stability"]
            + popularity * WEIGHTS["popularity"]
        )

    def pick_best(self, products: List[Dict]) -> Dict | None:
        """
        Return the highest-scoring product that meets minimum thresholds.
        Returns None if no product qualifies — no deal posted today.
        """
        qualified = [
            p for p in products
            if p.get("review_score", 0) >= MIN_REVIEW_SCORE
            and p.get("review_count", 0) >= MIN_REVIEW_COUNT
            and p.get("final_score", 0) > 0
        ]
        if not qualified:
            return None
        return max(qualified, key=lambda p: p["final_score"])

    # --- Private scoring methods ---

    def _score_price(self, product: Dict) -> float:
        """
        Pillars 1+2: how good is the current price vs historical averages?
        TODO: implement — compare current_price vs avg_price_90d and avg_price_1y.
        TODO: add inflation adjustment.
        """
        return 0.0

    def _score_reviews(self, product: Dict) -> float:
        """
        Pillar 3: review quality gate.
        Returns 0.0 if product does not meet minimum thresholds.
        """
        if product.get("review_count", 0) < MIN_REVIEW_COUNT:
            return 0.0
        if product.get("review_score", 0) < MIN_REVIEW_SCORE:
            return 0.0
        return (product["review_score"] - MIN_REVIEW_SCORE) / (5.0 - MIN_REVIEW_SCORE)

    def _score_stability(self, product: Dict) -> float:
        """
        Pillar 4: is this offer likely to last the full day?
        TODO: use Keepa price history to detect flash-deal patterns.
        """
        return 0.5  # neutral default until implemented

    def _score_popularity(self, product: Dict) -> float:
        """
        Pillar 5: does this product have broad mass appeal?
        TODO: implement using category or sales rank.
        """
        return 0.5  # neutral default until implemented
