from __future__ import annotations

import re
import subprocess
from collections import deque
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.templating import Jinja2Templates

from config.settings import APP_TIMEZONE
from database.connections import get_task_connection
from zoneinfo import ZoneInfo


app = FastAPI(title="SmartCartLab Task Dashboard")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR))
LOCAL_TZ = ZoneInfo(APP_TIMEZONE)
PROJECT_ROOT = Path("/home/enzo/dev/smartcartlab")
LOG_DIR = PROJECT_ROOT / "logs"

STATUS_VALUES = ("PENDING", "RUNNING", "COMPLETED", "FAILED")


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)


def _local_time(value: str | None) -> str:
    parsed = _parse_utc(value)
    if parsed is None:
        return "—"
    return parsed.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")


def _duration(row: dict[str, Any], now: datetime) -> str:
    if row["status"] == "PENDING":
        start = _parse_utc(row["created_at"])
        end = now
    else:
        start = _parse_utc(row.get("started_at"))
        end = (
            _parse_utc(row.get("completed_at"))
            or now
            if start
            else None
        )
    if start is None or end is None:
        return "—"

    seconds = max(0, int((end - start).total_seconds()))
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _query_tasks(
    *,
    status: str = "",
    task_type: str = "",
    limit: int | None = None,
    statuses: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []

    if status:
        clauses.append("status = ?")
        params.append(status)

    if statuses:
        placeholders = ",".join("?" for _ in statuses)
        clauses.append(f"status IN ({placeholders})")
        params.extend(statuses)

    if task_type:
        clauses.append("task_type = ?")
        params.append(task_type)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit_sql = f"LIMIT {int(limit)}" if limit else ""

    with get_task_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT id, task_type, payload, result_json, status, attempts,
                   last_error, created_at, started_at, completed_at
            FROM task_queue
            {where}
            ORDER BY id DESC
            {limit_sql}
            """,
            params,
        ).fetchall()

    return [dict(row) for row in rows]


def _queue_counts() -> dict[str, int]:
    with get_task_connection() as connection:
        rows = connection.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM task_queue
            GROUP BY status
            """
        ).fetchall()

    counts = {status: 0 for status in STATUS_VALUES}
    counts.update({row["status"]: row["count"] for row in rows})
    return counts


