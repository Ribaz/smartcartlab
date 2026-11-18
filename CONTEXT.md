# Smart Cart Lab — AI Context File

> Paste this file at the start of any AI chat session to provide full project context.
> Last updated: aligned with the current code.

---

## What is this project?

Smart Cart Lab has two pipelines in one repository.

The deal pipeline analyzes Amazon daily deals and selects the single best offer
of the day, then posts it to a Telegram channel. The active fetcher is fake data.
A Keepa fetcher for Amazon.it exists and is not the import used by `main.py`.

The social pipeline reads the WordPress blog, generates topics, posts, and images,
then reviews, schedules, and publishes them to Mastodon and Facebook.

The philosophy of the deal channel: quality over quantity. One deal per day — or
none if nothing is worth it.

---

## Goals

- Primary: build a working, documented project to showcase technical and AI skills
- Secondary: generate affiliate revenue via Amazon Associates (when account is active)
- Tertiary: grow a Telegram channel and blog audience organically

---

## Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 (`pyproject.toml` Ruff target) |
| Databases | SQLite: `data/smartcartlab.db`, `data/socialmanager.db`, `data/taskmanager.db` |
| Deal source | `FakeFetcher` in `main.py`. `KeepaFetcher` calls the Keepa API for Amazon.it |
| Deal copy | Local Ollama (`OLLAMA_URL`, `OLLAMA_MODEL`, default `gemma3:4b`) |
| Deal delivery | Telegram Bot API via `requests` |
| Blog intake | WordPress RSS (`urllib`), Italian feed by default |
| Social copy and prompts | Ollama through `integrations/ollama.py` |
| Images | Local `image-generator` CLI, sibling project |
| Social delivery | Mastodon API and Facebook Graph API, via `requests` |
| Review UI | FastAPI + Jinja2. Social dashboard port 8000, task dashboard port 8001 |
| Schedule display | `Europe/Rome` (`APP_TIMEZONE` in `config/settings.py`) |

`requirements.txt` lists `keepa`, `requests`, `fastapi`, `uvicorn`, and `jinja2`.
Telegram goes through the Bot API with `requests`.

---

## Architecture principles

1. **Alias import for the deal pipeline**: `main.py` imports the fetcher and scorer
   with `as`. Swap an implementation by changing that import.
2. **English only**: code, identifiers, and comments in English.
   Italian is for user-facing text (posts, Telegram messages, dashboard labels).
3. **Thin entry points**: `main.py` orchestrates the deal run. Each file in `jobs/`
   orchestrates one social or queue step. `tasks/` executes one queued task.
4. **No abstract base classes**: the expected methods are the contract.
5. **Credentials in .env**: `config/settings.py` loads `.env` from the repo root
   and reads secrets with `os.getenv()`. It is safe to commit.
6. **Three databases**: deals, social content, and the task queue stay separate.
   Connections live in `database/connections.py`.

---

## Project structure

```
smartcartlab/
├── config/settings.py
├── main.py                         # deal pipeline only
├── core/
│   ├── fetcher/                    # fake_fetcher.py, keepa_fetcher.py
│   ├── scorer/pillar_scorer.py
│   └── publisher/                  # telegram_publisher.py, wordpress_publisher.py
├── database/                       # connections, schemas, table helpers
├── integrations/                   # ollama, telegram, wordpress, mastodon,
│                                   # facebook, local_image_generator
├── social/                         # ingest, topics, copy, images, schedule, publish
├── jobs/                           # one-shot entry points
├── tasks/                          # queued task handlers
├── social_dashboard/               # review UI, port 8000
├── tasks_dashboard/                # queue, cron, logs UI, port 8001
├── CONTEXT.md
├── DEVELOPMENT.md
├── README.md
├── requirements.txt
├── pyproject.toml
├── .env.example
└── data/                           # SQLite files, gitignored
```

