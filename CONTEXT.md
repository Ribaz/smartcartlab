# Smart Cart Lab — AI Context File

> Paste this file at the start of any AI chat session to provide full project context.
> Last updated: after full refactor.

---

## What is this project?

Smart Cart Lab is an automated system that analyzes hundreds of Amazon daily deals
and selects the single best offer of the day, publishing it to a Telegram channel
and generating a daily report article on a WordPress blog.

The philosophy: quality over quantity. One deal per day — or none if nothing is worth it.

---

## Goals

- Primary: build a working, documented project to showcase technical and AI skills
- Secondary: generate affiliate revenue via Amazon Associates (when account is active)
- Tertiary: grow a Telegram channel and blog audience organically

---

## Stack

| Layer | Technology |
|---|---|
| Language | Python 3 |
| Database | SQLite (`smartcartlab.db`) |
| Data source | Keepa API (currently using FakeFetcher for development) |
| Messaging | Telegram Bot API (via raw requests, no SDK) |
| Blog | WordPress REST API (smartcartlab.com on Altervista) |
| Hosting | MiniPC (always-on, local), Docker planned |
| AI usage | Planned for text generation — not yet implemented |

---

## Architecture principles

1. **Alias import pattern**: each component is imported with `as` alias in `main.py`.
   To swap a component, change one word — nothing else. Example:
   `from core.fetcher.fake_fetcher import FakeFetcher as Fetcher`
2. **English only**: all code, variable names, function names, comments in English.
   Italian only in generated output text (posts, reports).
3. **Single orchestrator**: `main.py` is the only entry point.
4. **No abstract base classes**: contract is implicit — every implementation must have
   the expected methods. Python validates at runtime.
5. **Credentials in .env**: `settings.py` is safe to commit — it only holds config
   values. Credentials are read via `os.getenv()` and never hardcoded.

---

## Project structure

```
smartcartlab/
├── config/
│   └── settings.py            # project config — safe to commit
├── data/
│   └── smartcartlab.db        # SQLite database (excluded from git)
├── fetcher/
│   ├── fake_fetcher.py        # generates fake data for development (active)
│   └── keepa_fetcher.py       # Keepa API implementation (TODO)
├── scorer/
│   └── pillar_scorer.py       # 5-pillar scoring algorithm
├── publisher/
│   ├── telegram_publisher.py  # posts to Telegram channel
│   └── wordpress_publisher.py # creates report post on WordPress
├── utils/
│   └── db_helpers.py          # all DB access goes here
├── main.py                    # orchestrator — only entry point
├── CONTEXT.md                 # this file
├── README.md                  # GitHub project page
├── .env                       # credentials (excluded from git)
├── .gitignore
└── requirements.txt
```

---

## Database schema (`smartcartlab.db`)

### Single table: `products`

All data in one table — raw product data and final score together.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | auto-increment |
| asin | TEXT | Amazon product ID |
| title | TEXT | product title |
| category | TEXT | Amazon category |
| current_price | REAL | price at time of analysis |
| avg_price_90d | REAL | 90-day average price |
| avg_price_1y | REAL | 1-year average price |
| review_score | REAL | average star rating |
| review_count | INTEGER | number of reviews |
| final_score | REAL | weighted score from pillar algorithm |
| analyzed_at | TEXT | ISO timestamp |

No separate scores or daily_picks tables — the DB is a daily working structure,
not a permanent archive. The log lives on Telegram and WordPress.

---

## Scoring algorithm — 5 pillars

| Pillar | Weight | Description |
|---|---|---|
| 1+2 | 35% | Price lower than 90d and 1y historical average |
| 3 | 25% | Minimum 4.0 stars with at least 50 reviews |
| 4 | 20% | Offer expected to last the full day (no flash deals) |
| 5 | 20% | Product has broad mass appeal (not niche audience) |

Configured in `config/settings.py`: `MIN_REVIEW_SCORE`, `MIN_REVIEW_COUNT`.
Weights defined as `WEIGHTS` dict in `scorer/pillar_scorer.py`.

---

## Publishing flow

1. `main.py` runs (scheduled, e.g. 8:00 AM)
2. Fetcher pulls deals → list of product dicts in memory
3. Scorer assigns `final_score` to each product in memory
4. All products saved to DB in one shot (`save_products`)
5. `pick_best()` selects winner (or returns None if nothing qualifies)
6. Telegram publisher posts deal or "no deal today" message
7. WordPress publisher creates daily report article

---

## How to swap components (alias pattern)

```python
# main.py — change only the import line

# Development (no API needed):
from core.fetcher.fake_fetcher import FakeFetcher as Fetcher

# Production (Keepa API):
from core.fetcher.keepa_fetcher import KeepaFetcher as Fetcher

# Same pattern for scorer:
from core.scorer.pillar_scorer import PillarScorer as Scorer
```

---

## Key conventions for code generation

- All identifiers in English
- Single table: `products`
- Database file: `smartcartlab.db` (path in `config/settings.py` as `DB_PATH`)
- Credentials never hardcoded — always `os.getenv()` via `config.settings`
- No abstract base classes
- `requests` library for all HTTP calls (Telegram, WordPress) — no SDKs
