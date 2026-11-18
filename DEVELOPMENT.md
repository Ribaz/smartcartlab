# SmartCartLab Code Style

## General

* All source code must be written in English.
* Italian is allowed only for user-facing text (social posts, Telegram messages, dashboard labels, etc.).
* Write code for humans first, AI second.

## Files

* Every file starts with:

  1. project-relative path
  2. short module description

Example:

```python
# social/scheduling.py
# Calculates publication slots for approved social posts.
```

Each module should have one clear responsibility.

## Naming

* `snake_case` → files, variables, functions
* `PascalCase` → classes
* `UPPER_SNAKE_CASE` → constants
* private helpers start with `_`

Choose descriptive names.

## Imports

Order imports as:

1. Python standard library
2. Third-party libraries
3. Project modules

Separate groups with one blank line.

Avoid wildcard imports.

## Functions

* Use type hints.
* Add docstrings only when they improve understanding.
* Prefer small, focused functions.
* Avoid wrapper functions that add no value.
* Prefer early returns over nested `if` blocks.

## Comments

Comments explain **why**, not **what**.

Avoid decorative separators.

Keep comments short and in English.

## Logging

Use the standard `logging` module.

Prefer:

```python
logger.info("Created post #%s.", post_id)
```

instead of:

```python
logger.info(f"Created post #{post_id}.")
```

## Datetime

* Store timestamps in UTC.
* Convert to local timezone only for user interaction.

## Architecture

* `config/` → settings and `.env` loading
* `database/` → SQLite access for the deal, social, and task databases
* `integrations/` → external services
* `core/` → deal pipeline: fetch, score, publish
* `social/` → social manager workflow
* `jobs/` → one-shot entry points that queue work or run one social step
* `tasks/` → handlers for a single queued task
* `social_dashboard/` and `tasks_dashboard/` → FastAPI review and operations UI

`main.py` only orchestrates the deal pipeline. Each file in `jobs/` only
orchestrates one social or queue step. Task handlers do the work. Dashboards
call the same modules for review actions.

## Tooling

Ruff is configured in `pyproject.toml`: line length 100, Python 3.12, lint
rules E, F, and I. `social/copywriter.py` ignores E501 because its prompts are
long string literals.

Local AI assistant folders (`.cursor/`, `.claude/`, and similar) are gitignored.

## Commits

One logical change per commit.

Behavior-changing refactoring and code cleanup should be separate commits.