There is no `main_social_pipeline.py`. Social work is the `jobs/` modules.
The task dashboard reads the machine crontab and the `logs/` directory.
Its project root is the repository that contains `tasks_dashboard/`, taken
from the module path. A cron line is listed when its command contains that path.

---

## Databases

Paths default in `config/settings.py` and can be overridden with `DB_PATH`,
`SOCIAL_DB_PATH`, and `TASK_DB_PATH`.

### `smartcartlab.db` — table `products`

One table for the deal run. Raw fields and `final_score` live together.
`save_products()` appends rows; it does not replace the previous run.

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | auto-increment |
| asin | TEXT | Amazon product ID |
| title | TEXT | product title |
| category | TEXT | Amazon category |
| current_price | REAL | price at analysis time |
| avg_price_90d | REAL | 90-day average price |
| avg_price_1y | REAL | 1-year average price |
| review_score | REAL | average star rating |
| review_count | INTEGER | number of reviews |
| final_score | REAL | weighted pillar score |
| analyzed_at | TEXT | set with `datetime('now')` on insert |

### `socialmanager.db`

| Table | Role |
|---|---|
| `blog_articles` | RSS articles. `processing_status` defaults to `NEW`. Allowed values also include `QUEUED`, `GENERATED`, and `FAILED`; the jobs leave rows at `NEW`. |
| `article_topics` | Editorial topics for an article. The topic job aims for 3 per article. |
| `social_posts` | One generated post per topic and platform, plus custom posts from the dashboard. Status: `PENDING`, `APPROVED`, `REJECTED`, `PUBLISHED`. |
| `image_prompts` | One prompt per topic (unique on `topic_id`). |
| `generated_images` | Files produced for a prompt. `social_posts.image_id` points here. |

### `taskmanager.db` — table `task_queue`

| Column | Role |
|---|---|
| task_type | `GENERATE_ARTICLE_TOPIC`, `GENERATE_SOCIAL_POST`, `GENERATE_IMAGE_PROMPT`, `GENERATE_IMAGE` |
| payload / result_json | JSON |
| status | `PENDING`, `RUNNING`, `COMPLETED`, `FAILED` |
| attempts / last_error | claim increments attempts; failure stores the error |
| created_at / started_at / completed_at | UTC timestamps, `YYYY-MM-DD HH:MM:SS` |

The worker claims at most one task, and only when none is `RUNNING`.

---

## Deal pipeline

`python main.py`:

1. `initialize_db()`
2. `Fetcher.fetch()` — `FakeFetcher` unless the import is changed
3. `PillarScorer.score()` on each product, in memory
4. `save_products()`
5. `pick_best()` — requires `review_score >= 4.0`, `review_count >= 50`, and `final_score > 0`. Otherwise no deal.
6. `TelegramPublisher.publish()`. `WordPressPublisher` exists and is commented out of the publisher list. It is not called.

`TelegramPublisher` asks Ollama for an Italian channel message and appends a
test disclaimer. Fake product titles are Italian. The no-deal message is Italian.

`KeepaFetcher` scans Amazon.it categories (electronics, computers, home, toys,
sports), up to 150 deals per category, then loads product details.

### Scoring — 5 pillars

Weights in `core/scorer/pillar_scorer.py`. Thresholds in `config/settings.py`.

| Pillar | Weight | Current behaviour |
|---|---|---|
| 1+2 price | 35% | Placeholder. `_score_price()` returns `0.0`. |
| 3 reviews | 25% | Implemented. Below the minimum stars or review count scores `0.0`. |
| 4 stability | 20% | Placeholder. Returns `0.5` until flash deals are detected. |
| 5 popularity | 20% | Placeholder. Returns `0.5` until category or sales rank is used. |

`PUBLISH_HOUR = 8` is defined in settings and is not read by `main.py`.

---

## Social pipeline

Run each job from the repository root with `python -m jobs.<module>`.
Nothing in the repo chains them. Order that matches the data:

