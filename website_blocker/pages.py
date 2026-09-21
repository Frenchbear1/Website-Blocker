from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGraphicsBlurEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .constants import ACCENTS, APP_VERSION, COOLDOWN_OPTIONS, DNS_PRESETS, PAUSE_WINDOW_OPTIONS
from .models import AppSettings, EventRecord, ScheduleRule, TimeLimitRule
from .pause_timer import PausePhase, format_countdown, pause_timer_state
from .widgets import (
    AccentPicker,
    EmptyState,
    MetricCard,
    ProfileSlider,
    ProtectionButton,
    SettingRow,
    StatusOrb,
    ToggleSwitch,
    page_header,
)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget:
            widget.deleteLater()
        elif child:
            _clear_layout(child)


class ScrollPage(QScrollArea):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body = QWidget()
        self.body.setObjectName("pageHost")
        self.layout = QVBoxLayout(self.body)
        self.layout.setContentsMargins(34, 30, 34, 34)
        self.layout.setSpacing(22)
        self.setWidget(self.body)


class DashboardPage(ScrollPage):
    protection_requested = Signal(bool)
    navigation_requested = Signal(str)
    clear_activity_requested = Signal()

    def __init__(self, settings: AppSettings, parent: QWidget | None = None):
        super().__init__(parent)
        header, _ = page_header("", "Dashboard", "")
        self.layout.addLayout(header)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero.setFixedHeight(205)
        hero.setProperty("active", settings.protection_enabled)
        self.hero = hero
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(30, 25, 34, 25)
        hero_layout.setSpacing(30)
        message = QVBoxLayout()
        message.setSpacing(9)
        self.hero_title = QLabel()
        self.hero_title.setObjectName("heroTitle")
        profile_row = QHBoxLayout()
        self.profile_pill = QLabel()
        self.profile_pill.setObjectName("profilePill")
        change = QPushButton("Change profile")
        change.setObjectName("linkButton")
        change.clicked.connect(lambda: self.navigation_requested.emit("profiles"))
        profile_row.addWidget(self.profile_pill)
        profile_row.addWidget(change)
        profile_row.addStretch()
        self.pause_banner = QFrame()
        self.pause_banner.setObjectName("countdownCard")
        pause_layout = QHBoxLayout(self.pause_banner)
        pause_layout.setContentsMargins(13, 10, 14, 10)
        pause_layout.setSpacing(11)
        pause_icon = QLabel("◷")
        pause_icon.setObjectName("countdownIcon")
        pause_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pause_icon.setFixedSize(34, 34)
        pause_text = QVBoxLayout()
        pause_text.setSpacing(2)
        self.pause_phase_label = QLabel()
        self.pause_phase_label.setObjectName("countdownPhase")
        self.pause_detail_label = QLabel()
        self.pause_detail_label.setObjectName("tiny")
        self.pause_detail_label.setWordWrap(True)
        pause_text.addWidget(self.pause_phase_label)
        pause_text.addWidget(self.pause_detail_label)
        self.pause_value_label = QLabel()
        self.pause_value_label.setObjectName("countdownValue")
        pause_layout.addWidget(pause_icon)
        pause_layout.addLayout(pause_text, 1)
        pause_layout.addWidget(self.pause_value_label)
        self.pause_banner.hide()
        self.protection_button = ProtectionButton(settings.protection_enabled)
        self.protection_button.clicked.connect(self._request_toggle)
        message.addWidget(self.hero_title)
        message.addSpacing(6)
        message.addLayout(profile_row)
        message.addWidget(self.pause_banner)
        message.addSpacing(8)
        message.addWidget(self.protection_button, 0, Qt.AlignmentFlag.AlignLeft)
        hero_layout.addLayout(message, 1)
        self.orb = StatusOrb(settings.protection_enabled)
        hero_layout.addWidget(self.orb, 0, Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(hero)

        activity = QFrame()
        activity.setObjectName("card")
        activity_layout = QVBoxLayout(activity)
        activity_layout.setContentsMargins(20, 19, 20, 19)
        activity_layout.setSpacing(10)
        activity_header = QHBoxLayout()
        activity_title = QLabel("Recent activity")
        activity_title.setObjectName("sectionTitle")
        self.clear_activity_button = QPushButton("Clear")
        self.clear_activity_button.setObjectName("linkButton")
        self.clear_activity_button.setToolTip("Clear recent activity")
        self.clear_activity_button.clicked.connect(self.clear_activity_requested)
        activity_header.addWidget(activity_title)
        activity_header.addStretch()
        activity_header.addWidget(self.clear_activity_button, 0, Qt.AlignmentFlag.AlignVCenter)
        activity_layout.addLayout(activity_header)
        self.activity_layout = QVBoxLayout()
        self.activity_layout.setSpacing(7)
        activity_layout.addLayout(self.activity_layout)
        self.layout.addWidget(activity)
        self.layout.addStretch()
        self.refresh(settings, [])

    def _request_toggle(self) -> None:
        self.protection_requested.emit(self.protection_button.property("willEnable") is True)

    def refresh(self, settings: AppSettings, events: list[EventRecord]) -> None:
        enabled = settings.protection_enabled
        profile = DNS_PRESETS.get(settings.active_profile, DNS_PRESETS["strong"])
        self.orb.set_active(enabled)
        self.hero.setProperty("active", enabled)
        self.hero.style().unpolish(self.hero)
        self.hero.style().polish(self.hero)
        self.hero_title.setText("Protection on" if enabled else "Protection paused")
        self.profile_pill.setText(f"{profile['name']} profile")
        self.protection_button.set_active(enabled)
        self.protection_button.setProperty("willEnable", not enabled)
        self.clear_activity_button.setVisible(bool(events))
        _clear_layout(self.activity_layout)
        if not events:
            label = QLabel("No recent activity")
            label.setObjectName("muted")
            self.activity_layout.addWidget(label)
        else:
            for event in events[:4]:
                row = QFrame()
                row.setObjectName("softCard")
                layout = QHBoxLayout(row)
                layout.setContentsMargins(11, 9, 11, 9)
                dot = QLabel("●")
                colors = {"success": "#53D6B5", "warning": "#F4BE61", "error": "#FF7A90"}
                dot.setStyleSheet(f"color:{colors.get(event.kind, '#8B7CFF')};")
                text = QVBoxLayout()
                text.setSpacing(1)
                title = QLabel(event.title)
                title.setObjectName("cardTitle")
                detail = QLabel(event.detail)
                detail.setObjectName("tiny")
                detail.setWordWrap(True)
                text.addWidget(title)
                text.addWidget(detail)
                layout.addWidget(dot)
                layout.addLayout(text, 1)
                self.activity_layout.addWidget(row)
        self.update_pause_timer(settings)

    def update_pause_timer(self, settings: AppSettings, now: datetime | None = None) -> None:
        state = pause_timer_state(settings.pause_available_at, settings.pause_window_minutes, now)
        if state.phase not in (PausePhase.COUNTDOWN, PausePhase.WINDOW):
            self.pause_banner.hide()
            self.hero.setFixedHeight(205)
            return
        self.pause_banner.setProperty("phase", state.phase.value)
        self.pause_phase_label.setProperty("windowOpen", state.phase == PausePhase.WINDOW)
        self.pause_banner.style().unpolish(self.pause_banner)
        self.pause_banner.style().polish(self.pause_banner)
        self.pause_phase_label.style().unpolish(self.pause_phase_label)
        self.pause_phase_label.style().polish(self.pause_phase_label)
        close_bound = settings.pause_window_minutes == 0
        self.pause_value_label.setText("READY" if close_bound and state.phase == PausePhase.WINDOW else format_countdown(state.seconds_remaining))
        if state.phase == PausePhase.COUNTDOWN:
            self.pause_phase_label.setText("CHANGE COOLDOWN")
            self.pause_detail_label.setText(
                "The change window stays available until you close this window."
                if close_bound
                else f"A {settings.pause_window_minutes}-minute change window opens when this reaches zero."
            )
        else:
            self.pause_phase_label.setText("CHANGE WINDOW OPEN")
            self.pause_detail_label.setText(
                "Make the protected change now. Closing this window resets the cooldown."
                if close_bound
                else "Make the protected change before this window closes, or the delay resets."
            )
        self.pause_banner.show()
        self.hero.setFixedHeight(258)


class ProfilesPage(ScrollPage):
    profile_selected = Signal(str)
    custom_dns_changed = Signal(str, str, bool)

    PROFILE_DETAILS = {
        "balanced": "Blocks adult domains.",
        "strong": "Blocks adult domains, mixed-content sites and proxies, and enforces SafeSearch.",
        "private": "Blocks adult and malware domains.",
        "custom": "Uses the primary and secondary DNS addresses you enter below.",
    }

    def __init__(self, settings: AppSettings, parent: QWidget | None = None):
        super().__init__(parent)
        header, _ = page_header("", "Protection profile", "")
        self.layout.addLayout(header)

        options = [(profile_id, data["name"], data["color"]) for profile_id, data in DNS_PRESETS.items()]
        self.slider = ProfileSlider(options, settings.active_profile)
        self.slider.previewed.connect(self._show_profile)
        self.slider.activated.connect(self._activate_profile)
        self.layout.addWidget(self.slider)

        detail = QFrame()
        detail.setObjectName("profileDetailCard")
        detail_layout = QHBoxLayout(detail)
        detail_layout.setContentsMargins(20, 18, 20, 18)
        detail_layout.setSpacing(14)
        self.profile_dot = QLabel("●")
        self.profile_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.profile_dot.setFixedWidth(24)
        detail_text = QVBoxLayout()
        detail_text.setSpacing(4)
        self.profile_name = QLabel()
        self.profile_name.setObjectName("sectionTitle")
        self.profile_summary = QLabel()
        self.profile_summary.setObjectName("muted")
        self.profile_summary.setWordWrap(True)
        detail_text.addWidget(self.profile_name)
        detail_text.addWidget(self.profile_summary)
        detail_layout.addWidget(self.profile_dot)
        detail_layout.addLayout(detail_text, 1)
        self.layout.addWidget(detail)

        self.custom_dns_card = QFrame()
        self.custom_dns_card.setObjectName("card")
        custom_layout = QVBoxLayout(self.custom_dns_card)
        custom_layout.setContentsMargins(20, 18, 20, 18)
        custom_layout.setSpacing(10)
        custom_title = QLabel("Custom DNS servers")
        custom_title.setObjectName("sectionTitle")
        row = QHBoxLayout()
        self.primary_dns = QLineEdit(settings.custom_dns_primary)
        self.primary_dns.setPlaceholderText("Primary address")
        self.secondary_dns = QLineEdit(settings.custom_dns_secondary)
        self.secondary_dns.setPlaceholderText("Secondary address")
        save = QPushButton("Save and use")
        save.setObjectName("primaryButton")
        save.setMinimumHeight(40)
        save.clicked.connect(
            lambda: self.custom_dns_changed.emit(self.primary_dns.text(), self.secondary_dns.text(), True)
        )
        row.addWidget(self.primary_dns)
        row.addWidget(self.secondary_dns)
        row.addWidget(save)
        custom_layout.addWidget(custom_title)
        custom_layout.addLayout(row)
        self.layout.addWidget(self.custom_dns_card)
        self.layout.addStretch()
        self.refresh(settings)

    def _show_profile(self, profile_id: str) -> None:
        data = DNS_PRESETS.get(profile_id, DNS_PRESETS["strong"])
        self.profile_name.setText(data["name"])
        self.profile_summary.setText(self.PROFILE_DETAILS.get(profile_id, ""))
        self.profile_dot.setStyleSheet(f"color:{data['color']}; font-size:22px;")
        self.custom_dns_card.setVisible(profile_id == "custom")

    def _activate_profile(self, profile_id: str) -> None:
        self._show_profile(profile_id)
        if profile_id != "custom" or (self.primary_dns.text().strip() and self.secondary_dns.text().strip()):
            self.profile_selected.emit(profile_id)

    def refresh(self, settings: AppSettings) -> None:
        self.slider.set_selected(settings.active_profile)
        self.primary_dns.setText(settings.custom_dns_primary)
        self.secondary_dns.setText(settings.custom_dns_secondary)
        self._show_profile(settings.active_profile)


class DomainColumn(QFrame):
    add_requested = Signal(str)
    remove_requested = Signal(str)

    def __init__(self, title: str, placeholder: str, action_text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(19, 18, 19, 18)
        layout.setSpacing(10)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        entry = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        add = QPushButton(action_text)
        add.setObjectName("primaryButton")
        add.clicked.connect(self._add)
        self.input.returnPressed.connect(self._add)
        entry.addWidget(self.input, 1)
        entry.addWidget(add)
        self.list = QListWidget()
        self.list.hide()
        self.remove_button = QPushButton("Remove selected")
        self.remove_button.setObjectName("ghostButton")
        self.remove_button.clicked.connect(self._remove)
        self.remove_button.hide()
        layout.addWidget(title_label)
        layout.addLayout(entry)
        layout.addWidget(self.list)
        layout.addWidget(self.remove_button, 0, Qt.AlignmentFlag.AlignRight)

    def _add(self) -> None:
        value = self.input.text().strip()
        if value:
            self.add_requested.emit(value)

    def _remove(self) -> None:
        item = self.list.currentItem()
        if item:
            self.remove_requested.emit(item.text())

    def set_domains(self, domains: list[str]) -> None:
        self.list.clear()
        self.list.addItems(domains)
        has_domains = bool(domains)
        self.list.setVisible(has_domains)
        self.remove_button.setVisible(has_domains)
        if has_domains:
            visible_rows = min(4, len(domains))
            rows_height = sum(max(1, self.list.sizeHintForRow(index)) for index in range(visible_rows))
            self.list.setFixedHeight(rows_height + (2 * self.list.frameWidth()) + 2)
        else:
            self.list.setFixedHeight(0)
        self.input.clear()


class RulesPage(ScrollPage):
    add_domain = Signal(str, str)
    remove_domain = Signal(str, str)

    def __init__(self, settings: AppSettings, parent: QWidget | None = None):
        super().__init__(parent)
        header, _ = page_header("", "Site rules", "")
        self.layout.addLayout(header)
        notice = QFrame()
        notice.setObjectName("softCard")
        notice_layout = QHBoxLayout(notice)
        notice_layout.setContentsMargins(16, 13, 16, 13)
        icon = QLabel("i")
        icon.setObjectName("infoBadge")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(25, 25)
        text = QLabel("Allowed sites override blocked sites.")
        text.setObjectName("muted")
        text.setWordWrap(True)
        notice_layout.addWidget(icon)
        notice_layout.addWidget(text, 1)
        self.layout.addWidget(notice)
        columns = QHBoxLayout()
        columns.setSpacing(14)
        self.blocked = DomainColumn("Blocked sites", "example.com", "Block")
        self.allowed = DomainColumn("Allowed sites", "example.com", "Allow")
        self.blocked.add_requested.connect(lambda value: self.add_domain.emit("blocked", value))
        self.allowed.add_requested.connect(lambda value: self.add_domain.emit("allowed", value))
        self.blocked.remove_requested.connect(lambda value: self.remove_domain.emit("blocked", value))
        self.allowed.remove_requested.connect(lambda value: self.remove_domain.emit("allowed", value))
        columns.addWidget(self.blocked, 1, Qt.AlignmentFlag.AlignTop)
        columns.addWidget(self.allowed, 1, Qt.AlignmentFlag.AlignTop)
        self.layout.addLayout(columns)
        self.layout.addStretch()
        self.refresh(settings)

    def refresh(self, settings: AppSettings) -> None:
        self.blocked.set_domains(settings.blocked_domains)
        self.allowed.set_domains(settings.allowed_domains)


class ScheduleCard(QFrame):
    toggled = Signal(str, bool)
    deleted = Signal(str)

    DAY_LABELS = ["M", "T", "W", "T", "F", "S", "S"]

    def __init__(self, rule: ScheduleRule, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 15, 14, 15)
        layout.setSpacing(15)
        icon = QLabel("◷")
        icon.setObjectName("accentTile")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(40, 40)
        details = QVBoxLayout()
        details.setSpacing(4)
        title = QLabel(rule.name)
        title.setObjectName("cardTitle")
        time_text = QLabel(f"{self._display_time(rule.start)} – {self._display_time(rule.end)}")
        time_text.setObjectName("muted")
        day_row = QHBoxLayout()
        day_row.setSpacing(4)
        for index, day in enumerate(self.DAY_LABELS):
            label = QLabel(day)
            enabled = index in rule.days
            label.setObjectName("dayBadge")
            label.setProperty("active", enabled)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedSize(21, 21)
            day_row.addWidget(label)
        day_row.addStretch()
        details.addWidget(title)
        details.addWidget(time_text)
        details.addLayout(day_row)
        toggle = ToggleSwitch(rule.enabled)
        toggle.toggled.connect(lambda checked: self.toggled.emit(rule.id, checked))
        delete = QPushButton("Remove")
        delete.setObjectName("ghostButton")
        delete.clicked.connect(lambda: self.deleted.emit(rule.id))
        layout.addWidget(icon)
        layout.addLayout(details, 1)
        layout.addWidget(toggle)
        layout.addWidget(delete)

    @staticmethod
    def _display_time(value: str) -> str:
        return datetime.strptime(value, "%H:%M").strftime("%I:%M %p").lstrip("0")


class SchedulePage(ScrollPage):
    master_toggled = Signal(bool)
    add_requested = Signal()
    rule_toggled = Signal(str, bool)
    rule_deleted = Signal(str)

    def __init__(self, settings: AppSettings, parent: QWidget | None = None):
        super().__init__(parent)
        top = QHBoxLayout()
        header, _ = page_header("", "Schedules", "")
        top.addLayout(header)
        self.master = ToggleSwitch(settings.schedule_enabled)
        self.master.setToolTip("Turn automatic schedules on or off")
        self.master.toggled.connect(self.master_toggled)
        top.addWidget(self.master, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addStretch()
        self.add_button = QPushButton("Add schedule")
        self.add_button.setObjectName("primaryButton")
        self.add_button.setMinimumSize(116, 40)
        self.add_button.clicked.connect(self.add_requested)
        top.addWidget(self.add_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.layout.addLayout(top)

        self.gated_content = QWidget()
        gated_layout = QVBoxLayout(self.gated_content)
        gated_layout.setContentsMargins(0, 0, 0, 0)
        self.disabled_blur = QGraphicsBlurEffect(self.gated_content)
        self.disabled_blur.setBlurRadius(3.6)
        self.gated_content.setGraphicsEffect(self.disabled_blur)
        self.schedule_layout = QVBoxLayout()
        self.schedule_layout.setSpacing(10)
        gated_layout.addLayout(self.schedule_layout)
        self.layout.addWidget(self.gated_content)
        self.layout.addStretch()
        self.refresh(settings)

    def refresh(self, settings: AppSettings) -> None:
        self.set_enabled(settings.schedule_enabled)
        _clear_layout(self.schedule_layout)
        if not settings.schedules:
            empty = EmptyState("No schedules yet", "", "Add schedule")
            if empty.button:
                empty.button.clicked.connect(self.add_requested)
            self.schedule_layout.addWidget(empty)
            return
        for rule in settings.schedules:
            card = ScheduleCard(rule)
            card.toggled.connect(self.rule_toggled)
            card.deleted.connect(self.rule_deleted)
            self.schedule_layout.addWidget(card)

    def set_enabled(self, enabled: bool) -> None:
        self.master.setChecked(enabled)
        self.gated_content.setEnabled(enabled)
        self.disabled_blur.setEnabled(not enabled)
        self.add_button.setEnabled(enabled)


def _usage_text(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


class LimitCard(QFrame):
    toggled = Signal(str, bool)
    edited = Signal(str)
    deleted = Signal(str)
    reset_requested = Signal(str)
    DAY_LABELS = ["M", "T", "W", "T", "F", "S", "S"]

    def __init__(self, rule: TimeLimitRule, used_seconds: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 16, 16)
        layout.setSpacing(10)
        top = QHBoxLayout()
        glyph = QLabel("▣" if rule.target_type == "app" else "◎")
        glyph.setObjectName("accentTile")
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph.setFixedSize(40, 40)
        text = QVBoxLayout()
        text.setSpacing(3)
        title = QLabel(rule.display_name or rule.name)
        title.setObjectName("cardTitle")
        action = "Warn only" if rule.enforcement == "warn" else ("Close gracefully" if rule.target_type == "app" else "Block page")
        identifier = rule.target if rule.target_type == "website" else rule.target.replace("\\", "/").rsplit("/", 1)[-1]
        scope = "whole app/browser" if rule.target_type == "app" else "individual website"
        target = QLabel(f"{identifier}  ·  {scope}  ·  {rule.daily_minutes} min/day  ·  {action}")
        target.setObjectName("muted")
        target.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text.addWidget(title)
        text.addWidget(target)
        toggle = ToggleSwitch(rule.enabled)
        toggle.toggled.connect(lambda checked: self.toggled.emit(rule.id, checked))
        edit = QPushButton("Edit")
        edit.setObjectName("ghostButton")
        edit.clicked.connect(lambda: self.edited.emit(rule.id))
        remove = QPushButton("Remove")
        remove.setObjectName("ghostButton")
        remove.clicked.connect(lambda: self.deleted.emit(rule.id))
        top.addWidget(glyph)
        top.addLayout(text, 1)
        top.addWidget(toggle)
        top.addWidget(edit)
        top.addWidget(remove)
        layout.addLayout(top)

        allowance = rule.allowance_seconds
        remaining = max(0, allowance - used_seconds)
        usage_row = QHBoxLayout()
        used = QLabel(f"{_usage_text(used_seconds)} used")
        used.setObjectName("tiny")
        reset = QPushButton("Reset today's usage")
        reset.setObjectName("linkButton")
        reset.setEnabled(used_seconds > 0)
        reset.setToolTip("Clear only this limit's counter for today")
        reset.clicked.connect(lambda: self.reset_requested.emit(rule.id))
        remaining_label = QLabel("Limit reached" if remaining == 0 else f"{_usage_text(remaining)} left")
        remaining_label.setObjectName("tiny")
        usage_row.addWidget(used)
        usage_row.addWidget(reset)
        usage_row.addStretch()
        usage_row.addWidget(remaining_label)
        progress = QProgressBar()
        progress.setRange(0, 1000)
        progress.setValue(min(1000, int((used_seconds / allowance) * 1000)))
        progress.setTextVisible(False)
        progress.setFixedHeight(8)
        layout.addLayout(usage_row)
        layout.addWidget(progress)
        day_row = QHBoxLayout()
        day_row.setSpacing(4)
        for index, day in enumerate(self.DAY_LABELS):
            badge = QLabel(day)
            badge.setObjectName("dayBadge")
            badge.setProperty("active", index in rule.days)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(21, 21)
            day_row.addWidget(badge)
        day_row.addStretch()
        active_today = rule.is_active_day()
        today = QLabel("Counting today" if active_today else "Not scheduled today")
        today.setObjectName("tiny")
        day_row.addWidget(today)
        layout.addLayout(day_row)


class LimitsPage(ScrollPage):
    master_toggled = Signal(bool)
    add_requested = Signal()
    rule_toggled = Signal(str, bool)
    rule_edited = Signal(str)
    rule_deleted = Signal(str)
    rule_reset_requested = Signal(str)
    companion_requested = Signal()

    def __init__(self, settings: AppSettings, parent: QWidget | None = None):
        super().__init__(parent)
        top = QHBoxLayout()
        header, _ = page_header("", "Time limits", "")
        top.addLayout(header)
        self.master = ToggleSwitch(settings.limits_enabled)
        self.master.setToolTip("Turn time-limit tracking on or off")
        self.master.toggled.connect(self.master_toggled)
        top.addWidget(self.master, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addStretch()
        self.companion_button = QPushButton("Set up companion")
        self.companion_button.setObjectName("ghostButton")
        self.companion_button.setToolTip("Optional: limit individual websites")
        self.companion_button.clicked.connect(self.companion_requested)
        top.addWidget(self.companion_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.add_button = QPushButton("Add limit")
        self.add_button.setObjectName("primaryButton")
        self.add_button.setMinimumSize(104, 40)
        self.add_button.clicked.connect(self.add_requested)
        top.addWidget(self.add_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.layout.addLayout(top)

        self.gated_content = QWidget()
        gated_layout = QVBoxLayout(self.gated_content)
        gated_layout.setContentsMargins(0, 0, 0, 0)
        gated_layout.setSpacing(18)
        self.disabled_blur = QGraphicsBlurEffect(self.gated_content)
        self.disabled_blur.setBlurRadius(3.6)
        self.gated_content.setGraphicsEffect(self.disabled_blur)

        metrics = QHBoxLayout()
        metrics.setSpacing(13)
        self.active_metric = MetricCard("Active limits", "0", "Nothing configured", "#8B7CFF")
        self.usage_metric = MetricCard("Tracked today", "0m", "Foreground time only", "#53D6B5")
        self.bridge_metric = MetricCard("Browser companion", "Offline", "Desktop bridge", "#65B8FF")
        metrics.addWidget(self.active_metric)
        metrics.addWidget(self.usage_metric)
        metrics.addWidget(self.bridge_metric)
        gated_layout.addLayout(metrics)

        self.rules_layout = QVBoxLayout()
        self.rules_layout.setSpacing(10)
        gated_layout.addLayout(self.rules_layout)
        self.layout.addWidget(self.gated_content)
        self.layout.addStretch()
        self.refresh(settings, {}, 0, False, [])

    def refresh(
        self,
        settings: AppSettings,
        usage: dict[str, int],
        total_seconds: int,
        bridge_running: bool,
        connected_browsers: list[str],
    ) -> None:
        self.set_enabled(settings.limits_enabled)
        active = sum(1 for rule in settings.time_limits if rule.enabled)
        self.active_metric.set_value(str(active), "Enabled daily boundaries" if active else "Nothing configured")
        self.usage_metric.set_value(_usage_text(total_seconds), "Foreground/focused time today")
        if connected_browsers:
            browser_names = ", ".join(name.title() for name in connected_browsers)
            self.bridge_metric.set_value("Connected", browser_names)
            self.companion_button.setText("Companion connected")
        elif bridge_running:
            self.bridge_metric.set_value("Waiting", "No browser connected")
            self.companion_button.setText("Connect companion")
        else:
            self.bridge_metric.set_value("Offline", "Desktop bridge stopped")
            self.companion_button.setText("Set up companion")
        _clear_layout(self.rules_layout)
        if not settings.time_limits:
            empty = EmptyState(
                "No time limits yet",
                "",
                "Add your first limit",
            )
            if empty.button:
                empty.button.clicked.connect(self.add_requested)
            self.rules_layout.addWidget(empty)
            return
        for rule in settings.time_limits:
            card = LimitCard(rule, usage.get(rule.id, 0))
            card.toggled.connect(self.rule_toggled)
            card.edited.connect(self.rule_edited)
            card.deleted.connect(self.rule_deleted)
            card.reset_requested.connect(self.rule_reset_requested)
            self.rules_layout.addWidget(card)

    def set_enabled(self, enabled: bool) -> None:
        self.master.setChecked(enabled)
        self.gated_content.setEnabled(enabled)
        self.disabled_blur.setEnabled(not enabled)
        self.add_button.setEnabled(enabled)
        self.companion_button.setEnabled(enabled)


class SettingsPage(ScrollPage):
    preference_changed = Signal(str, object)
    pin_action_requested = Signal()
    pin_remove_requested = Signal()

    def __init__(self, settings: AppSettings, parent: QWidget | None = None):
        super().__init__(parent)
        header, _ = page_header("", "Settings", "")
        self.layout.addLayout(header)
        general_title = QLabel("General")
        general_title.setObjectName("sectionTitle")
        self.layout.addWidget(general_title)
        self.startup = SettingRow(
            "Launch with Windows",
            "Starts elevated after sign-in and recovers after sleep, unlock, or an unexpected exit.",
            settings.launch_at_startup,
        )
        self.tray = SettingRow("Close to system tray", "Keep Website Blocker running when the window is closed.", settings.minimize_to_tray)
        self.notifications = SettingRow("Status notifications", "", settings.notifications)
        self.startup.toggled.connect(lambda value: self.preference_changed.emit("launch_at_startup", value))
        self.tray.toggled.connect(lambda value: self.preference_changed.emit("minimize_to_tray", value))
        self.notifications.toggled.connect(lambda value: self.preference_changed.emit("notifications", value))
        self.layout.addWidget(self.startup)
        self.layout.addWidget(self.tray)
        self.layout.addWidget(self.notifications)

        security_title = QLabel("Friction & accountability")
        security_title.setObjectName("sectionTitle")
        self.layout.addWidget(security_title)
        pin_card = QFrame()
        pin_card.setObjectName("settingRow")
        pin_layout = QHBoxLayout(pin_card)
        pin_layout.setContentsMargins(18, 13, 16, 13)
        text = QVBoxLayout()
        pin_title = QLabel("Settings PIN")
        pin_title.setObjectName("cardTitle")
        self.pin_detail = QLabel()
        self.pin_detail.setObjectName("muted")
        self.pin_detail.setWordWrap(True)
        self.pin_detail.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text.addWidget(pin_title)
        text.addWidget(self.pin_detail)
        self.pin_button = QPushButton()
        self.pin_button.clicked.connect(self.pin_action_requested)
        pin_layout.addLayout(text, 1)
        pin_actions = QHBoxLayout()
        pin_actions.setSpacing(8)
        pin_actions.addWidget(self.pin_button)
        self.remove_pin_button = QPushButton("Remove PIN")
        self.remove_pin_button.setObjectName("dangerButton")
        self.remove_pin_button.clicked.connect(self.pin_remove_requested)
        pin_actions.addWidget(self.remove_pin_button)
        pin_layout.addLayout(pin_actions)
        self.layout.addWidget(pin_card)

        cooldown_card = QFrame()
        cooldown_card.setObjectName("settingRow")
        cooldown_layout = QHBoxLayout(cooldown_card)
        cooldown_layout.setContentsMargins(18, 13, 16, 13)
        cooldown_text = QVBoxLayout()
        cooldown_title = QLabel("Protected-change cooldown")
        cooldown_title.setObjectName("cardTitle")
        cooldown_detail = QLabel("Sets the wait before pausing protection or weakening a time limit. Enforced while this app is running.")
        cooldown_detail.setObjectName("muted")
        cooldown_detail.setWordWrap(True)
        cooldown_text.addWidget(cooldown_title)
        cooldown_text.addWidget(cooldown_detail)
        self.cooldown = QComboBox()
        for label, minutes in COOLDOWN_OPTIONS:
            self.cooldown.addItem(label, minutes)
        self.cooldown.currentIndexChanged.connect(
            lambda: self.preference_changed.emit("cooldown_minutes", self.cooldown.currentData())
        )
        cooldown_layout.addLayout(cooldown_text, 1)
        cooldown_layout.addWidget(self.cooldown)
        self.layout.addWidget(cooldown_card)

        window_card = QFrame()
        window_card.setObjectName("settingRow")
        window_layout = QHBoxLayout(window_card)
        window_layout.setContentsMargins(18, 13, 16, 13)
        window_text = QVBoxLayout()
        window_title = QLabel("Change window")
        window_title.setObjectName("cardTitle")
        window_detail = QLabel("Choose how long a protected change stays available after the cooldown.")
        window_detail.setObjectName("muted")
        window_detail.setWordWrap(True)
        window_text.addWidget(window_title)
        window_text.addWidget(window_detail)
        self.pause_window = QComboBox()
        for label, minutes in PAUSE_WINDOW_OPTIONS:
            self.pause_window.addItem(label, minutes)
        self.pause_window.currentIndexChanged.connect(
            lambda: self.preference_changed.emit("pause_window_minutes", self.pause_window.currentData())
        )
        window_layout.addLayout(window_text, 1)
        window_layout.addWidget(self.pause_window)
        self.layout.addWidget(window_card)

        appearance_title = QLabel("Appearance")
        appearance_title.setObjectName("sectionTitle")
        self.layout.addWidget(appearance_title)
        theme_card = QFrame()
        theme_card.setObjectName("settingRow")
        theme_layout = QHBoxLayout(theme_card)
        theme_layout.setContentsMargins(18, 13, 16, 13)
        theme_text = QVBoxLayout()
        theme_title = QLabel("App theme")
        theme_title.setObjectName("cardTitle")
        theme_text.addWidget(theme_title)
        theme_layout.addLayout(theme_text, 1)
        self.theme_group = QButtonGroup(self)
        self.theme_group.setExclusive(True)
        for label, value in (("☾  Dark", "dark"), ("☀  Light", "light")):
            button = QPushButton(label)
            button.setObjectName("themeButton")
            button.setCheckable(True)
            button.setProperty("themeName", value)
            button.clicked.connect(lambda checked=False, mode=value: self.preference_changed.emit("theme", mode))
            self.theme_group.addButton(button)
            theme_layout.addWidget(button)
        self.layout.addWidget(theme_card)

        accent_card = QFrame()
        accent_card.setObjectName("settingRow")
        accent_layout = QHBoxLayout(accent_card)
        accent_layout.setContentsMargins(18, 13, 16, 13)
        accent_text = QVBoxLayout()
        accent_title = QLabel("Accent color")
        accent_title.setObjectName("cardTitle")
        accent_text.addWidget(accent_title)
        accent_layout.addLayout(accent_text, 1)
        self.accent_group = QButtonGroup(self)
        self.accent_group.setExclusive(True)
        for name, color in ACCENTS.items():
            button = AccentPicker(color, name)
            button.clicked.connect(lambda checked=False, value=name: self.preference_changed.emit("accent", value))
            button.setProperty("accentName", name)
            self.accent_group.addButton(button)
            accent_layout.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.layout.addWidget(accent_card)

        about = QLabel(f"Website Blocker {APP_VERSION} · Settings and activity remain on this computer.")
        about.setObjectName("tiny")
        about.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(about)
        self.layout.addStretch()
        self.refresh(settings)

    def refresh(self, settings: AppSettings) -> None:
        self.startup.setChecked(settings.launch_at_startup)
        self.tray.setChecked(settings.minimize_to_tray)
        self.notifications.setChecked(settings.notifications)
        self.pin_detail.setText(
            "Enabled — protects profiles, site-rule removal, pause controls, and time-limit changes."
            if settings.lock_enabled
            else "Optional — let someone you trust hold the PIN."
        )
        self.pin_button.setText("Change PIN" if settings.lock_enabled else "Set PIN")
        self.remove_pin_button.setVisible(settings.lock_enabled)
        index = self.cooldown.findData(settings.cooldown_minutes)
        self.cooldown.blockSignals(True)
        self.cooldown.setCurrentIndex(max(0, index))
        self.cooldown.blockSignals(False)
        window_index = self.pause_window.findData(settings.pause_window_minutes)
        self.pause_window.blockSignals(True)
        self.pause_window.setCurrentIndex(max(0, window_index))
        self.pause_window.blockSignals(False)
        for button in self.accent_group.buttons():
            button.setChecked(button.property("accentName") == settings.accent)
        for button in self.theme_group.buttons():
            button.setChecked(button.property("themeName") == settings.theme)
