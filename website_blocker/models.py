from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, time
from typing import Any
from uuid import uuid4


@dataclass
class ScheduleRule:
    name: str = "Evening protection"
    days: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    start: str = "21:00"
    end: str = "07:00"
    enabled: bool = True
    profile_id: str = "strong"
    id: str = field(default_factory=lambda: uuid4().hex)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScheduleRule":
        allowed = {key: data[key] for key in cls.__dataclass_fields__ if key in data}
        return cls(**allowed)

    def is_active(self, moment: datetime | None = None) -> bool:
        if not self.enabled:
            return False
        moment = moment or datetime.now()
        start = time.fromisoformat(self.start)
        end = time.fromisoformat(self.end)
        now_time = moment.time().replace(second=0, microsecond=0)
        weekday = moment.weekday()
        if start <= end:
            return weekday in self.days and start <= now_time < end
        if now_time >= start:
            return weekday in self.days
        previous_day = (weekday - 1) % 7
        return previous_day in self.days and now_time < end


@dataclass
class TimeLimitRule:
    name: str = "New time limit"
    target_type: str = "app"
    target: str = ""
    display_name: str = ""
    daily_minutes: int = 60
    days: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    enabled: bool = True
    enforcement: str = "warn"
    warning_minutes: int = 5
    id: str = field(default_factory=lambda: uuid4().hex)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimeLimitRule":
        allowed = {key: data[key] for key in cls.__dataclass_fields__ if key in data}
        rule = cls(**allowed)
        rule.target_type = rule.target_type if rule.target_type in ("app", "website") else "app"
        rule.enforcement = rule.enforcement if rule.enforcement in ("warn", "block") else "warn"
        try:
            rule.daily_minutes = max(1, min(1440, int(rule.daily_minutes)))
        except (TypeError, ValueError):
            rule.daily_minutes = 60
        try:
            rule.warning_minutes = max(0, min(60, int(rule.warning_minutes)))
        except (TypeError, ValueError):
            rule.warning_minutes = 5
        days: set[int] = set()
        for day in rule.days if isinstance(rule.days, (list, tuple, set)) else []:
            try:
                number = int(day)
            except (TypeError, ValueError):
                continue
            if 0 <= number <= 6:
                days.add(number)
        rule.days = sorted(days)
        rule.target = str(rule.target).strip().lower()
        return rule

    def is_active_day(self, moment: datetime | None = None) -> bool:
        moment = moment or datetime.now()
        return self.enabled and moment.weekday() in self.days

    @property
    def allowance_seconds(self) -> int:
        return self.daily_minutes * 60


@dataclass
class AppSettings:
    protection_enabled: bool = False
    active_profile: str = "strong"
    custom_dns_primary: str = ""
    custom_dns_secondary: str = ""
    blocked_domains: list[str] = field(default_factory=list)
    allowed_domains: list[str] = field(default_factory=list)
    schedules: list[ScheduleRule] = field(default_factory=list)
    schedule_enabled: bool = False
    launch_at_startup: bool = False
    minimize_to_tray: bool = True
    notifications: bool = True
    theme: str = "dark"
    accent: str = "violet"
    pin_salt: str = ""
    pin_hash: str = ""
    lock_enabled: bool = False
    cooldown_minutes: int = 0
    pause_available_at: str = ""
    pause_window_minutes: int = 30
    limits_enabled: bool = True
    screen_usage_enabled: bool = False
    time_limits: list[TimeLimitRule] = field(default_factory=list)
    schedule_owns_protection: bool = False
    blocked_today: int = 0
    last_counter_date: str = ""
    first_run: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        allowed = {key: data[key] for key in cls.__dataclass_fields__ if key in data}
        allowed["schedules"] = [ScheduleRule.from_dict(item) for item in data.get("schedules", [])]
        allowed["time_limits"] = [
            TimeLimitRule.from_dict(item) for item in data.get("time_limits", []) if isinstance(item, dict)
        ]
        return cls(**allowed)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FilterResult:
    success: bool
    message: str
    detail: str = ""


@dataclass
class EventRecord:
    kind: str
    title: str
    detail: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventRecord":
        return cls(
            kind=str(data.get("kind", "info")),
            title=str(data.get("title", "Event")),
            detail=str(data.get("detail", "")),
            timestamp=str(data.get("timestamp", datetime.now().isoformat(timespec="seconds"))),
        )


@dataclass(frozen=True)
class ScreenUsageEntry:
    target_type: str
    target_id: str
    display_name: str
    seconds: int
    source_app: str = ""
