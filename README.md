# Smart Cart Lab 🛒

> One deal a day. The real one.

Smart Cart Lab analyzes hundreds of Amazon daily deals and selects the single best
offer of the day — or posts nothing if nothing is worth your attention.

Built in public. Documented step by step.

---

## What it does

- Fetches daily deals from Amazon via Keepa API
- Scores each product using a 5-pillar algorithm (price history, reviews, stability, appeal)
- Publishes the best deal of the day to a Telegram channel
- Generates a daily report article on WordPress

## Philosophy

Most deal channels spam dozens of posts per hour. Smart Cart Lab does the opposite:
one post per day, only when there is something genuinely worth buying.

## Built with

- Python 3
- SQLite
- Keepa API
- Telegram Bot API
- WordPress REST API

## Project status

🟡 In development — pipeline working with fake data, Keepa integration in progress.

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your credentials
4. Run: `python main.py`

To run with fake data (no API keys needed), change one line in `main.py`:
```python
from fetcher.fake_fetcher import FakeFetcher as Fetcher
```

## Follow the project

- 📱 Telegram: [Smart Cart Lab](https://t.me/smartcartlab)
- 📝 Blog: [smartcartlab.com](https://smartcartlab.com)

## Built in public

Every component of this project is documented on the blog, including architecture
decisions, experiments, and failures. If you want to replicate or fork it, everything
you need is there.

---

*Developed with the help of AI tools as part of an experiment in AI-assisted development.*
