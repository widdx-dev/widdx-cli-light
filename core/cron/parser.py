"""Parse human-readable schedules into cron expressions."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional


def _cron_fields(cron_expr: str) -> list[set[int]]:
    parts = cron_expr.split()
    if len(parts) == 5:
        parts.insert(0, "0")
    if len(parts) != 6:
        raise ValueError("Expected five cron fields or six with seconds first")

    fields = []
    for part, (minimum, maximum) in zip(
        parts, ((0, 59), (0, 59), (0, 23), (1, 31), (1, 12), (0, 7))
    ):
        if part == "*":
            values = set(range(minimum, maximum + 1))
        elif re.fullmatch(r"\*/\d+", part):
            interval = int(part[2:])
            if not 1 <= interval <= maximum:
                raise ValueError(f"Invalid cron interval: {part!r}")
            values = set(range(minimum, maximum + 1, interval))
        elif re.fullmatch(r"\d+-\d+", part):
            start, end = map(int, part.split("-"))
            if not minimum <= start <= end <= maximum:
                raise ValueError(f"Invalid cron range: {part!r}")
            values = set(range(start, end + 1))
        elif re.fullmatch(r"\d+(?:,\d+)*", part):
            values = {int(value) for value in part.split(",")}
        else:
            raise ValueError(f"Invalid cron field: {part!r}")
        if not all(minimum <= value <= maximum for value in values):
            raise ValueError(f"Cron field out of range: {part!r}")
        fields.append(values)
    fields[-1] = {value % 7 for value in fields[-1]}
    return fields


def _recurring(cron_expr: str) -> tuple[str, Optional[datetime]]:
    _cron_fields(cron_expr)
    return cron_expr, None


def _aware_datetime(value: datetime) -> datetime:
    if value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def parse_schedule(text: str) -> tuple[str, Optional[datetime]]:
    """Return (cron, None) or ("once", datetime); naive timestamps mean UTC.

    Five-field cron uses minute resolution; six-field cron starts with seconds.
    Intervals must be positive and no larger than the field's maximum value.
    """
    text = text.strip().lower()

    try:
        dt = datetime.fromisoformat(text.upper().replace("Z", "+00:00"))
        return "once", _aware_datetime(dt)
    except (ValueError, TypeError):
        pass

    m = re.fullmatch(r"(\d+)\s*(m|min|h|hr|s|sec)", text)
    if not m:
        m = re.fullmatch(
            r"every\s+(\d+)\s*(minutes?|min|m|hours?|hr|h|days?|d|seconds?|sec|s)",
            text,
        )
    if m:
        value = int(m.group(1))
        unit = m.group(2)
        if unit.startswith("s"):
            return _recurring(f"*/{value} * * * * *")
        if unit.startswith("m"):
            return _recurring(f"*/{value} * * * *")
        if unit.startswith("h"):
            return _recurring(f"0 */{value} * * *")
        return _recurring(f"0 0 */{value} * *")

    m = re.fullmatch(r"every\s+day\s+at\s+(\d{1,2})(?::(\d{2}))?", text)
    if m:
        hour = m.group(1).zfill(2)
        minute = m.group(2) or "0"
        return _recurring(f"{minute} {hour} * * *")

    m = re.fullmatch(r"every\s+weekday\s+at\s+(\d{1,2})(?::(\d{2}))?", text)
    if m:
        hour = m.group(1).zfill(2)
        minute = m.group(2) or "0"
        return _recurring(f"{minute} {hour} * * 1-5")

    day_map = {
        "sunday": 0, "monday": 1, "tuesday": 2, "wednesday": 3,
        "thursday": 4, "friday": 5, "saturday": 6,
        "sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6,
    }
    for name, num in day_map.items():
        pattern = rf"every\s+{name}\s+at\s+(\d{{1,2}})(?::(\d{{2}}))?"
        m = re.fullmatch(pattern, text)
        if m:
            hour = m.group(1).zfill(2)
            minute = m.group(2) or "0"
            return _recurring(f"{minute} {hour} * * {num}")

    if len(text.split()) in (5, 6):
        return _recurring(text)

    raise ValueError(f"Unrecognized schedule: {text!r}")


def next_cron_run(cron_expr: str) -> Optional[str]:
    """Return the first matching UTC instant strictly after now, or None.

    Restricted day-of-month and weekday fields match either day (cron OR).
    A wildcard or wildcard step in either day field requires both to match.
    Invalid schedules and dates impossible within a Gregorian cycle return None.
    """
    try:
        seconds, minutes, hours, days, months, weekdays = _cron_fields(cron_expr)
    except ValueError:
        return None

    parts = cron_expr.split()
    match_both_days = parts[-3].startswith("*") or parts[-1].startswith("*")
    now = datetime.now(timezone.utc)
    try:
        candidate = now.replace(microsecond=0) + timedelta(seconds=1)
        while candidate.year <= min(now.year + 400, 9999):
            if candidate.month not in months:
                candidate = (candidate.replace(day=1) + timedelta(days=32)).replace(
                    day=1, hour=0, minute=0, second=0
                )
                continue

            day_matches = candidate.day in days
            weekday_matches = (candidate.weekday() + 1) % 7 in weekdays
            if match_both_days:
                matches = day_matches and weekday_matches
            else:
                matches = day_matches or weekday_matches
            if not matches:
                candidate = (candidate + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0
                )
                continue
            if candidate.hour not in hours:
                candidate = (candidate + timedelta(hours=1)).replace(minute=0, second=0)
                continue
            if candidate.minute not in minutes:
                candidate = (candidate + timedelta(minutes=1)).replace(second=0)
                continue
            if candidate.second not in seconds:
                candidate += timedelta(seconds=1)
                continue
            return candidate.isoformat()
    except (ValueError, OverflowError):
        return None
    return None


def next_run(schedule: str, one_shot_dt: Optional[datetime] = None) -> Optional[str]:
    """Calculate the next run, treating naive one-shot datetimes as UTC."""
    if one_shot_dt is not None:
        one_shot_dt = _aware_datetime(one_shot_dt)
        if one_shot_dt < datetime.now(timezone.utc):
            return None
        return one_shot_dt.isoformat()
    return next_cron_run(schedule)
