from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class PausePhase(str, Enum):
    INACTIVE = "inactive"
    COUNTDOWN = "countdown"
    WINDOW = "window"
    EXPIRED = "expired"


@dataclass(frozen=True)
class PauseTimerState:
    phase: PausePhase
    seconds_remaining: int = 0
    available_at: datetime | None = None
    closes_at: datetime | None = None


def pause_timer_state(
    pause_available_at: str,
    window_minutes: int,
    now: datetime | None = None,
) -> PauseTimerState:
    if not pause_available_at:
        return PauseTimerState(PausePhase.INACTIVE)
    now = now or datetime.now()
    try:
        available = datetime.fromisoformat(pause_available_at)
    except ValueError:
        return PauseTimerState(PausePhase.EXPIRED)
    close_bound = int(window_minutes) == 0
    closes = None if close_bound else available + timedelta(minutes=max(1, int(window_minutes)))
    if now < available:
        seconds = max(1, math.ceil((available - now).total_seconds()))
        return PauseTimerState(PausePhase.COUNTDOWN, seconds, available, closes)
    if close_bound:
        return PauseTimerState(PausePhase.WINDOW, 0, available, None)
    assert closes is not None
    if now < closes:
        seconds = max(1, math.ceil((closes - now).total_seconds()))
        return PauseTimerState(PausePhase.WINDOW, seconds, available, closes)
    return PauseTimerState(PausePhase.EXPIRED, 0, available, closes)


def format_countdown(seconds: int) -> str:
    seconds = max(0, int(seconds))
    days, remainder = divmod(seconds, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, seconds = divmod(remainder, 60)
    if days:
        return f"{days}d {hours:02}:{minutes:02}:{seconds:02}"
    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"
    return f"{minutes:02}:{seconds:02}"