1. `ingest_blog_articles` — latest 10 Italian RSS posts. New rows are inserted; known ids are skipped.
2. `generate_article_topics` — queues `GENERATE_ARTICLE_TOPIC` until the article has 3 topics. Skips empty content and articles that already have an active task.
3. `generate_image_prompts` — queues `GENERATE_IMAGE_PROMPT` for topics with no prompt.
4. `generate_social_posts` — queues `GENERATE_SOCIAL_POST` for each topic on `facebook` and `mastodon`.
5. `generate_images` — queues at most one `GENERATE_IMAGE` per run, and none if that type is already active. Default image is 512×512, quality `standard`.
6. `process_task_queue` — runs one pending task.
7. Review in the social dashboard. Generated posts start as `PENDING`. Approve, reject, edit, regenerate, or publish now.
8. `schedule_social_posts` — gives each approved, unscheduled post a slot in `Europe/Rome`. Window is 10 days. Minimum gap on a platform is 24 hours, preferred gap is 36 hours, weekday and time preferences bias the choice.
9. `publish_social_posts` — publishes due `APPROVED` posts. A missing linked image skips the post. Success marks `PUBLISHED` and notifies `TELEGRAM_ADMIN_CHAT_ID`. Failure leaves the post `APPROVED`.

Ollama generation for topics, posts, and prompts goes through `integrations/ollama.py`.
The deal Telegram copy calls Ollama directly from `TelegramPublisher`.

Images are produced by `LOCAL_IMAGE_GENERATOR_PATH`. The default is
`../image-generator/generate` next to this repo, resolved from the project
root. Files are resolved under `IMAGE_OUTPUT_ROOT`, the sibling
`image-generator/output` directory.

RSS URLs: `{WORDPRESS_URL}/feed/` for Italian, `{WORDPRESS_URL}/en/feed/` for English.
Ingestion calls the Italian feed.

---

## Dashboards

`python -m social_dashboard.dashboard_social` — entities, review, calendar,
manual post creation, reschedule, and publish-now. Host `0.0.0.0`, port 8000.

`python -m tasks_dashboard.dashboard_task` — queue counts, task list, crontab,
and log tails. Host `0.0.0.0`, port 8001.

---

## Credentials

Set in `.env`. `settings.py` only fills a variable when it is not already set.

| Variable | Used for |
|---|---|
| `KEEPA_API_KEY` | Keepa fetcher |
| `TELEGRAM_BOT_TOKEN` | channel posts and admin notices |
| `TELEGRAM_CHANNEL_ID` | daily deal destination |
| `TELEGRAM_ADMIN_CHAT_ID` | notice after a social post is published. Not in `.env.example`. |
| `WORDPRESS_URL` | RSS base URL. Also used by the unused REST publisher. |
| `WORDPRESS_USER`, `WORDPRESS_APP_PASSWORD` | `WordPressPublisher` only |
| `OLLAMA_URL`, `OLLAMA_MODEL` | local generation |
| `MASTODON_API_BASE_URL`, `MASTODON_ACCESS_TOKEN` | Mastodon |
| `FACEBOOK_PAGE_ID`, `FACEBOOK_ACCESS_TOKEN` | Facebook Page |
| `LOCAL_IMAGE_GENERATOR_PATH` | image CLI. Optional; defaults to the sibling `../image-generator/generate` |
| `DB_PATH`, `SOCIAL_DB_PATH`, `TASK_DB_PATH` | optional database paths |

---

## Conventions for code generation

- Identifiers, comments, docstrings, and log messages in English
- Italian only in user-facing copy
- Credentials through `config.settings`, never hardcoded
- No abstract base classes
- Persist through `database/` helpers
- Talk to external services through `integrations/`
- A new social background step is a job that enqueues work, plus a task handler
- Store timestamps in UTC. Convert to `Europe/Rome` for display and scheduling slots
- Ruff: line length 100, rules E, F, and I. `social/copywriter.py` ignores E501
