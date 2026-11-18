# Smart Cart Lab 🛒

> One deal a day. The real one.

Smart Cart Lab analyzes Amazon daily deals and selects the single best
offer of the day — or posts nothing if nothing is worth your attention.
The same repository turns the blog into reviewed, scheduled social posts.

Built in public. Documented step by step.

---

## What it does

Daily deals:

- Fetches deals. The active source is fake data; a Keepa fetcher for Amazon.it is in the tree
- Scores each product with a 5-pillar algorithm
- Saves the run to SQLite
- Publishes the best deal, or a no-deal message, to a Telegram channel

Social manager:

- Reads new articles from the WordPress RSS feed
- Asks a local Ollama model for topics, social copy, and image prompts
- Generates images with a local image-generator CLI
- Reviews, schedules, and publishes posts to Mastodon and Facebook
- Notifies a Telegram admin chat when a post goes out

Two local dashboards cover the social review queue and the background task queue.

## Philosophy

Most deal channels spam dozens of posts per hour. Smart Cart Lab does the opposite:
one post per day, only when there is something genuinely worth buying.

## Built with

- Python 3.12
- SQLite (deals, social content, and the task queue)
- Keepa API
- Telegram Bot API over HTTP
- WordPress RSS
- Ollama
- Mastodon and the Facebook Graph API
- FastAPI

## Project status

🟡 In development.

The deal run uses fake products. Price history, offer stability, and popularity
scoring are still placeholders, and each Telegram deal message carries a test
disclaimer. The social pipeline is wired through ingest, queue, generate, review,
schedule, and publish.

## Setup

From the repository root:

1. Install dependencies: `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in the credentials you use
3. Run the deal pipeline: `python main.py`

`main.py` imports `FakeFetcher`. To use Keepa, change that import to:

```python
from core.fetcher.keepa_fetcher import KeepaFetcher as Fetcher
```

Social jobs, each safe to run on its own:

```text
python -m jobs.ingest_blog_articles
python -m jobs.generate_article_topics
python -m jobs.generate_image_prompts
python -m jobs.generate_social_posts
python -m jobs.generate_images
python -m jobs.process_task_queue
python -m jobs.schedule_social_posts
python -m jobs.publish_social_posts
```

Dashboards:

```text
python -m social_dashboard.dashboard_social
python -m tasks_dashboard.dashboard_task
```

The social dashboard listens on port 8000. The task dashboard listens on port 8001.

## Follow the project

- 📱 Telegram: [Smart Cart Lab](https://t.me/smartcartlab)
- 📝 Blog: [smartcartlab.com](https://smartcartlab.com)

## Built in public

Every component of this project is documented on the blog, including architecture
decisions, experiments, and failures. If you want to replicate or fork it, everything
you need is there.

---

*Developed with the help of AI tools as part of an experiment in AI-assisted development.*