def _task_types() -> list[str]:
    with get_task_connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT task_type
            FROM task_queue
            ORDER BY task_type
            """
        ).fetchall()
    return [row["task_type"] for row in rows]


def _read_last_lines(path: Path, max_lines: int = 200) -> list[str]:
    if not path.exists():
        return [f"Log file not found: {path}"]

    lines: deque[str] = deque(maxlen=max_lines)
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                lines.append(line.rstrip("\n"))
    except OSError as exc:
        return [f"Unable to read log: {exc}"]

    return list(lines)


def _cron_fields_match(value: int, expression: str, minimum: int, maximum: int) -> bool:
    def match_part(part: str) -> bool:
        if "/" in part:
            base, step_text = part.split("/", 1)
            step = int(step_text)
            if base == "*":
                start = minimum
                end = maximum
            elif "-" in base:
                start_text, end_text = base.split("-", 1)
                start, end = int(start_text), int(end_text)
            else:
                start = int(base)
                end = maximum
            return start <= value <= end and (value - start) % step == 0

        if part == "*":
            return True
        if "-" in part:
            start, end = (int(x) for x in part.split("-", 1))
            return start <= value <= end
        return value == int(part)

    return any(match_part(part) for part in expression.split(","))


def _cron_matches(dt: datetime, fields: list[str]) -> bool:
    minute, hour, dom, month, dow = fields
    cron_dow = (dt.weekday() + 1) % 7

    if not _cron_fields_match(dt.minute, minute, 0, 59):
        return False
    if not _cron_fields_match(dt.hour, hour, 0, 23):
        return False
    if not _cron_fields_match(dt.month, month, 1, 12):
        return False

    dom_match = _cron_fields_match(dt.day, dom, 1, 31)
    dow_match = _cron_fields_match(cron_dow, dow, 0, 6)

    # Standard cron semantics: if both DOM and DOW are restricted,
    # either one may match.
    dom_star = dom == "*"
    dow_star = dow == "*"
    if not dom_star and not dow_star:
        return dom_match or dow_match
    return dom_match and dow_match


def _next_cron_run(schedule: str, now: datetime) -> datetime | None:
    fields = schedule.split()
    if len(fields) != 5:
        return None

    cursor = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    # One year is more than enough for the schedules used by this dashboard.
    for _ in range(366 * 24 * 60):
        if _cron_matches(cursor, fields):
            return cursor
        cursor += timedelta(minutes=1)
    return None


def _frequency_label(schedule: str) -> str:
    if schedule == "* * * * *":
        return "Every minute"
    if schedule.startswith("*/"):
        minute = schedule.split()[0]
        if minute.startswith("*/"):
            n = minute[2:]
            if n.isdigit():
                return f"Every {n} minutes"
    parts = schedule.split()
    if len(parts) == 5 and parts[0] != "*" and parts[1] == "*":
        return f"At minute {parts[0]} of every hour"
    if len(parts) == 5 and parts[0] != "*" and parts[1] != "*":
        return f"At {parts[1]}:{int(parts[0]):02d}"
    return schedule


def _parse_crontab() -> tuple[list[dict[str, Any]], str | None]:
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return [], f"Unable to execute crontab: {exc}"

    if result.returncode != 0:
        message = (result.stderr or "").strip()
        if "no crontab" in message.lower():
            return [], None
        return [], message or "Unable to read crontab."

    now = datetime.now(LOCAL_TZ)
    entries: list[dict[str, Any]] = []
    pending_comment: str | None = None

    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("#"):
            if "SmartCartLab" in line:
                pending_comment = line.lstrip("#").strip()
            continue

        fields = line.split()
        if len(fields) < 6:
            pending_comment = None
            continue

        schedule = " ".join(fields[:5])
        command = " ".join(fields[5:])

        if str(PROJECT_ROOT) not in command:
            pending_comment = None
            continue

        log_match = re.search(r">>\s*([^\s]+)\s*2>&1", command)
        log_path = Path(log_match.group(1)) if log_match else None
        if log_path and not log_path.is_absolute():
            log_path = PROJECT_ROOT / log_path

        next_run = _next_cron_run(schedule, now)
        entries.append(
            {
                "schedule": schedule,
                "frequency": _frequency_label(schedule),
                "command": command,
                "comment": pending_comment,
                "log_path": str(log_path) if log_path else "",
                "log_name": log_path.name if log_path else "—",
                "next_run": next_run.strftime("%Y-%m-%d %H:%M:%S") if next_run else "—",
            }
        )
        pending_comment = None

    return entries, None


def _decorate_tasks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    for row in rows:
        row["created_local"] = _local_time(row["created_at"])
        row["started_local"] = _local_time(row["started_at"])
        row["completed_local"] = _local_time(row["completed_at"])
        row["duration"] = _duration(row, now)
    return rows


@app.get("/")
def overview(
    request: Request,
    status: str = Query(default=""),
    task_type: str = Query(default=""),
):
    counts = _queue_counts()
    running = _decorate_tasks(
        _query_tasks(status="RUNNING", limit=1)
    )
    pending = _decorate_tasks(
        _query_tasks(status="PENDING", limit=100)
    )
    recent = _decorate_tasks(
        _query_tasks(
            status=status,
            task_type=task_type,
            limit=50,
            statuses=("COMPLETED", "FAILED"),
        )
    )
    cron_jobs, cron_error = _parse_crontab()

    return templates.TemplateResponse(
        request=request,
        name="dashboard_task.html",
        context={
            "page": "overview",
            "counts": counts,
            "running": running[0] if running else None,
            "pending": pending,
            "recent": recent,
            "task_types": _task_types(),
            "selected_status": status,
            "selected_task_type": task_type,
            "cron_jobs": cron_jobs,
            "cron_error": cron_error,
            "app_timezone": APP_TIMEZONE,
        },
        headers={"Cache-Control": "no-store"},
    )


@app.get("/tasks")
def tasks_page(
    request: Request,
    status: str = Query(default=""),
    task_type: str = Query(default=""),
):
    tasks = _decorate_tasks(
        _query_tasks(status=status, task_type=task_type, limit=200)
    )
    return templates.TemplateResponse(
        request=request,
        name="dashboard_task.html",
        context={
            "page": "tasks",
            "tasks": tasks,
            "task_types": _task_types(),
            "selected_status": status,
            "selected_task_type": task_type,
            "app_timezone": APP_TIMEZONE,
        },
        headers={"Cache-Control": "no-store"},
    )


@app.get("/logs")
def logs_page(
    request: Request,
    log: str = Query(default=""),
):
    cron_jobs, cron_error = _parse_crontab()
    log_options = []
    selected_path = ""

    for job in cron_jobs:
        path = job["log_path"]
        if path and path not in {x["path"] for x in log_options}:
            log_options.append({"path": path, "name": job["log_name"]})

    allowed_paths = {x["path"] for x in log_options}
    if log in allowed_paths:
        selected_path = log
    elif log_options:
        selected_path = log_options[0]["path"]

    lines = _read_last_lines(Path(selected_path), 200) if selected_path else []

    return templates.TemplateResponse(
        request=request,
        name="dashboard_task.html",
        context={
            "page": "logs",
            "log_options": log_options,
            "selected_log": selected_path,
            "log_lines": lines,
            "cron_error": cron_error,
            "app_timezone": APP_TIMEZONE,
        },
        headers={"Cache-Control": "no-store"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "tasks_dashboard.dashboard_task:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )