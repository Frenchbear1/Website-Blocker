from datetime import datetime, timedelta

from website_blocker.pause_timer import PausePhase, format_countdown, pause_timer_state


def test_pause_timer_moves_from_countdown_to_bounded_window():
    available = datetime(2026, 8, 10, 9, 0)
    saved = available.isoformat(timespec="seconds")

    countdown = pause_timer_state(saved, 30, datetime(2026, 8, 10, 8, 55))
    assert countdown.phase == PausePhase.COUNTDOWN
    assert countdown.seconds_remaining == 300

    window = pause_timer_state(saved, 30, datetime(2026, 8, 10, 9, 10))
    assert window.phase == PausePhase.WINDOW
    assert window.seconds_remaining == 1200


def test_pause_window_relocks_at_its_exact_end():
    available = datetime(2026, 8, 10, 9, 0)
    saved = available.isoformat(timespec="seconds")
    state = pause_timer_state(saved, 30, datetime(2026, 8, 10, 9, 30))
    assert state.phase == PausePhase.EXPIRED


def test_close_bound_pause_window_stays_open_without_a_timer():
    available = datetime(2026, 8, 10, 9, 0)
    saved = available.isoformat(timespec="seconds")

    state = pause_timer_state(saved, 0, datetime(2026, 8, 20, 9, 0))

    assert state.phase == PausePhase.WINDOW
    assert state.seconds_remaining == 0
    assert state.closes_at is None


def test_next_day_deadline_is_expired_not_pauseable():
    available = datetime(2026, 8, 10, 9, 0)
    saved = available.isoformat(timespec="seconds")
    state = pause_timer_state(saved, 30, datetime(2026, 8, 11, 8, 0))
    assert state.phase == PausePhase.EXPIRED


def test_invalid_or_missing_deadlines_are_safe():
    assert pause_timer_state("", 30).phase == PausePhase.INACTIVE
    assert pause_timer_state("not-a-date", 30).phase == PausePhase.EXPIRED


def test_countdown_format_supports_minutes_hours_and_days():
    assert format_countdown(65) == "01:05"
    assert format_countdown(3661) == "1:01:01"
    assert format_countdown(90_061) == "1d 01:01:01"
