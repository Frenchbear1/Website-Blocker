from __future__ import annotations

import ctypes
import ipaddress
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, QTimer, Qt, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QColor, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .browser_bridge import BrowserBridge
from .constants import ACCENTS, APP_NAME, DNS_PRESETS, app_data_dir
from .dialogs import LimitWarningDialog, PinDialog, ScheduleDialog, TimeLimitDialog, ask_confirmation, show_message
from .domains import normalize_domain
from .icons import nav_icon, shield_icon
from .models import AppSettings, EventRecord
from .pages import DashboardPage, LimitsPage, ProfilesPage, RulesPage, SchedulePage, SettingsPage
from .pause_timer import PausePhase, format_countdown, pause_timer_state
from .security import create_pin_hash, verify_pin
from .startup import set_launch_at_startup
from .storage import EventStore, SettingsStore, UsageStore
from .system_filter import PreviewSystemFilter, SystemFilter
from .theme import apply_palette, colors, menu_stylesheet, stylesheet
from .time_limiter import TimeLimitEngine
from .usage_page import ScreenUsagePage, usage_period
from .widgets import configure_accents
from .win_activity import list_open_apps


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings_store: SettingsStore | None = None,
        event_store: EventStore | None = None,
        usage_store: UsageStore | None = None,
        system_filter: SystemFilter | None = None,
        preview: bool = False,
    ):
        super().__init__()
        self.preview = preview
        self.settings_store = settings_store or SettingsStore()
        self.event_store = event_store or EventStore()
        self.usage_store = usage_store or UsageStore()
        self.system_filter = system_filter or (PreviewSystemFilter() if preview else SystemFilter())
        self.settings = self.settings_store.load()
        if self.settings.theme not in ("dark", "light"):
            self.settings.theme = "dark"
        self.events = self.event_store.load()
        if self.settings.launch_at_startup and not preview:
            startup_ok, startup_detail = set_launch_at_startup(True)
            if not startup_ok:
                self.event_store.add(EventRecord("error", "Windows startup needs attention", startup_detail))
                self.events = self.event_store.load()
        self._force_quit = False
        self._close_notice_shown = False
        self._page_animation: QPropertyAnimation | None = None
        self._limit_popups: list[LimitWarningDialog] = []
        self._last_pause_phase = PausePhase.INACTIVE
        self.time_engine = TimeLimitEngine(lambda: self.settings, self.usage_store, preview=preview, parent=self)
        self.browser_bridge = BrowserBridge(self.time_engine)

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(shield_icon(64, ACCENTS.get(self.settings.accent, ACCENTS["violet"])))
        self.setMinimumSize(1000, 690)
        self.resize(1180, 780)
        apply_palette(QApplication.instance(), self.settings.theme)
        self.setStyleSheet(stylesheet(self.settings.accent, self.settings.theme))
        self._build_ui()
        self._wire_pages()
        self._build_tray()
        if not self.preview:
            self.browser_bridge.start()
        self.refresh_all()

        self.schedule_timer = QTimer(self)
        self.schedule_timer.setInterval(30_000)
        self.schedule_timer.timeout.connect(self._evaluate_schedules)
        self.schedule_timer.start()
        QTimer.singleShot(1000, self._evaluate_schedules)
        self.pause_status_timer = QTimer(self)
        self.pause_status_timer.setInterval(1000)
        self.pause_status_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.pause_status_timer.timeout.connect(self._tick_pause_status)
        self.pause_status_timer.start()
        QTimer.singleShot(250, self._tick_pause_status)
        self.time_limit_timer = QTimer(self)
        self.time_limit_timer.setInterval(1000)
        self.time_limit_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.time_limit_timer.timeout.connect(self._tick_time_limits)
        self.time_limit_timer.start()
        # AutoConnection is immediate for app ticks on the UI thread, so the popup
        # can capture the target monitor before a block action closes that window.
        # Browser bridge events still cross to the UI thread safely as queued calls.
        self.time_engine.limit_event.connect(self._on_limit_event)
        self.time_engine.site_detected.connect(self._on_site_detected, Qt.ConnectionType.QueuedConnection)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(232)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 22, 18, 18)
        sidebar_layout.setSpacing(8)

        brand = QHBoxLayout()
        self.logo = QLabel()
        self.logo.setPixmap(shield_icon(42, ACCENTS.get(self.settings.accent, ACCENTS["violet"])).pixmap(38, 38))
        name_column = QVBoxLayout()
        name_column.setSpacing(0)
        name = QLabel(APP_NAME)
        name.setObjectName("brandName")
        name_column.addWidget(name)
        brand.addWidget(self.logo)
        brand.addLayout(name_column)
        brand.addStretch()
        sidebar_layout.addLayout(brand)
        sidebar_layout.addSpacing(25)

        self.nav_buttons: dict[str, QPushButton] = {}
        nav_items = [
            ("dashboard", "Dashboard"),
            ("usage", "Screen Usage"),
            ("profiles", "Profiles"),
            ("rules", "Site rules"),
            ("schedule", "Schedules"),
            ("limits", "Time limits"),
            ("settings", "Settings"),
        ]
        for key, label in nav_items:
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, destination=key: self.navigate(destination))
            self.nav_buttons[key] = button
            sidebar_layout.addWidget(button)
        self._refresh_nav_icons()
        sidebar_layout.addStretch()

        status_card = QFrame()
        status_card.setObjectName("softCard")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(13, 12, 13, 12)
        status_layout.setSpacing(5)
        row = QHBoxLayout()
        self.sidebar_dot = QLabel("●")
        self.sidebar_status = QLabel()
        self.sidebar_status.setObjectName("cardTitle")
        row.addWidget(self.sidebar_dot)
        row.addWidget(self.sidebar_status)
        row.addStretch()
        self.sidebar_profile = QLabel()
        self.sidebar_profile.setObjectName("tiny")
        status_layout.addLayout(row)
        status_layout.addWidget(self.sidebar_profile)
        sidebar_layout.addWidget(status_card)

        self.pages = QStackedWidget()
        self.pages.setObjectName("pageHost")
        self.dashboard_page = DashboardPage(self.settings)
        self.usage_page = ScreenUsagePage(self.settings)
        self.profiles_page = ProfilesPage(self.settings)
        self.rules_page = RulesPage(self.settings)
        self.schedule_page = SchedulePage(self.settings)
        self.limits_page = LimitsPage(self.settings)
        self.settings_page = SettingsPage(self.settings)
        self.page_map = {
            "dashboard": self.dashboard_page,
            "usage": self.usage_page,
            "profiles": self.profiles_page,
            "rules": self.rules_page,
            "schedule": self.schedule_page,
            "limits": self.limits_page,
            "settings": self.settings_page,
        }
        for page in self.page_map.values():
            self.pages.addWidget(page)
        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)
        self.navigate("dashboard", animate=False)

    def _refresh_nav_icons(self) -> None:
        palette = colors(self.settings.theme)
        accent = ACCENTS.get(self.settings.accent, ACCENTS["violet"])
        for key, button in self.nav_buttons.items():
            button.setIcon(nav_icon(key, palette["muted"], accent))
            button.setIconSize(QSize(22, 22))

    def _wire_pages(self) -> None:
        self.dashboard_page.protection_requested.connect(self.set_protection)
        self.dashboard_page.navigation_requested.connect(self.navigate)
        self.usage_page.tracking_toggled.connect(self.set_screen_usage_master)
        self.usage_page.view_changed.connect(self._refresh_screen_usage_page)
        self.profiles_page.profile_selected.connect(self.set_profile)
        self.profiles_page.custom_dns_changed.connect(self.set_custom_dns)
        self.rules_page.add_domain.connect(self.add_domain)
        self.rules_page.remove_domain.connect(self.remove_domain)
        self.schedule_page.master_toggled.connect(self.set_schedule_master)
        self.schedule_page.add_requested.connect(self.add_schedule)
        self.schedule_page.rule_toggled.connect(self.toggle_schedule_rule)
        self.schedule_page.rule_deleted.connect(self.delete_schedule_rule)
        self.limits_page.master_toggled.connect(self.set_limits_master)
        self.limits_page.add_requested.connect(self.add_time_limit)
        self.limits_page.rule_toggled.connect(self.toggle_time_limit)
        self.limits_page.rule_edited.connect(self.edit_time_limit)
        self.limits_page.rule_deleted.connect(self.delete_time_limit)
        self.limits_page.rule_reset_requested.connect(self.reset_time_limit_usage)
        self.limits_page.companion_requested.connect(self.open_companion_folder)
        self.settings_page.preference_changed.connect(self.set_preference)
        self.settings_page.pin_action_requested.connect(self.configure_pin)
        self.settings_page.pin_remove_requested.connect(self.remove_pin)

    def _build_tray(self) -> None:
        accent = ACCENTS.get(self.settings.accent, ACCENTS["violet"])
        self.tray = QSystemTrayIcon(shield_icon(64, accent, self.settings.protection_enabled), self)
        menu = QMenu(self)
        menu.setObjectName("trayMenu")
        menu.setStyleSheet(menu_stylesheet(self.settings.theme, self.settings.accent))
        self.tray_menu = menu
        show_action = QAction("Open Website Blocker", self)
        show_action.triggered.connect(self.show_from_tray)
        limits_action = QAction("Open time limits", self)
        limits_action.triggered.connect(self.show_time_limits)
        self.tray_toggle_action = QAction(self)
        self.tray_toggle_action.triggered.connect(lambda: self.set_protection(not self.settings.protection_enabled))
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_application)
        menu.addAction(show_action)
        menu.addAction(limits_action)
        menu.addAction(self.tray_toggle_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def navigate(self, destination: str, animate: bool = True) -> None:
        page = self.page_map.get(destination)
        if page is None:
            return
        for key, button in self.nav_buttons.items():
            button.setChecked(key == destination)
        self.pages.setCurrentWidget(page)
        if page is self.usage_page:
            self._refresh_screen_usage_page()
        if animate:
            effect = QGraphicsOpacityEffect(page)
            page.setGraphicsEffect(effect)
            self._page_animation = QPropertyAnimation(effect, b"opacity", self)
            self._page_animation.setDuration(180)
            self._page_animation.setStartValue(0.35)
            self._page_animation.setEndValue(1.0)
            self._page_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._page_animation.finished.connect(lambda: page.setGraphicsEffect(None))
            self._page_animation.start()

    def refresh_all(self) -> None:
        self.events = self.event_store.load()
        self.dashboard_page.refresh(self.settings, self.events)
        self._refresh_screen_usage_page()
        self.profiles_page.refresh(self.settings)
        self.rules_page.refresh(self.settings)
        self.schedule_page.refresh(self.settings)
        self._refresh_limits_page()
        self.settings_page.refresh(self.settings)
        profile = DNS_PRESETS.get(self.settings.active_profile, DNS_PRESETS["strong"])
        self.sidebar_status.setText("Protected" if self.settings.protection_enabled else "Protection paused")
        self.sidebar_profile.setText(f"{profile['name']} profile")
        self.sidebar_dot.setStyleSheet(f"color:{'#53D6B5' if self.settings.protection_enabled else '#77798A'};")
        self.tray_toggle_action.setText("Pause protection" if self.settings.protection_enabled else "Turn on protection")
        accent = ACCENTS.get(self.settings.accent, ACCENTS["violet"])
        brand_icon = shield_icon(64, accent, True)
        self.logo.setPixmap(brand_icon.pixmap(38, 38))
        self.setWindowIcon(brand_icon)
        self.tray.setIcon(shield_icon(64, accent, self.settings.protection_enabled))
        configure_accents(self, self.settings.accent, self.settings.theme)

    def _save(self) -> None:
        self.settings_store.save(self.settings)

    def _event(self, kind: str, title: str, detail: str) -> None:
        self.event_store.add(EventRecord(kind, title, detail))

    def _authorize_pause(self) -> bool:
        if not self.settings.lock_enabled:
            return True
        dialog = PinDialog("Unlock protection", "Enter your Website Blocker PIN before pausing protection.", parent=self)
        if dialog.exec() != PinDialog.DialogCode.Accepted:
            return False
        if not verify_pin(dialog.value, self.settings.pin_salt, self.settings.pin_hash):
            show_message(self, "Incorrect PIN", "Protection was not changed.", warning=True)
            return False
        return True

    def _cooldown_allows_pause(self) -> bool:
        minutes = self.settings.cooldown_minutes
        if minutes <= 0:
            return True
        now = datetime.now()
        state = pause_timer_state(self.settings.pause_available_at, self.settings.pause_window_minutes, now)
        if state.phase == PausePhase.COUNTDOWN:
            show_message(
                self,
                "Pause is cooling down",
                f"The pause window opens in {format_countdown(state.seconds_remaining)}.",
            )
            return False
        if state.phase == PausePhase.WINDOW:
            return True
        if state.phase == PausePhase.EXPIRED:
            self.settings.pause_available_at = ""
            self._last_pause_phase = PausePhase.INACTIVE
        available = now + timedelta(minutes=minutes)
        self.settings.pause_available_at = available.isoformat(timespec="seconds")
        self._save()
        self._event("warning", "Pause requested", f"Cooldown ends at {available.strftime('%I:%M %p').lstrip('0')}.")
        self._last_pause_phase = PausePhase.COUNTDOWN
        self.refresh_all()
        show_message(
            self,
            "Cooldown started",
            f"Protection will remain active for {self._format_duration(minutes)}. "
            + (
                "The pause window will then stay open until you close the Website Blocker window."
                if self.settings.pause_window_minutes == 0
                else f"You will then have {self._format_duration(self.settings.pause_window_minutes)} to confirm the pause before it relocks."
            ),
        )
        return False

    def _tick_pause_status(self) -> None:
        state = pause_timer_state(self.settings.pause_available_at, self.settings.pause_window_minutes)
        if not self.settings.protection_enabled:
            if self.settings.pause_available_at:
                self.settings.pause_available_at = ""
                self._save()
            self._last_pause_phase = PausePhase.INACTIVE
            if self._window_is_open():
                self.dashboard_page.update_pause_timer(self.settings)
            return
        if state.phase == PausePhase.EXPIRED:
            self.settings.pause_available_at = ""
            self._save()
            self._event("warning", "Pause window expired", "Protection relocked and a new delay will be required.")
            self._last_pause_phase = PausePhase.INACTIVE
            if self._window_is_open():
                self.refresh_all()
            if self.settings.notifications and self.tray.isVisible():
                self.tray.showMessage(
                    APP_NAME,
                    "Pause window closed. Protection is locked again.",
                    shield_icon(32, ACCENTS[self.settings.accent], True),
                    3000,
                )
            return
        if state.phase == PausePhase.WINDOW and self._last_pause_phase != PausePhase.WINDOW:
            close_bound = self.settings.pause_window_minutes == 0
            self._event(
                "success",
                "Pause window opened",
                "It will reset when the Website Blocker window closes."
                if close_bound
                else f"You have {self._format_duration(self.settings.pause_window_minutes)} to pause protection.",
            )
            if self._window_is_open():
                self.refresh_all()
            if self.settings.notifications and self.tray.isVisible():
                self.tray.showMessage(
                    APP_NAME,
                    "Pause window open until the app window closes."
                    if close_bound
                    else f"Pause window open for {self._format_duration(self.settings.pause_window_minutes)}.",
                    shield_icon(32, ACCENTS[self.settings.accent], True),
                    3500,
                )
        elif self._window_is_open():
            self.dashboard_page.update_pause_timer(self.settings)
        self._last_pause_phase = state.phase

    @staticmethod
    def _format_duration(minutes: int) -> str:
        if minutes < 60:
            return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
        days, day_remainder = divmod(minutes, 1440)
        hours, remainder = divmod(day_remainder, 60)
        parts: list[str] = []
        if days:
            parts.append(f"{days} day" if days == 1 else f"{days} days")
        if hours:
            parts.append(f"{hours} hour" if hours == 1 else f"{hours} hours")
        if remainder:
            parts.append(f"{remainder} minute" if remainder == 1 else f"{remainder} minutes")
        return " ".join(parts)

    def set_protection(self, enabled: bool, automated: bool = False) -> bool:
        enabled = bool(enabled)
        if enabled == self.settings.protection_enabled:
            return True
        if not enabled and not automated:
            if not self._cooldown_allows_pause() or not self._authorize_pause():
                self.refresh_all()
                return False
        result = self.system_filter.enable(self.settings) if enabled else self.system_filter.disable()
        if not result.success:
            self._event("error", result.message, result.detail)
            self.refresh_all()
            show_message(self, result.message, result.detail, warning=True)
            return False
        self.settings.protection_enabled = enabled
        self.settings.pause_available_at = ""
        self._last_pause_phase = PausePhase.INACTIVE
        if not automated:
            self.settings.schedule_owns_protection = False
        self._save()
        self._event("success" if enabled else "warning", result.message, result.detail)
        self.refresh_all()
        if self.settings.notifications and self.tray.isVisible():
            self.tray.showMessage(APP_NAME, result.message, shield_icon(32, ACCENTS[self.settings.accent], enabled), 2500)
        return True

    def set_profile(self, profile_id: str) -> None:
        if profile_id not in DNS_PRESETS or profile_id == self.settings.active_profile:
            return
        if profile_id == "custom":
            try:
                if ipaddress.ip_address(self.settings.custom_dns_primary).version != 4:
                    raise ValueError
                if ipaddress.ip_address(self.settings.custom_dns_secondary).version != 4:
                    raise ValueError
            except ValueError:
                show_message(self, "Custom DNS needs two addresses", "Save valid primary and secondary DNS addresses first.", warning=True)
                return
        old = self.settings.active_profile
        self.settings.active_profile = profile_id
        if self.settings.protection_enabled:
            result = self.system_filter.enable(self.settings)
            if not result.success:
                self.settings.active_profile = old
                show_message(self, result.message, result.detail, warning=True)
                self.refresh_all()
                return
        self._save()
        self._event("success", "Profile changed", f"{DNS_PRESETS[profile_id]['name']} is now selected.")
        self.refresh_all()

    def set_custom_dns(self, primary: str, secondary: str, activate: bool = False) -> None:
        try:
            primary_address = ipaddress.ip_address(primary.strip())
            secondary_address = ipaddress.ip_address(secondary.strip())
            if primary_address.version != 4 or secondary_address.version != 4:
                raise ValueError
            primary = str(primary_address)
            secondary = str(secondary_address)
        except ValueError:
            show_message(self, "Invalid DNS address", "Enter two valid IPv4 addresses.", warning=True)
            return
        old_primary = self.settings.custom_dns_primary
        old_secondary = self.settings.custom_dns_secondary
        old_profile = self.settings.active_profile
        self.settings.custom_dns_primary = primary
        self.settings.custom_dns_secondary = secondary
        if activate:
            self.settings.active_profile = "custom"
        if self.settings.protection_enabled and self.settings.active_profile == "custom":
            result = self.system_filter.enable(self.settings)
            if not result.success:
                self.settings.custom_dns_primary = old_primary
                self.settings.custom_dns_secondary = old_secondary
                self.settings.active_profile = old_profile
                show_message(self, result.message, result.detail, warning=True)
                self.refresh_all()
                return
        self._save()
        title = "Custom profile selected" if activate else "Custom DNS saved"
        self._event("success", title, f"Primary {primary} · Secondary {secondary}")
        self.refresh_all()

    def add_domain(self, kind: str, value: str) -> None:
        try:
            domain = normalize_domain(value)
        except ValueError as exc:
            show_message(self, "That domain does not look right", str(exc), warning=True)
            return
        target = self.settings.blocked_domains if kind == "blocked" else self.settings.allowed_domains
        opposite = self.settings.allowed_domains if kind == "blocked" else self.settings.blocked_domains
        if domain not in target:
            target.append(domain)
            target.sort()
        if domain in opposite:
            opposite.remove(domain)
        if self.settings.protection_enabled:
            result = self.system_filter.enable(self.settings)
            if not result.success:
                show_message(self, result.message, result.detail, warning=True)
                return
        self._save()
        self._event("success", "Site rule updated", f"{domain} was {kind}.")
        self.refresh_all()

    def remove_domain(self, kind: str, domain: str) -> None:
        target = self.settings.blocked_domains if kind == "blocked" else self.settings.allowed_domains
        if domain in target:
            target.remove(domain)
        if self.settings.protection_enabled:
            result = self.system_filter.enable(self.settings)
            if not result.success:
                show_message(self, result.message, result.detail, warning=True)
                return
        self._save()
        self._event("warning", "Site rule removed", domain)
        self.refresh_all()

    def set_schedule_master(self, enabled: bool) -> None:
        self.settings.schedule_enabled = bool(enabled)
        if not enabled:
            self.settings.schedule_owns_protection = False
        self._save()
        self._event("success" if enabled else "warning", "Schedules enabled" if enabled else "Schedules paused", "Automation preference changed.")
        self.refresh_all()
        self._evaluate_schedules()

    def add_schedule(self) -> None:
        dialog = ScheduleDialog(self)
        if dialog.exec() != ScheduleDialog.DialogCode.Accepted:
            return
        self.settings.schedules.append(dialog.rule(self.settings.active_profile))
        self._save()
        self._event("success", "Schedule added", self.settings.schedules[-1].name)
        self.refresh_all()

    def toggle_schedule_rule(self, rule_id: str, enabled: bool) -> None:
        for rule in self.settings.schedules:
            if rule.id == rule_id:
                rule.enabled = enabled
                break
        self._save()
        self.refresh_all()
        self._evaluate_schedules()

    def delete_schedule_rule(self, rule_id: str) -> None:
        self.settings.schedules = [rule for rule in self.settings.schedules if rule.id != rule_id]
        self._save()
        self._event("warning", "Schedule removed", "The automatic window was deleted.")
        self.refresh_all()

    def _tick_time_limits(self) -> None:
        self.time_engine.tick()
        if not self._window_is_open():
            return
        if self.pages.currentWidget() is self.limits_page and self.settings.limits_enabled:
            self._refresh_limits_page()
        elif self.pages.currentWidget() is self.usage_page and self.settings.screen_usage_enabled:
            self._refresh_screen_usage_page()

    def _window_is_open(self) -> bool:
        """Return whether live UI redraws can currently be seen."""
        return self.isVisible() and not self.isMinimized()

    def _refresh_screen_usage_page(self) -> None:
        first_day, _last_day = self.time_engine.screen_usage_bounds()
        period = usage_period(self.usage_page.range_key, first_day)
        target_filter = self.usage_page.type_filter if self.usage_page.type_filter in ("app", "website") else None
        rows = self.time_engine.screen_usage_summary(
            period.start.isoformat(),
            period.end.isoformat(),
            target_filter,
        )
        hide_browser_apps = target_filter is None and any(
            entry.target_type == "website" for entry in rows
        )
        if hide_browser_apps:
            browser_executables = self.time_engine.browser_executable_names()
            rows = [
                entry
                for entry in rows
                if not (
                    entry.target_type == "app" and entry.target_id in browser_executables
                )
            ]
        selected = self.usage_page.selected_target()
        if selected and not any((entry.target_type, entry.target_id) == selected for entry in rows):
            self.usage_page.clear_selection()
            selected = None
        series_values = self.time_engine.screen_usage_series(
            period.start.isoformat(),
            period.end.isoformat(),
            period.bucket,
            selected[0] if selected else target_filter,
            selected[1] if selected else None,
            hide_browser_apps and selected is None,
        )
        series = [(label, series_values.get(key, 0)) for key, label in zip(period.keys, period.labels)]
        self.usage_page.refresh(
            self.settings,
            rows,
            series,
            period.title,
            period.days,
            self.time_engine.connected_companions(),
        )

    def set_screen_usage_master(self, enabled: bool) -> None:
        self.time_engine.flush()
        self.settings.screen_usage_enabled = bool(enabled)
        self.time_engine.reset_screen_tracking_session()
        self._save()
        self._event(
            "success" if enabled else "warning",
            "Screen Usage enabled" if enabled else "Screen Usage paused",
            "Foreground app and focused website tracking changed.",
        )
        self.refresh_all()

    def _refresh_limits_page(self) -> None:
        self.limits_page.refresh(
            self.settings,
            self.time_engine.usage_map(),
            self.time_engine.total_seconds_today(),
            self.browser_bridge.running,
            self.time_engine.connected_companions(),
        )

    def set_limits_master(self, enabled: bool) -> None:
        self.settings.limits_enabled = bool(enabled)
        self._save()
        self._event(
            "success" if enabled else "warning",
            "Time limits enabled" if enabled else "Time limits paused",
            "Foreground usage tracking preference changed.",
        )
        self.refresh_all()

    def add_time_limit(self) -> None:
        apps = [app for app in list_open_apps() if app.executable_name != "website blocker.exe"]
        dialog = TimeLimitDialog(apps, self.time_engine.recent_sites(), parent=self)
        if dialog.exec() != TimeLimitDialog.DialogCode.Accepted:
            return
        rule = dialog.rule()
        duplicate = any(
            existing.target_type == rule.target_type and existing.target == rule.target
            for existing in self.settings.time_limits
        )
        if duplicate:
            show_message(
                self,
                "That target already has a limit",
                "Remove its existing limit before adding a replacement.",
                warning=True,
            )
            return
        self.settings.time_limits.append(rule)
        self._save()
        self._event(
            "success",
            "Time limit added",
            f"{rule.display_name} · {rule.daily_minutes} minutes per active day.",
        )
        self.refresh_all()

    def toggle_time_limit(self, rule_id: str, enabled: bool) -> None:
        for rule in self.settings.time_limits:
            if rule.id == rule_id:
                rule.enabled = bool(enabled)
                break
        self._save()
        self._refresh_limits_page()

    def edit_time_limit(self, rule_id: str) -> None:
        current = next((rule for rule in self.settings.time_limits if rule.id == rule_id), None)
        if not current:
            return
        apps = [app for app in list_open_apps() if app.executable_name != "website blocker.exe"]
        dialog = TimeLimitDialog(apps, self.time_engine.recent_sites(), current, self)
        if dialog.exec() != TimeLimitDialog.DialogCode.Accepted:
            return
        updated = dialog.rule()
        duplicate = any(
            existing.id != rule_id
            and existing.target_type == updated.target_type
            and existing.target == updated.target
            for existing in self.settings.time_limits
        )
        if duplicate:
            show_message(self, "That target already has a limit", "Choose a different app or website.", warning=True)
            return
        self.settings.time_limits = [updated if rule.id == rule_id else rule for rule in self.settings.time_limits]
        self._save()
        self._event("success", "Time limit updated", updated.display_name or updated.name)
        self.refresh_all()

    def delete_time_limit(self, rule_id: str) -> None:
        removed = next((rule for rule in self.settings.time_limits if rule.id == rule_id), None)
        if not removed:
            return
        if not ask_confirmation(
            self,
            "Remove this time limit?",
            f"Tracking for {removed.display_name or removed.name} will stop.",
            "Remove",
        ):
            return
        self.settings.time_limits = [rule for rule in self.settings.time_limits if rule.id != rule_id]
        self._save()
        self._event("warning", "Time limit removed", removed.display_name or removed.name)
        self.refresh_all()

    def reset_time_limit_usage(self, rule_id: str) -> None:
        rule = next((item for item in self.settings.time_limits if item.id == rule_id), None)
        if not rule:
            return
        label = rule.display_name or rule.name
        if self.settings.lock_enabled:
            dialog = PinDialog(
                "Reset today's usage",
                f"Enter your Website Blocker PIN to clear today's counter for {label}.",
                parent=self,
            )
            if dialog.exec() != PinDialog.DialogCode.Accepted:
                return
            if not verify_pin(dialog.value, self.settings.pin_salt, self.settings.pin_hash):
                show_message(self, "Incorrect PIN", "Usage was not reset.", warning=True)
                return
        elif not ask_confirmation(
            self,
            "Reset today's usage?",
            f"Only today's counter for {label} will be cleared. Other limits and earlier days stay unchanged.",
            "Reset usage",
        ):
            return
        self.time_engine.reset_usage(rule_id)
        self._event("warning", "Time-limit usage reset", f"Today's counter for {label} was cleared.")
        self._refresh_limits_page()
        show_message(self, "Usage reset", f"Today's counter for {label} is back to zero.")

    def _on_limit_event(self, kind: str, title: str, detail: str, hwnd: int) -> None:
        self._event(kind, title, detail)
        popup = LimitWarningDialog(title, detail, self.settings.theme, self.settings.accent, self)
        self._limit_popups.append(popup)
        popup.finished.connect(lambda _result, shown=popup: self._release_limit_popup(shown))
        popup.show_centered(hwnd)
        if self.pages.currentWidget() is self.limits_page:
            self._refresh_limits_page()

    def _release_limit_popup(self, popup: LimitWarningDialog) -> None:
        if popup in self._limit_popups:
            self._limit_popups.remove(popup)

    def _on_site_detected(self, _domain: str) -> None:
        if self.pages.currentWidget() is self.limits_page:
            self._refresh_limits_page()

    def open_companion_folder(self) -> None:
        source_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])) / "browser-extension"
        target_root = app_data_dir() / "Browser Companion"
        if not source_root.exists():
            show_message(
                self,
                "Companion files were not found",
                "Reinstall Website Blocker or use the companion ZIP included with this build.",
                warning=True,
            )
            return
        try:
            target_root.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source_root, target_root, dirs_exist_ok=True)
        except OSError as exc:
            show_message(self, "Could not prepare the companion", str(exc), warning=True)
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target_root)))
        show_message(
            self,
            "Finish setup in your browser",
            "1. Open the browser's Extensions page (vivaldi://extensions, chrome://extensions, or edge://extensions).\n"
            "2. Turn on Developer mode.\n"
            "3. Choose Load unpacked and select the folder that just opened.\n"
            "4. Refresh an ordinary website tab, then click the Website Blocker extension icon to confirm Connected.",
        )

    def _evaluate_schedules(self) -> None:
        if self.preview or not self.settings.schedule_enabled:
            return
        active_rules = [rule for rule in self.settings.schedules if rule.is_active()]
        if active_rules and not self.settings.protection_enabled:
            rule = active_rules[0]
            if rule.profile_id in DNS_PRESETS:
                self.settings.active_profile = rule.profile_id
            if self.set_protection(True, automated=True):
                self.settings.schedule_owns_protection = True
                self._save()
        elif not active_rules and self.settings.protection_enabled and self.settings.schedule_owns_protection:
            if self.set_protection(False, automated=True):
                self.settings.schedule_owns_protection = False
                self._save()

    def set_preference(self, name: str, value: object) -> None:
        if not hasattr(self.settings, name):
            return
        current_value = getattr(self.settings, name)
        if value == current_value:
            return
        if name in ("cooldown_minutes", "pause_window_minutes") and self.settings.lock_enabled:
            state = pause_timer_state(self.settings.pause_available_at, self.settings.pause_window_minutes)
            if state.phase in (PausePhase.COUNTDOWN, PausePhase.WINDOW):
                dialog = PinDialog(
                    "Unlock pause timing",
                    "Enter the current PIN before changing timing during an active cooldown.",
                    parent=self,
                )
                if dialog.exec() != PinDialog.DialogCode.Accepted:
                    self.settings_page.refresh(self.settings)
                    return
                if not verify_pin(dialog.value, self.settings.pin_salt, self.settings.pin_hash):
                    self.settings_page.refresh(self.settings)
                    show_message(self, "Incorrect PIN", "The active pause timing was not changed.", warning=True)
                    return
        if name in ("cooldown_minutes", "pause_window_minutes"):
            self.settings.pause_available_at = ""
            self._last_pause_phase = PausePhase.INACTIVE
        if name == "launch_at_startup" and not self.preview:
            success, detail = set_launch_at_startup(bool(value))
            if not success:
                self.settings_page.refresh(self.settings)
                show_message(self, "Startup setting was not changed", detail, warning=True)
                return
        setattr(self.settings, name, value)
        self._save()
        if name in ("accent", "theme"):
            apply_palette(QApplication.instance(), self.settings.theme)
            self.setStyleSheet(stylesheet(self.settings.accent, self.settings.theme))
            self.tray_menu.setStyleSheet(menu_stylesheet(self.settings.theme, self.settings.accent))
            accent = ACCENTS.get(self.settings.accent, ACCENTS["violet"])
            self.setWindowIcon(shield_icon(64, accent, True))
            self._refresh_nav_icons()
        self.refresh_all()

    def configure_pin(self) -> None:
        if self.settings.lock_enabled:
            current = PinDialog("Verify current PIN", "Enter the current PIN before replacing it.", parent=self)
            if current.exec() != PinDialog.DialogCode.Accepted:
                return
            if not verify_pin(current.value, self.settings.pin_salt, self.settings.pin_hash):
                show_message(self, "Incorrect PIN", "The PIN was not changed.", warning=True)
                return
        setup = PinDialog("Set a protection PIN", "For accountability, let someone you trust choose and retain this PIN.", confirm=True, parent=self)
        if setup.exec() != PinDialog.DialogCode.Accepted:
            return
        salt, digest = create_pin_hash(setup.value)
        self.settings.pin_salt = salt
        self.settings.pin_hash = digest
        self.settings.lock_enabled = True
        self._save()
        self._event("success", "Protection PIN enabled", "A PIN is now required before protection can be paused.")
        self.refresh_all()

    def remove_pin(self) -> None:
        if not self.settings.lock_enabled:
            return
        current = PinDialog(
            "Remove settings PIN",
            "Enter the current PIN to remove it completely.",
            parent=self,
        )
        if current.exec() != PinDialog.DialogCode.Accepted:
            return
        if not verify_pin(current.value, self.settings.pin_salt, self.settings.pin_hash):
            show_message(self, "Incorrect PIN", "The PIN was not removed.", warning=True)
            return
        if not ask_confirmation(
            self,
            "Remove the settings PIN?",
            "Protection can then be paused and time-limit usage reset without a PIN.",
            "Remove PIN",
        ):
            return
        self.settings.pin_salt = ""
        self.settings.pin_hash = ""
        self.settings.lock_enabled = False
        self._save()
        self._event("warning", "Protection PIN removed", "PIN checks are now off.")
        self.refresh_all()
        show_message(self, "PIN removed", "Website Blocker no longer requires a PIN.")

    def show_from_tray(self) -> None:
        self.showNormal()
        self.refresh_all()
        self.raise_()
        self.activateWindow()

    def show_time_limits(self) -> None:
        self.show_from_tray()
        self.navigate("limits")

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_from_tray()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._reset_close_bound_pause_window()
        if self._force_quit or not self.settings.minimize_to_tray:
            event.accept()
            return
        event.ignore()
        self.hide()
        if not self._close_notice_shown and self.settings.notifications:
            self.tray.showMessage(APP_NAME, "Still running in the system tray.", self.windowIcon(), 2200)
            self._close_notice_shown = True

    def quit_application(self) -> None:
        if self.settings.protection_enabled:
            if not ask_confirmation(
                self,
                "Quit Website Blocker?",
                "System filtering remains applied after the interface closes, but schedules and time limits will not run until Website Blocker starts again.",
                "Quit",
            ):
                return
        self._force_quit = True
        self.shutdown()
        self.tray.hide()
        QApplication.instance().quit()

    def shutdown(self) -> None:
        self._reset_close_bound_pause_window()
        self.browser_bridge.stop()
        self.time_engine.flush()

    def _reset_close_bound_pause_window(self) -> None:
        if self.settings.pause_window_minutes != 0 or not self.settings.pause_available_at:
            return
        state = pause_timer_state(self.settings.pause_available_at, 0)
        if state.phase != PausePhase.WINDOW:
            return
        self.settings.pause_available_at = ""
        self._last_pause_phase = PausePhase.INACTIVE
        self._save()
        self._event("warning", "Pause window reset", "The Website Blocker window was closed.")

    def apply_windows_frame(self) -> None:
        if os.name != "nt" or not self.windowHandle():
            return
        try:
            hwnd = int(self.winId())
            dark = ctypes.c_int(1 if self.settings.theme == "dark" else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
            corner = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(corner), ctypes.sizeof(corner))
        except (AttributeError, OSError, ValueError):
            pass
