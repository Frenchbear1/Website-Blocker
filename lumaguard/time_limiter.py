from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .constants import ACCENTS
from .domains import normalize_domain
from .models import AppSettings, ScreenUsageEntry, TimeLimitRule
from .storage import UsageStore
from .win_activity import WindowsApp, foreground_app, request_close


BROWSER_EXECUTABLES = {
    "brave.exe": "brave",
    "chrome.exe": "chrome",
    "firefox.exe": "firefox",
    "msedge.exe": "edge",
    "opera.exe": "opera",
    "vivaldi.exe": "vivaldi",
}

SCREEN_USAGE_IGNORED_EXECUTABLES = {
    "applicationframehost.exe",
    "ctfmon.exe",
    "dwm.exe",
    "lockapp.exe",
    "lumaguard.exe",
    "python.exe",
    "pythonw.exe",
    "searchhost.exe",
    "shellexperiencehost.exe",
    "sihost.exe",
    "startmenuexperiencehost.exe",
    "textinputhost.exe",
}

APP_DISPLAY_NAMES = {
    "brave.exe": "Brave",
    "chrome.exe": "Google Chrome",
    "code.exe": "Visual Studio Code",
    "explorer.exe": "File Explorer",
    "firefox.exe": "Firefox",
    "msedge.exe": "Microsoft Edge",
    "notepad.exe": "Notepad",
    "opera.exe": "Opera",
    "powerpnt.exe": "Microsoft PowerPoint",
    "vivaldi.exe": "Vivaldi",
    "winword.exe": "Microsoft Word",
}


def _is_lumaguard_executable(value: str) -> bool:
    filename = Path(value.strip().lower()).name
    return filename.startswith("lumaguard") and filename.endswith(".exe")


