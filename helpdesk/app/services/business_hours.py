"""Business hours SLA calculation utilities.

Only count working hours (9am-6pm, Mon-Fri) towards SLA time.
Weekends and outside-hours are excluded from the timer.
"""

from datetime import datetime, timedelta, time, date, timezone

BUSINESS_START = time(9, 0)    # 9:00 AM
BUSINESS_END = time(18, 0)     # 6:00 PM
WEEKEND_DAYS = {5, 6}          # Saturday=5, Sunday=6


def is_business_hour(dt: datetime) -> bool:
    """Check if dt falls within business hours (9am-6pm Mon-Fri)."""
    if dt.weekday() in WEEKEND_DAYS:
        return False
    return BUSINESS_START <= dt.time() < BUSINESS_END


def next_business_start(dt: datetime) -> datetime:
    """Return the next business hour start at or after dt."""
    # If during business hours, return dt as-is
    if is_business_hour(dt):
        return dt

    # If after business hours on a weekday (6pm+), next day 9am
    if dt.weekday() not in WEEKEND_DAYS and dt.time() >= BUSINESS_END:
        next_dt = dt.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    # If before business hours on a weekday (before 9am)
    elif dt.weekday() not in WEEKEND_DAYS and dt.time() < BUSINESS_START:
        next_dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
    # Weekend — advance to Monday 9am
    else:
        if dt.weekday() == 5:       # Saturday
            days_ahead = 2
        elif dt.weekday() == 6:     # Sunday
            days_ahead = 1
        else:
            days_ahead = (7 - dt.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
        next_dt = (dt + timedelta(days=days_ahead)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )

    return next_dt


def next_business_end(dt: datetime) -> datetime:
    """Return the next business day end at or after dt."""
    candidate = next_business_start(dt)
    return candidate.replace(hour=18, minute=0, second=0, microsecond=0)


def business_minutes_between(start: datetime, end: datetime) -> int:
    """
    Calculate the number of business-minutes between two datetimes.
    Only counts time within 9am-6pm Mon-Fri.
    Uses incremental day-by-day approach to correctly handle weekends.
    """
    if start >= end:
        return 0

    total_minutes = 0
    current = next_business_start(start)

    while current < end:
        # Skip weekends
        if current.weekday() in WEEKEND_DAYS:
            current = (current + timedelta(days=1)).replace(
                hour=9, minute=0, second=0, microsecond=0
            )
            continue

        # Calculate business minutes for this day
        day_start = max(current, current.replace(
            hour=BUSINESS_START.hour, minute=BUSINESS_START.minute,
            second=0, microsecond=0
        ))
        day_end = min(end, current.replace(
            hour=BUSINESS_END.hour, minute=BUSINESS_END.minute,
            second=0, microsecond=0
        ))

        if day_start < day_end:
            diff_seconds = (day_end - day_start).total_seconds()
            total_minutes += diff_seconds / 60

        # Move to next day at 9am
        current = (current + timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )

    return int(total_minutes)


def add_business_minutes(start: datetime, minutes: int) -> datetime:
    """
    Add a number of business-minutes to a start datetime.
    Returns the resulting datetime (skipping weekends/off-hours).
    """
    if minutes <= 0:
        return start

    remaining = minutes
    current = next_business_start(start)

    while remaining > 0:
        # Skip weekends
        if current.weekday() in WEEKEND_DAYS:
            current = (current + timedelta(days=1)).replace(
                hour=9, minute=0, second=0, microsecond=0
            )
            continue

        # Calculate remaining business minutes today
        end_of_day = current.replace(
            hour=BUSINESS_END.hour, minute=BUSINESS_END.minute,
            second=0, microsecond=0
        )
        available_today = int((end_of_day - current).total_seconds() / 60)

        if available_today >= remaining:
            # Fits within today's remaining business hours
            current += timedelta(minutes=remaining)
            remaining = 0
        else:
            # Consume rest of today and continue tomorrow
            remaining -= available_today
            # Jump to end of business day, then advance to next day 9am
            current = end_of_day

    return current


def get_elapsed_business_minutes(created_at: datetime, paused_mins: int = 0,
                                 paused_at: datetime = None) -> int:
    """
    Calculate elapsed business minutes from ticket creation to now,
    accounting for SLA pauses.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if paused_at:
        elapsed = business_minutes_between(created_at, paused_at)
    else:
        elapsed = business_minutes_between(created_at, now)

    elapsed -= paused_mins
    return max(0, int(elapsed))


def get_remaining_business_minutes(created_at: datetime, total_minutes: int,
                                   paused_mins: int = 0,
                                   paused_at: datetime = None) -> int:
    """Calculate remaining business minutes before SLA expiry."""
    elapsed = get_elapsed_business_minutes(created_at, paused_mins, paused_at)
    remaining = total_minutes - elapsed
    return max(0, int(remaining))


def get_sla_percent(created_at: datetime, total_minutes: int,
                    paused_mins: int = 0,
                    paused_at: datetime = None) -> int:
    """Calculate SLA percentage elapsed (business hours aware)."""
    if total_minutes <= 0:
        return 100
    elapsed = get_elapsed_business_minutes(created_at, paused_mins, paused_at)
    pct = (elapsed / total_minutes) * 100
    return min(100, int(pct))


def is_sla_breached(created_at: datetime, total_minutes: int,
                    paused_mins: int = 0,
                    paused_at: datetime = None) -> bool:
    """Check if SLA is breached (business hours aware)."""
    if created_at is None or total_minutes is None or total_minutes <= 0:
        return False
    elapsed = get_elapsed_business_minutes(created_at, paused_mins, paused_at)
    return elapsed >= total_minutes
