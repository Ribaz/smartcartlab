# main.py
# Smart Cart Lab — main orchestrator.
# Run this file to execute the full daily pipeline.
# To swap a component, change the import below — nothing else needs to change.

# To swap the data source, change only this line:
from datetime import datetime

from core.fetcher.fake_fetcher import FakeFetcher as Fetcher
from core.publisher.telegram_publisher import TelegramPublisher

# To swap the scoring algorithm, change only this line:
from core.scorer.pillar_scorer import PillarScorer as Scorer
from database.products import save_products
from database.schema_core import initialize_db


# --- Color helpers (ANSI codes, no external libraries) ---
def log_info(msg):    print(f"\033[97m{msg}\033[0m")   #white
def log_success(msg): print(f"\033[92m✓ {msg}\033[0m") #green
def log_warning(msg): print(f"\033[93m⚠ {msg}\033[0m") #yellow
def log_error(msg):   print(f"\033[91m✗ {msg}\033[0m") #red

fetcher = Fetcher()
scorer = Scorer()

publishers = [
    TelegramPublisher(),
    #WordPressPublisher(),
]


def run():
    
    log_success(f"[{datetime.now()}] Smart Cart Lab pipeline starting...")

    # Step 1: initialize database (creates tables if they do not exist)
    initialize_db()

    # Step 2: fetch deals
    log_info("Fetching deals...")
    products = fetcher.fetch()
    log_success(f"Fetched {len(products)} products.")

    # Step 3: score all products in memory
    log_info("Scoring products...")
    for product in products:
        product["final_score"] = scorer.score(product)

    # Step 4: save everything to DB in one shot
    save_products(products)

    # Step 5: pick the best
    best = scorer.pick_best(products)

    if best is None:
        log_warning("No qualifying deal found today.")
    else:
        log_success(f"Best deal: {best.get('title')} (score: {best.get('final_score'):.2f})")

    # Step 6: publish (deal or no-deal message)
    for publisher in publishers:
        platform = publisher.__class__.__name__.replace("Publisher", "").lower()
        log_warning(f"Publishing to {platform}.")
        
        try:
            success = publisher.publish(best)
            if success:
                log_success(f"Published to {platform}.")
            else:
                log_error(f"Failed to publish to {platform}.")
        except Exception as e:
            log_error(f"Error publishing to {platform}: {e}")

    log_success(f"[{datetime.now()}] Pipeline complete.")


if __name__ == "__main__":
    run()
