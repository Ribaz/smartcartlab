import logging
from datetime import datetime, timedelta

from database.db_helpers import (
    get_next_approved_post,
    is_scheduling_slot_taken,
    set_post_scheduled,
)


logger = logging.getLogger(__name__)


WEEKLY_SLOTS = {
    0: ["08:45", "12:45", "18:15"],  # lunedì
    1: ["08:45", "12:45", "18:15"],  # martedì
    2: ["08:45", "12:45", "18:15"],  # mercoledì
    3: ["08:45", "12:45", "18:15"],  # giovedì
    4: ["08:45", "12:45"],           # venerdì
}


def get_next_candidate_slot(after: datetime) -> datetime:
    """Return the first configured publication slot after the supplied datetime."""
    current_day = after.date()

    while True:
        weekday = current_day.weekday()
        day_slots = WEEKLY_SLOTS.get(weekday, [])

        for slot_time in day_slots:
            hour, minute = map(int, slot_time.split(":"))

            candidate = datetime.combine(
                current_day,
                datetime.min.time(),
            ).replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )

            if candidate > after:
                return candidate

        current_day += timedelta(days=1)


def get_next_available_slot(
    platform: str,
    after: datetime,
) -> datetime:
    """Return the first configured slot not already used by the platform."""
    candidate = get_next_candidate_slot(after)

    while True:
        candidate_str = candidate.strftime("%Y-%m-%d %H:%M:%S")

        if not is_scheduling_slot_taken(platform, candidate_str):
            return candidate

        candidate = get_next_candidate_slot(candidate)


def process_scheduling(platform: str = "mastodon"):
    """
    Select the oldest APPROVED post and assign a publication timestamp.
    Calculates the next available slot based on the last scheduled post for this platform.
    """
    logger.info(f"Phase 2 [{platform}]: Assigning publication slots to approved posts...")
    approved_post = get_next_approved_post(platform=platform)

    if not approved_post:
        logger.info(f"No APPROVED posts waiting for scheduling on platform: {platform}.")
        return

    target_slot = get_next_available_slot(
        platform=platform,
        after=datetime.now(),
    )

    slot_str = target_slot.strftime("%Y-%m-%d %H:%M:%S")

    set_post_scheduled(approved_post["id"], slot_str)
    logger.info(f"[{platform}] Post #{approved_post['id']} successfully scheduled for {slot_str}.")


    