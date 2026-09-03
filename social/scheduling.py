import logging
import math
import random
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from config.settings import APP_TIMEZONE
from database.posts import (
    get_approved_unscheduled_posts,
    get_platform_scheduling_activity,
    is_scheduling_slot_taken,
    set_post_scheduled,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scheduling policy
# ---------------------------------------------------------------------------

WEEKLY_SLOTS = {
    0: ["08:45", "12:45", "18:15"],  # Monday
    1: ["08:45", "12:45", "18:15"],  # Tuesday
    2: ["08:45", "12:45", "18:15"],  # Wednesday
    3: ["08:45", "12:45", "18:15"],  # Thursday
    4: ["08:45", "12:45", "18:15"],  # Friday
    5: ["10:30", "16:00"],            # Saturday
    6: ["10:30", "16:00"],            # Sunday
}

# Base preference for each weekday.
# These are preferences, not hard restrictions.
WEEKDAY_SCORES = {
    0: 62,  # Monday
    1: 86,  # Tuesday
    2: 90,  # Wednesday
    3: 90,  # Thursday
    4: 56,  # Friday
    5: 38,  # Saturday
    6: 34,  # Sunday
}

MIN_SPACING_HOURS = 24
MAX_SPACING_HOURS = 72
PREFERRED_SPACING_HOURS = 36
CANDIDATE_WINDOW_DAYS = 10
RECENT_TIME_HISTORY = 5

# Higher values make the random choice more varied.
# Lower values make it more deterministic.
RANDOM_TEMPERATURE = 12.0

LOCAL_TIMEZONE = ZoneInfo(APP_TIMEZONE)
UTC = timezone.utc
DB_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _parse_db_datetime(value: str | None) -> datetime | None:
    """Parse a UTC timestamp stored in the social database."""
    if not value:
        return None

    try:
        parsed = datetime.strptime(value, DB_DATETIME_FORMAT)
    except ValueError:
        return None

    return parsed.replace(tzinfo=UTC)


def _activity_datetime(row) -> datetime | None:
    """Return the timestamp that represents an existing platform activity."""
    if row["status"] == "PUBLISHED":
        return (
            _parse_db_datetime(row["published_at"])
            or _parse_db_datetime(row["scheduled_at"])
        )

    return _parse_db_datetime(row["scheduled_at"])


# ---------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------

def _generate_candidate_slots(
    after: datetime,
    days: int = CANDIDATE_WINDOW_DAYS,
) -> list[datetime]:
    """Generate all configured local slots in the candidate window."""
    if after.tzinfo is None:
        raise ValueError("Expected a timezone-aware datetime.")

    local_after = after.astimezone(LOCAL_TIMEZONE)
    candidates: list[datetime] = []

    start_day = local_after.date()
    end_day = start_day + timedelta(days=days)

    current_day = start_day

    while current_day <= end_day:
        for slot_time in WEEKLY_SLOTS.get(current_day.weekday(), []):
            hour, minute = map(int, slot_time.split(":"))

            candidate = datetime(
                year=current_day.year,
                month=current_day.month,
                day=current_day.day,
                hour=hour,
                minute=minute,
                tzinfo=LOCAL_TIMEZONE,
            )

            if candidate > local_after:
                candidates.append(candidate)

        current_day += timedelta(days=1)

    return candidates


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_spacing(hours_from_previous: float) -> float:
    if hours_from_previous < 24:
        return -1000

    if hours_from_previous < 36:
        return 4

    if hours_from_previous < 48:
        return 14

    if hours_from_previous < 60:
        return 22

    if hours_from_previous < 72:
        return 14

    return 0


def _score_day_and_time(candidate: datetime) -> float:
    """Apply editorial preferences for particular weekday/time combinations."""
    weekday = candidate.weekday()
    hour = candidate.hour

    score = float(WEEKDAY_SCORES[weekday])

    # Monday: afternoon/evening is preferable to early morning.
    if weekday == 0:
        if hour < 12:
            score -= 22
        elif hour >= 17:
            score += 12
        else:
            score += 5

    # Tuesday to Thursday: lunch and late afternoon are slightly preferred,
    # but morning remains perfectly valid.
    elif weekday in (1, 2, 3):
        if 11 <= hour < 16:
            score += 7
        elif hour >= 17:
            score += 4

    # Friday evening is deliberately discouraged, not forbidden.
    elif weekday == 4:
        if hour >= 17:
            score -= 25
        elif 11 <= hour < 16:
            score += 5

    # Weekend remains possible. Sunday afternoon gets a small preference
    # over Sunday morning.
    elif weekday == 6 and hour >= 14:
        score += 8

    return score


def _score_time_variety(
    candidate: datetime,
    recent_activity: list[datetime],
) -> float:
    """Penalize repeated use of the same publication time."""
    if not recent_activity:
        return 0

    candidate_time = candidate.strftime("%H:%M")
    recent_times = [
        item.astimezone(LOCAL_TIMEZONE).strftime("%H:%M")
        for item in recent_activity[-RECENT_TIME_HISTORY:]
    ]

    occurrences = recent_times.count(candidate_time)

    if occurrences == 0:
        return 8

    if occurrences == 1:
        return -5

    if occurrences == 2:
        return -14

    return -24


def _score_candidate(
    candidate: datetime,
    previous_activity: datetime,
    recent_activity: list[datetime],
) -> float:
    hours_from_previous = (
        candidate.astimezone(UTC) - previous_activity.astimezone(UTC)
    ).total_seconds() / 3600

    score = _score_day_and_time(candidate)
    score += _score_spacing(hours_from_previous)
    score += _score_time_variety(candidate, recent_activity)

    return score


# ---------------------------------------------------------------------------
# Weighted selection
# ---------------------------------------------------------------------------

def _weighted_candidate_choice(
    scored_candidates: list[tuple[datetime, float]],
) -> datetime:
    """
    Choose a candidate probabilistically.

    Better candidates are substantially more likely to win, but the choice
    is intentionally not deterministic.
    """
    if not scored_candidates:
        raise ValueError("Cannot choose from an empty candidate list.")

    best_score = max(score for _, score in scored_candidates)

    weights = [
        math.exp((score - best_score) / RANDOM_TEMPERATURE)
        for _, score in scored_candidates
    ]

    candidates = [candidate for candidate, _ in scored_candidates]

    return random.choices(
        population=candidates,
        weights=weights,
        k=1,
    )[0]


# ---------------------------------------------------------------------------
# Slot selection
# ---------------------------------------------------------------------------

def get_smart_scheduling_slot(
    platform: str,
    after: datetime,
    activity: list[datetime],
) -> datetime:
    """
    Choose a sensible future publication slot for one platform.

    Guardrails:
    - maximum one post per local calendar day;
    - minimum 36 hours between platform posts;
    - exact DB slot must still be free.

    All other editorial rules are expressed as scoring preferences.
    """
    if after.tzinfo is None:
        raise ValueError("Expected a timezone-aware datetime.")

    previous_activity = max(activity) if activity else after.astimezone(UTC)

    # Never schedule relative to a point in the past when the platform
    # already has future content.
    scheduling_anchor = max(
        after.astimezone(UTC),
        previous_activity.astimezone(UTC),
    )

    earliest_allowed = scheduling_anchor + timedelta(
        hours=MIN_SPACING_HOURS
    )

    latest_allowed = scheduling_anchor + timedelta(
        hours=MAX_SPACING_HOURS
    )

    occupied_local_days: set[date] = {
        item.astimezone(LOCAL_TIMEZONE).date()
        for item in activity
    }

    candidates = _generate_candidate_slots(
        after=earliest_allowed - timedelta(seconds=1),
    )

    valid_candidates: list[datetime] = []

    for candidate in candidates:
        candidate_utc = candidate.astimezone(UTC)

        if candidate_utc > latest_allowed:
            continue

        if candidate.date() in occupied_local_days:
            continue

        candidate_str = candidate_utc.strftime(DB_DATETIME_FORMAT)

        if is_scheduling_slot_taken(platform, candidate_str):
            continue

        valid_candidates.append(candidate)

    # If the normal window becomes saturated, expand it.
    if not valid_candidates:
        raise RuntimeError(
            f"No valid scheduling slot found for '{platform}' "
            f"between {MIN_SPACING_HOURS}h and {MAX_SPACING_HOURS}h "
            f"after the latest scheduled activity."
        )


    recent_activity = sorted(activity)

    scored_candidates = [
        (
            candidate,
            _score_candidate(
                candidate=candidate,
                previous_activity=scheduling_anchor,
                recent_activity=recent_activity,
            ),
        )
        for candidate in valid_candidates
    ]

    selected = _weighted_candidate_choice(scored_candidates)

    logger.info(
        "[%s] Selected smart slot %s from %d candidates.",
        platform,
        selected.isoformat(),
        len(scored_candidates),
    )

    return selected


# ---------------------------------------------------------------------------
# Scheduling process
# ---------------------------------------------------------------------------

def process_scheduling(platform: str = "mastodon") -> None:
    """
    Schedule every APPROVED unscheduled post for a platform.

    Each newly assigned slot immediately becomes part of the platform
    activity considered while scheduling the remaining backlog.
    """
    logger.info(
        "Phase 2 [%s]: Assigning publication slots to approved posts...",
        platform,
    )

    approved_posts = get_approved_unscheduled_posts(platform=platform)

    if not approved_posts:
        logger.info(
            "No APPROVED posts waiting for scheduling on platform: %s.",
            platform,
        )
        return

    db_activity = get_platform_scheduling_activity(platform)

    activity: list[datetime] = []

    for row in db_activity:
        event_at = _activity_datetime(row)

        if event_at:
            activity.append(event_at)

    now = datetime.now(UTC)

    scheduled_count = 0

    for approved_post in approved_posts:
        target_slot = get_smart_scheduling_slot(
            platform=platform,
            after=now,
            activity=activity,
        )

        target_utc = target_slot.astimezone(UTC)
        slot_str = target_utc.strftime(DB_DATETIME_FORMAT)

        set_post_scheduled(
            approved_post["id"],
            slot_str,
        )

        # Important: the next post scheduled during this same run must see
        # this newly assigned slot immediately.
        activity.append(target_utc)

        scheduled_count += 1

        logger.info(
            "[%s] Post #%s scheduled for %s local (%s UTC).",
            platform,
            approved_post["id"],
            target_slot.strftime("%Y-%m-%d %H:%M"),
            slot_str,
        )

    logger.info(
        "[%s] Scheduling completed: %d post(s) assigned.",
        platform,
        scheduled_count,
    )