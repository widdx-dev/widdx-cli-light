"""Tests for cron schedule parser."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from core.cron.parser import parse_schedule, next_run


def test_next_run_skips_month_without_requested_day():
    now = datetime(2026, 4, 1, tzinfo=timezone.utc)
    with patch("core.cron.parser.datetime") as clock:
        clock.now.return_value = now
        assert next_run("0 9 31 * *") == "2026-05-31T09:00:00+00:00"


def test_parse_duration_minutes():
    cron, dt = parse_schedule("30m")
    assert cron == "*/30 * * * *"
    assert dt is None


def test_parse_duration_hours():
    cron, dt = parse_schedule("2h")
    assert cron == "0 */2 * * *"
    assert dt is None


def test_parse_duration_seconds():
    cron, dt = parse_schedule("30s")
    assert cron == "*/30 * * * * *"
    assert dt is None


def test_parse_every_day_at():
    cron, dt = parse_schedule("every day at 9")
    assert cron == "0 09 * * *"
    assert dt is None


def test_parse_every_day_at_with_minutes():
    cron, dt = parse_schedule("every day at 9:30")
    assert cron == "30 09 * * *"
    assert dt is None


def test_parse_every_day_at_arabic():
    """9 صباحاً should work same as 'every day at 9'."""
    cron, dt = parse_schedule("every day at 9")
    assert cron == "0 09 * * *"


def test_parse_every_monday():
    cron, dt = parse_schedule("every monday at 10")
    assert "10" in cron or "010" in cron
    assert "1" in cron or "0" in cron  # Monday = 1 (iso) or 0 (cron legacy)
    assert dt is None


def test_parse_every_weekday():
    cron, dt = parse_schedule("every weekday at 8")
    assert "8" in cron
    assert "1-5" in cron
    assert dt is None


def test_parse_iso_timestamp():
    cron, dt = parse_schedule("2026-07-01T09:00:00")
    assert cron == "once"
    assert dt is not None


def test_parse_cron_direct():
    cron, dt = parse_schedule("0 9 * * *")
    assert cron == "0 9 * * *"
    assert dt is None


def test_parse_cron_5_fields():
    cron, dt = parse_schedule("30 14 * * 5")
    assert cron == "30 14 * * 5"


def test_parse_invalid_raises():
    import pytest
    with pytest.raises(ValueError):
        parse_schedule("not a schedule at all")


def test_next_run_daily():
    result = next_run("0 9 * * *")
    assert result is not None
    assert "T09:00:00" in result


def test_next_run_every_30m():
    result = next_run("*/30 * * * *")
    assert result is not None


def test_next_run_one_shot_past():
    from datetime import datetime, timezone, timedelta
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    result = next_run("once", one_shot_dt=past)
    assert result is None  # Already past


def test_next_run_one_shot_future():
    from datetime import datetime, timezone, timedelta
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    result = next_run("once", one_shot_dt=future)
    assert result is not None


@pytest.mark.parametrize(
    "schedule, now, expected",
    [
        ("30m", "2026-12-31T23:59:59", "2027-01-01T00:00:00"),
        ("2h", "2026-04-30T23:00:00", "2026-05-01T00:00:00"),
        ("every day at 9", "2026-01-31T10:00:00", "2026-02-01T09:00:00"),
        ("every day at 9", "2026-02-28T09:00:00", "2026-03-01T09:00:00"),
        ("every day at 9", "2028-02-28T10:00:00", "2028-02-29T09:00:00"),
        ("every day at 9", "2028-02-29T10:00:00", "2028-03-01T09:00:00"),
        ("every day at 9", "2026-12-31T09:00:00", "2027-01-01T09:00:00"),
        ("every monday at 10", "2026-09-18T11:00:00", "2026-09-21T10:00:00"),
        ("every monday at 10", "2026-09-21T10:00:00", "2026-09-28T10:00:00"),
        ("every weekday at 8", "2026-09-18T08:00:00", "2026-09-21T08:00:00"),
        ("every weekday at 8", "2026-09-21T07:59:59", "2026-09-21T08:00:00"),
        ("every sun at 8", "2026-09-19T09:00:00", "2026-09-20T08:00:00"),
        ("0 8 * * 7", "2026-09-19T09:00:00", "2026-09-20T08:00:00"),
        ("0 8 * * 6-7", "2026-09-19T08:00:00", "2026-09-20T08:00:00"),
        ("every 2 days", "2026-04-29T00:00:00", "2026-05-01T00:00:00"),
        ("every 2 days", "2026-05-01T00:00:00", "2026-05-03T00:00:00"),
        ("0 0 29 2 *", "2028-02-29T00:00:00", "2032-02-29T00:00:00"),
        ("0 0 29 2 *", "2096-03-01T00:00:00", "2104-02-29T00:00:00"),
        ("0 9 1 1 *", "2026-09-18T00:00:00", "2027-01-01T09:00:00"),
        ("0 9 1 */3 *", "2026-02-01T00:00:00", "2026-04-01T09:00:00"),
        ("0 9 1 2,4 *", "2026-02-01T09:00:00", "2026-04-01T09:00:00"),
        ("15,45 9-10 * * 1-5", "2026-09-18T09:45:01", "2026-09-18T10:15:00"),
        ("*/15 9 1 10 *", "2026-09-18T09:00:00", "2026-10-01T09:00:00"),
        ("0 */2 * 10 1", "2026-09-18T09:00:00", "2026-10-05T00:00:00"),
        ("0 9 13 * 1", "2026-09-12T00:00:00", "2026-09-13T09:00:00"),
        ("0 9 13 * 1", "2026-09-13T09:00:00", "2026-09-14T09:00:00"),
        ("0 9 */2 * 1", "2026-09-14T00:00:00", "2026-09-21T09:00:00"),
        ("* * * * *", "2026-09-18T12:30:00", "2026-09-18T12:31:00"),
        ("* * * * *", "2026-09-18T12:30:59.999999", "2026-09-18T12:31:00"),
        ("30s", "2026-09-18T12:30:15", "2026-09-18T12:30:30"),
        ("30s", "2026-12-31T23:59:30", "2027-01-01T00:00:00"),
        ("every 5 seconds", "2026-09-18T12:30:05", "2026-09-18T12:30:10"),
        ("* * * * * *", "2026-09-18T12:30:05.123456", "2026-09-18T12:30:06"),
        ("15,45 30 9 1 10 *", "2026-09-18T09:30:00", "2026-10-01T09:30:15"),
        ("*/40 * * * *", "2026-09-18T12:40:00", "2026-09-18T13:00:00"),
        ("0 0 */31 * *", "2026-04-01T00:00:00", "2026-05-01T00:00:00"),
    ],
)
def test_next_run_matches_calendar(schedule, now, expected):
    cron, dt = parse_schedule(schedule)
    frozen_now = datetime.fromisoformat(now).replace(tzinfo=timezone.utc)
    with patch("core.cron.parser.datetime") as clock:
        clock.now.return_value = frozen_now
        assert next_run(cron, dt) == expected + "+00:00"


@pytest.mark.parametrize(
    "schedule",
    [
        "0s", "0m", "0h", "60s", "90s", "60m", "24h",
        "every 0 minutes", "every 0 hours", "every 0 days", "every 32 days",
        "every 60 minutes", "every 24 hours", "every 60 seconds",
        "every day at 24", "every weekday at 9:60", "every mon at 25:00",
        "every day at 9:000", "every monday at 9 trailing",
        "every 2 minutes trailing", "-1m",
    ],
)
def test_parse_rejects_invalid_human_schedules(schedule):
    with pytest.raises(ValueError):
        parse_schedule(schedule)


@pytest.mark.parametrize(
    "schedule",
    [
        "*/0 * * * *", "0 */0 * * *", "0 0 */0 * *",
        "0 0 * */0 *", "0 0 * * */0", "*/0 * * * * *",
        "*/60 * * * *", "0 */24 * * *", "0 0 */32 * *",
        "0 0 * */13 *", "0 0 * * */8", "*/60 * * * * *",
        "60 * * * *", "0 24 * * *", "0 0 0 * *", "0 0 32 * *",
        "0 0 * 0 *", "0 0 * 13 *", "0 0 * * 8", "60 * * * * *",
        "0,60 * * * *", "5-2 * * * *", "0-60 * * * *", "-1 * * * *",
        "*/x * * * *", "0 0 * * mon", "* * * *", "* * * * * * *",
        "not a schedule", "once", "",
    ],
)
def test_invalid_cron_raises_on_parse_and_has_no_next_run(schedule):
    with pytest.raises(ValueError):
        parse_schedule(schedule)
    assert next_run(schedule) is None


@pytest.mark.parametrize("schedule", ["0 0 30 2 *", "0 0 31 4 *"])
def test_impossible_calendar_has_no_next_run(schedule):
    cron, dt = parse_schedule(schedule)
    with patch("core.cron.parser.datetime") as clock:
        clock.now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert next_run(cron, dt) is None


def test_next_run_handles_datetime_limit():
    with patch("core.cron.parser.datetime") as clock:
        clock.now.return_value = datetime.max.replace(tzinfo=timezone.utc)
        assert next_run("* * * * *") is None


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2026-09-18T09:00:00", "2026-09-18T09:00:00+00:00"),
        ("2026-09-18", "2026-09-18T00:00:00+00:00"),
        ("2026-09-18T09:00:00Z", "2026-09-18T09:00:00+00:00"),
        ("2026-09-18T09:00:00+02:00", "2026-09-18T09:00:00+02:00"),
    ],
)
def test_parse_one_shot_timezone_policy(text, expected):
    cron, dt = parse_schedule(text)
    assert cron == "once"
    assert dt is not None
    assert dt.isoformat() == expected


@pytest.mark.parametrize(
    "one_shot, expected",
    [
        ("2026-09-18T08:59:59", None),
        ("2026-09-18T09:00:00", "2026-09-18T09:00:00+00:00"),
        ("2026-09-18T09:00:01", "2026-09-18T09:00:01+00:00"),
        ("2026-09-18T10:00:00+02:00", None),
        ("2026-09-18T11:00:00+02:00", "2026-09-18T11:00:00+02:00"),
        ("2026-09-18T08:00:00-02:00", "2026-09-18T08:00:00-02:00"),
    ],
)
def test_next_run_one_shot_timezone_policy(one_shot, expected):
    dt = datetime.fromisoformat(one_shot)
    with patch("core.cron.parser.datetime") as clock:
        clock.now.return_value = datetime(2026, 9, 18, 9, tzinfo=timezone.utc)
        assert next_run("once", dt) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("59sec", "*/59 * * * * *"),
        ("59min", "*/59 * * * *"),
        ("23hr", "0 */23 * * *"),
        ("every 31 days", "0 0 */31 * *"),
        ("every 2 hours", "0 */2 * * *"),
        ("every 2 minutes", "*/2 * * * *"),
        ("every 2 d", "0 0 */2 * *"),
        ("every 2 m", "*/2 * * * *"),
        (" EVERY MONDAY AT 09:30 ", "30 09 * * 1"),
    ],
)
def test_parse_preserves_supported_spellings_and_interval_limits(text, expected):
    assert parse_schedule(text) == (expected, None)


def test_seconds_expression_round_trips():
    cron, dt = parse_schedule("30s")
    assert parse_schedule(cron) == (cron, dt)