class TimeLimitEngine(QObject):
    usage_changed = Signal()
    limit_event = Signal(str, str, str, int)
    site_detected = Signal(str)

    def __init__(
        self,
        settings_provider: Callable[[], AppSettings],
        usage_store: UsageStore,
        preview: bool = False,
        app_provider: Callable[[], WindowsApp | None] = foreground_app,
        close_request: Callable[[int], bool] = request_close,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._settings_provider = settings_provider
        self.store = usage_store
        self.preview = preview
        self._app_provider = app_provider
        self._close_request = close_request
        self._lock = threading.RLock()
        self._pending: dict[tuple[str, str], int] = {}
        self._screen_pending: dict[tuple[str, int, str, str, str, str], int] = {}
        self._web_seen: dict[tuple[str, str], float] = {}
        self._screen_web_seen: dict[tuple[str, str], float] = {}
        self._companion_seen: dict[str, float] = {}
        self._recorded_sites: set[str] = set(self.store.recent_sites(200))
        self._warned: set[tuple[str, str]] = set()
        self._limited_notified: set[tuple[str, str]] = set()
        self._last_close: dict[str, float] = {}
        self._ticks_since_flush = 0

    @staticmethod
    def _today() -> str:
        return date.today().isoformat()

    @staticmethod
    def browser_executable_names() -> set[str]:
        return set(BROWSER_EXECUTABLES)

    def _rules(self) -> list[TimeLimitRule]:
        settings = self._settings_provider()
        return settings.time_limits if settings.limits_enabled else []

    def used_seconds(self, rule_id: str, day: str | None = None) -> int:
        day_key = day or self._today()
        stored = self.store.seconds_for_rule(rule_id, day_key)
        with self._lock:
            return stored + self._pending.get((day_key, rule_id), 0)

    def usage_map(self) -> dict[str, int]:
        rule_ids = [rule.id for rule in self._settings_provider().time_limits]
        values = self.store.seconds_for_rules(rule_ids, self._today())
        with self._lock:
            for rule_id in rule_ids:
                values[rule_id] = values.get(rule_id, 0) + self._pending.get((self._today(), rule_id), 0)
        return values

    def total_seconds_today(self) -> int:
        total = self.store.total_seconds(self._today())
        with self._lock:
            total += sum(value for (day_key, _rule_id), value in self._pending.items() if day_key == self._today())
        return total

    def reset_usage(self, rule_id: str, day: str | None = None) -> None:
        """Reset one rule without disturbing any other limit or historical day."""
        day_key = day or self._today()
        with self._lock:
            self._pending.pop((day_key, rule_id), None)
            self._warned.discard((day_key, rule_id))
            self._limited_notified.discard((day_key, rule_id))
            self._last_close.pop(rule_id, None)
            self.store.reset_rule_usage(rule_id, day_key)
        self.usage_changed.emit()

    def _add_seconds(self, rule_id: str, seconds: int) -> None:
        amount = max(0, int(seconds))
        if amount == 0:
            return
        key = (self._today(), rule_id)
        with self._lock:
            self._pending[key] = self._pending.get(key, 0) + amount

    def _add_screen_seconds(
        self,
        target_type: str,
        target_id: str,
        display_name: str,
        seconds: int,
        moment: datetime | None = None,
        source_app: str = "",
    ) -> None:
        amount = max(0, int(seconds))
        if amount == 0:
            return
        recorded_at = moment or datetime.now()
        key = (
            recorded_at.date().isoformat(),
            recorded_at.hour,
            target_type,
            target_id.strip().lower(),
            display_name.strip(),
            source_app.strip(),
        )
        with self._lock:
            self._screen_pending[key] = self._screen_pending.get(key, 0) + amount

    @staticmethod
    def _screen_app_name(app: WindowsApp) -> str:
        return APP_DISPLAY_NAMES.get(app.executable_name.lower(), app.display_name.strip() or app.executable_name)

    @staticmethod
    def _is_screen_app(app: WindowsApp) -> bool:
        executable_name = app.executable_name.strip().lower()
        return bool(
            executable_name
            and executable_name not in SCREEN_USAGE_IGNORED_EXECUTABLES
            and not _is_lumaguard_executable(executable_name)
        )

    @staticmethod
    def _matching_app_rule(rules: list[TimeLimitRule], app: WindowsApp) -> TimeLimitRule | None:
        app_path = app.executable.lower()
        app_name = app.executable_name.lower()
        candidates = [
            rule
            for rule in rules
            if rule.target_type == "app"
            and rule.is_active_day()
            and (rule.target.lower() in (app_path, app_name) or Path(rule.target).name.lower() == app_name)
        ]
        return candidates[0] if candidates else None

    @staticmethod
    def _matching_site_rule(rules: list[TimeLimitRule], domain: str) -> TimeLimitRule | None:
        candidates = [
            rule
            for rule in rules
            if rule.target_type == "website"
            and rule.is_active_day()
            and (domain == rule.target or domain.endswith(f".{rule.target}"))
        ]
        return max(candidates, key=lambda item: len(item.target), default=None)

    def tick(self) -> None:
        """Account one second for the foreground app. Called by the UI timer."""
        self._ticks_since_flush += 1
        settings = self._settings_provider()
        rules = self._rules()
        # Foreground-window inspection is unnecessary unless screen tracking or an
        # active app rule needs it. Website limits arrive through the companion.
        needs_foreground = settings.screen_usage_enabled or any(
            rule.target_type == "app" and rule.is_active_day() for rule in rules
        )
        app = self._app_provider() if needs_foreground else None
        if app:
            own_names = {"lumaguard.exe", "python.exe", "pythonw.exe"} if self.preview else {"lumaguard.exe"}
            if app.executable_name not in own_names:
                if (
                    settings.screen_usage_enabled
                    and self._is_screen_app(app)
                ):
                    self._add_screen_seconds(
                        "app",
                        app.executable_name,
                        self._screen_app_name(app),
                        1,
                        source_app=app.executable,
                    )
                if rules:
                    rule = self._matching_app_rule(rules, app)
                    if rule:
                        self._add_seconds(rule.id, 1)
                        self._evaluate_rule(rule, app.hwnd)
                        self.usage_changed.emit()
        if self._ticks_since_flush >= 10:
            self.flush()

    def record_web_heartbeat(
        self, browser: str, domain_value: str, now: float | None = None, active: bool = True
    ) -> dict[str, object]:
        try:
            domain = normalize_domain(domain_value)
        except ValueError:
            return {"ok": False, "blocked": False, "error": "invalid_domain"}
        now_value = time.monotonic() if now is None else float(now)
        browser_id = (browser or "browser").strip().lower()[:32]
        self.record_companion_presence(browser_id, now_value)
        key = (browser_id, domain)
        with self._lock:
            previous = self._web_seen.get(key) if active else None
            if active:
                self._web_seen[key] = now_value
            else:
                self._web_seen.pop(key, None)
            stale = [item for item, seen_at in self._web_seen.items() if now_value - seen_at > 30]
            for item in stale:
                self._web_seen.pop(item, None)
            screen_previous = self._screen_web_seen.get(key) if active else None
            if active and self._settings_provider().screen_usage_enabled:
                self._screen_web_seen[key] = now_value
            else:
                self._screen_web_seen.pop(key, None)
            stale_screen = [item for item, seen_at in self._screen_web_seen.items() if now_value - seen_at > 8]
            for item in stale_screen:
                self._screen_web_seen.pop(item, None)
        if domain not in self._recorded_sites:
            self._recorded_sites.add(domain)
            self.store.record_site(domain)
            self.site_detected.emit(domain)

        if active and screen_previous is not None and self._settings_provider().screen_usage_enabled:
            screen_elapsed = max(0, min(8, int(now_value - screen_previous)))
            self._add_screen_seconds(
                "website", domain, domain, screen_elapsed, source_app=browser_id
            )

        rule = self._matching_site_rule(self._rules(), domain)
        if not rule:
            return {"ok": True, "blocked": False, "limited": False, "domain": domain}
        if active and previous is not None:
            elapsed = max(0, min(8, int(now_value - previous)))
            self._add_seconds(rule.id, elapsed)
            if elapsed:
                self.usage_changed.emit()
        status = self._evaluate_rule(rule)
        response: dict[str, object] = {
            "ok": True,
            "blocked": bool(status["blocked"]),
            "limited": True,
            "domain": domain,
            "rule_name": rule.name,
            "remaining_seconds": int(status["remaining_seconds"]),
        }
        if status.get("notice"):
            response["notice"] = status["notice"]
        return response

    def block_site_today(self, domain_value: str) -> dict[str, object]:
        """Honor a voluntary block chosen from an in-page warning."""
        try:
            domain = normalize_domain(domain_value)
        except ValueError:
            return {"ok": False, "blocked": False, "error": "invalid_domain"}
        rule = self._matching_site_rule(self._rules(), domain)
        if not rule:
            return {"ok": False, "blocked": False, "error": "no_matching_limit", "domain": domain}
        self.store.block_rule_for_day(rule.id, self._today())
        return {
            "ok": True,
            "blocked": True,
            "domain": domain,
            "rule_name": rule.display_name or rule.name,
        }

    def record_companion_presence(self, browser: str, now: float | None = None) -> None:
        browser_id = (browser or "browser").strip().lower()[:32]
        with self._lock:
            self._companion_seen[browser_id] = time.monotonic() if now is None else float(now)

    def connected_companions(self, max_age_seconds: int = 90, now: float | None = None) -> list[str]:
        current = time.monotonic() if now is None else float(now)
        with self._lock:
            active = [
                browser
                for browser, seen_at in self._companion_seen.items()
                if current - seen_at <= max(1, max_age_seconds)
            ]
        return sorted(active)

    def companion_appearance(self) -> dict[str, object]:
        settings = self._settings_provider()
        accent_name = settings.accent if settings.accent in ACCENTS else "violet"
        return {
            "accent": accent_name,
            "accent_color": ACCENTS[accent_name],
            "protection_enabled": bool(settings.protection_enabled),
        }

    def _evaluate_rule(self, rule: TimeLimitRule, hwnd: int = 0) -> dict[str, object]:
        used = self.used_seconds(rule.id)
        remaining = max(0, rule.allowance_seconds - used)
        day_key = self._today()
        notice: dict[str, str] | None = None
        if rule.warning_minutes > 0 and 0 < remaining <= rule.warning_minutes * 60:
            warning_key = (day_key, rule.id)
            if warning_key not in self._warned:
                self._warned.add(warning_key)
                title = f"{rule.display_name or rule.name} is almost out of time"
                detail = f"About {max(1, (remaining + 59) // 60)} minute(s) remain today."
                if rule.target_type == "website":
                    notice = {"kind": "approaching", "title": title, "detail": detail}
                else:
                    self.limit_event.emit("warning", title, detail, self._notification_hwnd(rule, hwnd))

        manually_blocked = self.store.is_rule_blocked(rule.id, day_key)
        blocked = manually_blocked or (used >= rule.allowance_seconds and rule.enforcement == "block")
        if used >= rule.allowance_seconds:
            limited_key = (day_key, rule.id)
            if limited_key not in self._limited_notified:
                self._limited_notified.add(limited_key)
                action = "will now be blocked" if rule.enforcement == "block" else "has reached its warning limit"
                title = f"Daily limit reached for {rule.display_name or rule.name}"
                detail = f"This target {action} until its next active day resets."
                if rule.target_type == "website":
                    notice = {"kind": "limit_reached", "title": title, "detail": detail}
                else:
                    self.limit_event.emit("warning", title, detail, self._notification_hwnd(rule, hwnd))
            if blocked and hwnd:
                last_close = self._last_close.get(rule.id, 0.0)
                current = time.monotonic()
                if current - last_close >= 15:
                    self._last_close[rule.id] = current
                    if not self.preview:
                        self._close_request(hwnd)
        return {
            "used_seconds": used,
            "remaining_seconds": remaining,
            "blocked": blocked,
            "notice": notice,
        }

    def _notification_hwnd(self, rule: TimeLimitRule, hwnd: int) -> int:
        if hwnd or rule.target_type != "website":
            return int(hwnd or 0)
        active_app = self._app_provider()
        return int(active_app.hwnd) if active_app else 0

    def flush(self) -> None:
        with self._lock:
            pending = self._pending
            screen_pending = self._screen_pending
            self._pending = {}
            self._screen_pending = {}
            self._ticks_since_flush = 0
        for (day_key, rule_id), seconds in pending.items():
            self.store.add_seconds(rule_id, seconds, day_key)
        for (
            day_key,
            hour,
            target_type,
            target_id,
            display_name,
            source_app,
        ), seconds in screen_pending.items():
            recorded_at = datetime.fromisoformat(f"{day_key}T{hour:02d}:00:00")
            self.store.add_screen_seconds(
                target_type,
                target_id,
                display_name,
                seconds,
                recorded_at,
                source_app,
            )

    def reset_screen_tracking_session(self) -> None:
        with self._lock:
            self._screen_web_seen.clear()

    def screen_usage_summary(
        self,
        start_day: str,
        end_day: str,
        target_type: str | None = None,
    ) -> list[ScreenUsageEntry]:
        combined = {
            (entry.target_type, entry.target_id): entry
            for entry in self.store.screen_usage_summary(start_day, end_day, target_type)
        }
        with self._lock:
            pending = list(self._screen_pending.items())
        for (day_key, _hour, kind, identifier, display_name, source_app), seconds in pending:
            if not (start_day <= day_key <= end_day) or (target_type and kind != target_type):
                continue
            key = (kind, identifier)
            previous = combined.get(key)
            combined[key] = ScreenUsageEntry(
                kind,
                identifier,
                display_name,
                seconds + (previous.seconds if previous else 0),
                source_app or (previous.source_app if previous else ""),
            )
        visible = [
            entry
            for entry in combined.values()
            if not (
                entry.target_type == "app"
                and _is_lumaguard_executable(entry.target_id)
            )
        ]
        return sorted(visible, key=lambda entry: (-entry.seconds, entry.display_name.lower()))

    def screen_usage_series(
        self,
        start_day: str,
        end_day: str,
        bucket: str,
        target_type: str | None = None,
        target_id: str | None = None,
        exclude_browser_apps: bool = False,
    ) -> dict[str, int]:
        excluded_app_ids = set(BROWSER_EXECUTABLES) if exclude_browser_apps else None
        values = self.store.screen_usage_series(
            start_day,
            end_day,
            bucket,
            target_type,
            target_id,
            excluded_app_ids,
            True,
        )
        normalized_target = target_id.strip().lower() if target_id else None
        with self._lock:
            pending = list(self._screen_pending.items())
        for (day_key, hour, kind, identifier, _display_name, _source_app), seconds in pending:
            if not (start_day <= day_key <= end_day):
                continue
            if target_type and kind != target_type:
                continue
            if normalized_target and identifier != normalized_target:
                continue
            if kind == "app" and _is_lumaguard_executable(identifier):
                continue
            if exclude_browser_apps and kind == "app" and identifier in BROWSER_EXECUTABLES:
                continue
            bucket_key = f"{day_key} {hour:02d}" if bucket == "hour" else (day_key[:7] if bucket == "month" else day_key)
            values[bucket_key] = values.get(bucket_key, 0) + seconds
        return values

    def screen_usage_bounds(self) -> tuple[str | None, str | None]:
        first, last = self.store.screen_usage_bounds()
        with self._lock:
            pending_days = [key[0] for key in self._screen_pending]
        if pending_days:
            first = min([day for day in (first, *pending_days) if day])
            last = max([day for day in (last, *pending_days) if day])
        return first, last

    def recent_sites(self) -> list[str]:
        return self.store.recent_sites()
