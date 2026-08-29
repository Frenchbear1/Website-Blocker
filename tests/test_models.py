from datetime import datetime

from lumaguard.models import ScheduleRule, TimeLimitRule


def test_schedule_within_same_day():
    rule = ScheduleRule(days=[0], start="09:00", end="17:00")
    assert rule.is_active(datetime(2026, 8, 10, 12, 0))
    assert not rule.is_active(datetime(2026, 8, 10, 18, 0))


def test_overnight_schedule_uses_previous_day_after_midnight():
    rule = ScheduleRule(days=[0], start="21:00", end="07:00")
    assert rule.is_active(datetime(2026, 8, 10, 23, 0))
    assert rule.is_active(datetime(2026, 8, 11, 2, 0))
    assert not rule.is_active(datetime(2026, 8, 11, 8, 0))


def test_disabled_schedule_never_runs():
    rule = ScheduleRule(enabled=False, days=list(range(7)), start="00:00", end="23:59")
    assert not rule.is_active(datetime(2026, 8, 10, 12, 0))


def test_time_limit_active_days_and_allowance():
    rule = TimeLimitRule(days=[0, 2, 4], daily_minutes=45)
    assert rule.is_active_day(datetime(2026, 8, 10, 12, 0))
    assert not rule.is_active_day(datetime(2026, 8, 11, 12, 0))
    assert rule.allowance_seconds == 2700


def test_time_limit_from_dict_sanitizes_values():
    rule = TimeLimitRule.from_dict(
        {"target_type": "unknown", "enforcement": "destroy", "daily_minutes": 5000, "days": [0, 0, 8]}
    )
    assert rule.target_type == "app"
    assert rule.enforcement == "warn"
    assert rule.daily_minutes == 1440
    assert rule.days == [0]
