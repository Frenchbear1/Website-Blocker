from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTime, Qt
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QWindow
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from .models import ScheduleRule, TimeLimitRule
from .constants import ACCENTS
from .icons import shield_icon
from .theme import colors, stylesheet
from .win_activity import WindowsApp


def _dialog_context(parent: QWidget | None) -> tuple[str, str, str]:
    settings = getattr(parent, "settings", None)
    theme = getattr(settings, "theme", "dark")
    accent_name = getattr(settings, "accent", "violet")
    accent = ACCENTS.get(accent_name, ACCENTS["violet"])
    return theme if theme in ("dark", "light") else "dark", accent_name, accent


class StyledDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        theme, accent_name, accent = _dialog_context(parent)
        self.dialog_theme = theme
        self.dialog_accent = accent
        self.setObjectName("modalDialog")
        self.setWindowIcon(shield_icon(64, accent, True))
        self.setStyleSheet(stylesheet(accent_name, theme))
        self._entrance = QPropertyAnimation(self, b"windowOpacity", self)
        self._entrance.setDuration(170)
        self._entrance.setStartValue(0.0)
        self._entrance.setEndValue(1.0)
        self._entrance.setEasingCurve(QEasingCurve.Type.OutCubic)

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self.setWindowOpacity(0.0)
        self._entrance.start()

    def add_header(self, layout: QVBoxLayout, eyebrow: str, title: str, detail: str) -> None:
        row = QHBoxLayout()
        row.setSpacing(15)
        icon = QLabel()
        icon.setObjectName("dialogIcon")
        icon.setPixmap(shield_icon(52, self.dialog_accent, True).pixmap(46, 46))
        icon.setFixedSize(50, 50)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text = QVBoxLayout()
        text.setSpacing(3)
        eyebrow_label = QLabel(eyebrow.upper())
        eyebrow_label.setObjectName("dialogEyebrow")
        heading = QLabel(title)
        heading.setObjectName("dialogTitle")
        heading.setWordWrap(True)
        body = QLabel(detail)
        body.setObjectName("dialogBody")
        body.setWordWrap(True)
        text.addWidget(eyebrow_label)
        text.addWidget(heading)
        if detail:
            text.addWidget(body)
        row.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        row.addLayout(text, 1)
        layout.addLayout(row)


class PinDialog(StyledDialog):
    def __init__(self, title: str, detail: str, confirm: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(18)
        self.add_header(layout, "SECURE ACTION", title, detail)
        panel = QFrame()
        panel.setObjectName("dialogPanel")
        fields = QVBoxLayout(panel)
        fields.setContentsMargins(18, 16, 18, 17)
        fields.setSpacing(8)
        pin_label = QLabel("PIN")
        pin_label.setObjectName("dialogFieldLabel")
        self.pin = QLineEdit()
        self.pin.setEchoMode(QLineEdit.EchoMode.Password)
        self.pin.setPlaceholderText("Enter PIN")
        self.pin.setMaxLength(64)
        self.pin.setMinimumHeight(42)
        self.pin.returnPressed.connect(self._accept)
        fields.addWidget(pin_label)
        fields.addWidget(self.pin)
        self.confirm_pin = None
        if confirm:
            self.confirm_pin = QLineEdit()
            self.confirm_pin.setEchoMode(QLineEdit.EchoMode.Password)
            self.confirm_pin.setPlaceholderText("Confirm PIN")
            self.confirm_pin.setMaxLength(64)
            self.confirm_pin.setMinimumHeight(42)
            self.confirm_pin.returnPressed.connect(self._accept)
            confirm_label = QLabel("CONFIRM PIN")
            confirm_label.setObjectName("dialogFieldLabel")
            fields.addSpacing(5)
            fields.addWidget(confirm_label)
            fields.addWidget(self.confirm_pin)
        layout.addWidget(panel)
        self.error = QLabel("")
        self.error.setObjectName("dialogError")
        self.error.setMinimumHeight(17)
        layout.addWidget(self.error)
        footer = QHBoxLayout()
        footer.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("ghostButton")
        cancel.setMinimumSize(96, 40)
        cancel.clicked.connect(self.reject)
        proceed = QPushButton("Set PIN" if confirm else "Continue")
        proceed.setObjectName("primaryButton")
        proceed.setMinimumSize(112, 40)
        proceed.clicked.connect(self._accept)
        proceed.setDefault(True)
        footer.addWidget(cancel)
        footer.addWidget(proceed)
        layout.addLayout(footer)
        self.pin.setFocus()

    def _accept(self) -> None:
        if len(self.pin.text()) < 4:
            self.error.setText("Use at least four characters.")
            return
        if self.confirm_pin is not None and self.pin.text() != self.confirm_pin.text():
            self.error.setText("Those PINs do not match.")
            return
        self.accept()

    @property
    def value(self) -> str:
        return self.pin.text()


class LimitWarningDialog(QDialog):
    """A monitor-aware, non-blocking time-limit warning."""

    def __init__(
        self,
        title: str,
        detail: str,
        theme: str,
        accent_name: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(False)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumWidth(560)
        self.setMaximumWidth(620)

        palette = colors(theme)
        accent = ACCENTS.get(accent_name, ACCENTS["violet"])
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        card = QFrame()
        card.setObjectName("limitWarningCard")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(46)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 150))
        card.setGraphicsEffect(shadow)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(26, 24, 26, 22)
        card_layout.setSpacing(14)

        top = QHBoxLayout()
        top.setSpacing(14)
        icon = QLabel("!")
        icon.setObjectName("limitWarningIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(48, 48)
        heading = QVBoxLayout()
        heading.setSpacing(3)
        eyebrow = QLabel("TIME LIMIT")
        eyebrow.setObjectName("limitWarningEyebrow")
        title_label = QLabel(title)
        title_label.setObjectName("limitWarningTitle")
        title_label.setWordWrap(True)
        heading.addWidget(eyebrow)
        heading.addWidget(title_label)
        top.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        top.addLayout(heading, 1)
        card_layout.addLayout(top)

        body = QLabel(detail)
        body.setObjectName("limitWarningBody")
        body.setWordWrap(True)
        body.setMinimumWidth(450)
        card_layout.addWidget(body)

        footer = QHBoxLayout()
        note = QLabel("LumaGuard pauses counting while this message has focus.")
        note.setObjectName("limitWarningNote")
        note.setWordWrap(True)
        dismiss = QPushButton("Got it")
        dismiss.setObjectName("limitWarningButton")
        dismiss.clicked.connect(self.accept)
        footer.addWidget(note, 1)
        footer.addWidget(dismiss)
        card_layout.addLayout(footer)
        outer.addWidget(card)

        self.setStyleSheet(
            f"""
            QFrame#limitWarningCard {{
                background-color: {palette['surface']};
                border: 1px solid {palette['border_strong']};
                border-radius: 20px;
            }}
            QLabel {{ color: {palette['text']}; font-family: "Segoe UI Variable", "Segoe UI"; }}
            QLabel#limitWarningIcon {{
                background-color: {palette['selected']}; color: {accent};
                border: 1px solid {accent}; border-radius: 14px;
                font-size: 25px; font-weight: 800;
            }}
            QLabel#limitWarningEyebrow {{ color: {accent}; font-size: 10px; font-weight: 800; letter-spacing: 1px; }}
            QLabel#limitWarningTitle {{ color: {palette['text']}; font-size: 18px; font-weight: 700; }}
            QLabel#limitWarningBody {{ color: {palette['text_soft']}; font-size: 13px; line-height: 1.45; }}
            QLabel#limitWarningNote {{ color: {palette['faint']}; font-size: 10px; }}
            QPushButton#limitWarningButton {{
                background-color: {accent}; color: {palette['accent_text']}; border: none;
                border-radius: 10px; padding: 9px 18px; font-size: 12px; font-weight: 700;
            }}
            """
        )
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(190)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)

    @staticmethod
    def _target_screen(hwnd: int):
        app = QGuiApplication.instance()
        if hwnd:
            try:
                foreign_window = QWindow.fromWinId(int(hwnd))
                if foreign_window and foreign_window.screen():
                    return foreign_window.screen()
            except (RuntimeError, TypeError, ValueError):
                pass
        return app.screenAt(QCursor.pos()) or app.primaryScreen()

    def show_centered(self, hwnd: int = 0) -> None:
        screen = self._target_screen(hwnd)
        self.adjustSize()
        if screen:
            available = screen.availableGeometry()
            self.move(available.center() - self.rect().center())
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self._fade.start()


class ScheduleDialog(StyledDialog):
    DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Add a protection schedule")
        self.setModal(True)
        self.setMinimumWidth(570)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(18)
        self.add_header(layout, "AUTOMATION", "New schedule", "Choose when protection turns on automatically.")
        panel = QFrame()
        panel.setObjectName("dialogPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(19, 17, 19, 18)
        panel_layout.setSpacing(14)
        form = QFormLayout()
        form.setSpacing(12)
        self.name_edit = QLineEdit("Evening protection")
        self.start_edit = QTimeEdit(QTime(21, 0))
        self.start_edit.setDisplayFormat("h:mm AP")
        self.end_edit = QTimeEdit(QTime(7, 0))
        self.end_edit.setDisplayFormat("h:mm AP")
        form.addRow("Name", self.name_edit)
        form.addRow("Starts", self.start_edit)
        form.addRow("Ends", self.end_edit)
        panel_layout.addLayout(form)
        days_label = QLabel("Days")
        days_label.setObjectName("dialogFieldLabel")
        panel_layout.addWidget(days_label)
        days = QHBoxLayout()
        days.setSpacing(6)
        self.day_buttons: list[QPushButton] = []
        for label in self.DAY_LABELS:
            button = QPushButton(label)
            button.setObjectName("wizardDay")
            button.setCheckable(True)
            button.setChecked(True)
            button.setMinimumSize(58, 40)
            self.day_buttons.append(button)
            days.addWidget(button)
        panel_layout.addLayout(days)
        layout.addWidget(panel)
        self.error = QLabel("")
        self.error.setObjectName("dialogError")
        self.error.setMinimumHeight(17)
        layout.addWidget(self.error)
        footer = QHBoxLayout()
        footer.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("ghostButton")
        cancel.setMinimumSize(96, 40)
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save schedule")
        save.setObjectName("primaryButton")
        save.setMinimumSize(132, 40)
        save.clicked.connect(self._accept)
        save.setDefault(True)
        footer.addWidget(cancel)
        footer.addWidget(save)
        layout.addLayout(footer)

    def _accept(self) -> None:
        if not self.name_edit.text().strip():
            self.error.setText("Give this schedule a name.")
            return
        if not any(button.isChecked() for button in self.day_buttons):
            self.error.setText("Select at least one day.")
            return
        self.accept()

    def rule(self, profile_id: str) -> ScheduleRule:
        return ScheduleRule(
            name=self.name_edit.text().strip(),
            days=[index for index, button in enumerate(self.day_buttons) if button.isChecked()],
            start=self.start_edit.time().toString("HH:mm"),
            end=self.end_edit.time().toString("HH:mm"),
            profile_id=profile_id,
        )


class TimeLimitDialog(StyledDialog):
    DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    BROWSER_EXECUTABLES = {"chrome.exe", "msedge.exe", "firefox.exe", "vivaldi.exe", "brave.exe", "opera.exe"}

    def __init__(
        self,
        apps: list[WindowsApp],
        sites: list[str],
        existing: TimeLimitRule | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.existing = existing
        self.setWindowTitle("Edit time limit" if existing else "Add a time limit")
        self.setModal(True)
        self.setMinimumSize(740, 620)
        self.resize(760, 650)
        self._page_animation: QPropertyAnimation | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 27, 30, 25)
        layout.setSpacing(18)

        header_row = QHBoxLayout()
        header_row.setSpacing(15)
        header_icon = QLabel()
        header_icon.setPixmap(shield_icon(52, self.dialog_accent, True).pixmap(46, 46))
        header_icon.setFixedSize(50, 50)
        header_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_text = QVBoxLayout()
        header_text.setSpacing(4)
        self.heading = QLabel()
        self.heading.setObjectName("pageTitle")
        self.heading.setStyleSheet("font-size:25px;")
        self.detail = QLabel()
        self.detail.setObjectName("muted")
        self.detail.setWordWrap(True)
        header_text.addWidget(self.heading)
        header_text.addWidget(self.detail)
        self.step_count = QLabel()
        self.step_count.setObjectName("tagPill")
        self.step_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.step_count.setMinimumWidth(78)
        header_row.addWidget(header_icon, 0, Qt.AlignmentFlag.AlignTop)
        header_row.addLayout(header_text, 1)
        header_row.addWidget(self.step_count, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header_row)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(7)
        self.step_labels: list[QLabel] = []
        for index, name in enumerate(("Target", "Time", "Days", "Action")):
            label = QLabel(f"{index + 1}  {name}")
            label.setObjectName("wizardStep")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setMinimumHeight(31)
            self.step_labels.append(label)
            progress_row.addWidget(label, 1)
        layout.addLayout(progress_row)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_target_step(apps, sites))
        self.stack.addWidget(self._build_allowance_step())
        self.stack.addWidget(self._build_days_step())
        self.stack.addWidget(self._build_action_step())
        layout.addWidget(self.stack, 1)

        self.error = QLabel("")
        self.error.setStyleSheet("color:#FF8FA2; font-size:11px;")
        self.error.setMinimumHeight(16)
        layout.addWidget(self.error)

        footer = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("ghostButton")
        self.cancel_button.clicked.connect(self.reject)
        self.back_button = QPushButton("Back")
        self.back_button.setObjectName("ghostButton")
        self.back_button.clicked.connect(self._back)
        self.next_button = QPushButton("Continue")
        self.next_button.setObjectName("primaryButton")
        self.next_button.setMinimumWidth(125)
        self.next_button.clicked.connect(self._next)
        footer.addWidget(self.cancel_button)
        footer.addStretch()
        footer.addWidget(self.back_button)
        footer.addWidget(self.next_button)
        layout.addLayout(footer)

        self._load_existing(existing)
        self._set_step(0, animate=False)

    def _page(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(2, 5, 2, 2)
        page_layout.setSpacing(13)
        return page, page_layout

    def _build_target_step(self, apps: list[WindowsApp], sites: list[str]) -> QWidget:
        page, page_layout = self._page()
        prompt = QLabel("What would you like to limit?")
        prompt.setObjectName("sectionTitle")
        page_layout.addWidget(prompt)

        choices = QHBoxLayout()
        choices.setSpacing(11)
        self.target_group = QButtonGroup(self)
        self.target_group.setExclusive(True)
        self.app_type_button = QPushButton("An app or whole browser\nNo extension needed")
        self.site_type_button = QPushButton("One specific website\nBrowser companion needed")
        for button, target_id in ((self.app_type_button, 0), (self.site_type_button, 1)):
            button.setObjectName("wizardChoice")
            button.setCheckable(True)
            button.setMinimumHeight(82)
            self.target_group.addButton(button, target_id)
            choices.addWidget(button, 1)
        self.app_type_button.clicked.connect(lambda: self._set_target_type("app"))
        self.site_type_button.clicked.connect(lambda: self._set_target_type("website"))
        page_layout.addLayout(choices)

        self.target_panel = QFrame()
        self.target_panel.setObjectName("wizardPanel")
        target_layout = QVBoxLayout(self.target_panel)
        target_layout.setContentsMargins(18, 15, 18, 16)
        target_layout.setSpacing(8)
        self.target_prompt = QLabel()
        self.target_prompt.setObjectName("cardTitle")
        self.target_help = QLabel()
        self.target_help.setObjectName("muted")
        self.target_help.setWordWrap(True)
        self.app_combo = QComboBox()
        ordered_apps = sorted(
            apps,
            key=lambda app: (app.executable_name not in self.BROWSER_EXECUTABLES, app.display_name.lower()),
        )
        for app in ordered_apps:
            suffix = "whole browser · no extension" if app.executable_name in self.BROWSER_EXECUTABLES else app.executable_name
            self.app_combo.addItem(f"{app.display_name}  ·  {suffix}", app.executable.lower())
        if not apps:
            self.app_combo.addItem("No open applications detected", "")
        self.site_combo = QComboBox()
        self.site_combo.setEditable(True)
        self.site_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.site_combo.lineEdit().setPlaceholderText("example.com")
        for site in sites:
            self.site_combo.addItem(site, site)
        if sites:
            self.site_combo.setCurrentText(sites[0])
        target_layout.addWidget(self.target_prompt)
        target_layout.addWidget(self.target_help)
        target_layout.addWidget(self.app_combo)
        target_layout.addWidget(self.site_combo)
        page_layout.addWidget(self.target_panel)
        page_layout.addStretch()
        self.app_type_button.setChecked(True)
        self._set_target_type("app")
        return page

    def _build_allowance_step(self) -> QWidget:
        page, page_layout = self._page()
        prompt = QLabel("How much time feels reasonable?")
        prompt.setObjectName("sectionTitle")
        note = QLabel("Pick a common allowance or enter your own. The counter starts fresh at local midnight.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        page_layout.addWidget(prompt)
        page_layout.addWidget(note)
        presets = QHBoxLayout()
        presets.setSpacing(7)
        self.allowance_group = QButtonGroup(self)
        self.allowance_group.setExclusive(True)
        self.allowance_buttons: dict[int, QPushButton] = {}
        for minutes in (15, 30, 45, 60, 90, 120):
            label = f"{minutes // 60}h {minutes % 60}m" if minutes >= 60 and minutes % 60 else (f"{minutes // 60}h" if minutes >= 60 else f"{minutes}m")
            button = QPushButton(label)
            button.setObjectName("wizardPill")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, value=minutes: self._set_allowance(value))
            self.allowance_group.addButton(button)
            self.allowance_buttons[minutes] = button
            presets.addWidget(button, 1)
        page_layout.addLayout(presets)
        custom = QFrame()
        custom.setObjectName("wizardPanel")
        custom_layout = QHBoxLayout(custom)
        custom_layout.setContentsMargins(18, 15, 18, 15)
        custom_text = QVBoxLayout()
        custom_title = QLabel("Custom daily allowance")
        custom_title.setObjectName("cardTitle")
        custom_detail = QLabel("Anywhere from 1 minute to 24 hours.")
        custom_detail.setObjectName("muted")
        custom_text.addWidget(custom_title)
        custom_text.addWidget(custom_detail)
        self.allowance = QSpinBox()
        self.allowance.setRange(1, 1440)
        self.allowance.setValue(60)
        self.allowance.setSuffix(" minutes")
        self.allowance.valueChanged.connect(self._sync_allowance_preset)
        custom_layout.addLayout(custom_text, 1)
        custom_layout.addWidget(self.allowance)
        page_layout.addWidget(custom)
        page_layout.addStretch()
        self._sync_allowance_preset(60)
        return page

    def _build_days_step(self) -> QWidget:
        page, page_layout = self._page()
        prompt = QLabel("When should this limit apply?")
        prompt.setObjectName("sectionTitle")
        note = QLabel("Use a preset or tap individual days to make your own schedule.")
        note.setObjectName("muted")
        page_layout.addWidget(prompt)
        page_layout.addWidget(note)
        presets = QHBoxLayout()
        presets.setSpacing(8)
        self.day_preset_buttons: dict[str, QPushButton] = {}
        for key, label in (("every", "Every day"), ("weekdays", "Weekdays"), ("weekends", "Weekends"), ("custom", "Custom")):
            button = QPushButton(label)
            button.setObjectName("wizardPill")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, value=key: self._set_day_preset(value))
            self.day_preset_buttons[key] = button
            presets.addWidget(button, 1)
        page_layout.addLayout(presets)
        day_panel = QFrame()
        day_panel.setObjectName("wizardPanel")
        day_panel_layout = QVBoxLayout(day_panel)
        day_panel_layout.setContentsMargins(18, 16, 18, 17)
        day_title = QLabel("Active days")
        day_title.setObjectName("cardTitle")
        day_panel_layout.addWidget(day_title)
        day_row = QHBoxLayout()
        day_row.setSpacing(7)
        self.day_buttons: list[QPushButton] = []
        for label in self.DAY_LABELS:
            button = QPushButton(label)
            button.setObjectName("wizardDay")
            button.setCheckable(True)
            button.setChecked(True)
            button.clicked.connect(self._sync_day_preset)
            self.day_buttons.append(button)
            day_row.addWidget(button, 1)
        day_panel_layout.addLayout(day_row)
        page_layout.addWidget(day_panel)
        page_layout.addStretch()
        self._sync_day_preset()
        return page

    def _build_action_step(self) -> QWidget:
        page, page_layout = self._page()
        prompt = QLabel("What should happen when time runs out?")
        prompt.setObjectName("sectionTitle")
        page_layout.addWidget(prompt)
        actions = QHBoxLayout()
        actions.setSpacing(11)
        self.action_group = QButtonGroup(self)
        self.action_group.setExclusive(True)
        self.block_button = QPushButton("◆   Block it\n      The firmer boundary")
        self.warn_button = QPushButton("◇   Warn me\n      Keep it available")
        for button, action_id in ((self.block_button, 0), (self.warn_button, 1)):
            button.setObjectName("wizardChoice")
            button.setCheckable(True)
            button.setMinimumHeight(78)
            self.action_group.addButton(button, action_id)
            actions.addWidget(button, 1)
        self.block_button.clicked.connect(self._update_action_note)
        self.warn_button.clicked.connect(self._update_action_note)
        self.block_button.setChecked(True)
        page_layout.addLayout(actions)

        warning_panel = QFrame()
        warning_panel.setObjectName("wizardPanel")
        warning_layout = QHBoxLayout(warning_panel)
        warning_layout.setContentsMargins(18, 13, 18, 13)
        warning_text = QVBoxLayout()
        warning_title = QLabel("Give me a heads-up")
        warning_title.setObjectName("cardTitle")
        warning_detail = QLabel("Show a centered interruption shortly before the allowance is gone.")
        warning_detail.setObjectName("muted")
        warning_text.addWidget(warning_title)
        warning_text.addWidget(warning_detail)
        self.warning = QSpinBox()
        self.warning.setRange(0, 60)
        self.warning.setValue(5)
        self.warning.setSuffix(" minutes before")
        self.warning.valueChanged.connect(self._update_summary)
        warning_layout.addLayout(warning_text, 1)
        warning_layout.addWidget(self.warning)
        page_layout.addWidget(warning_panel)
        self.safety_note = QLabel()
        self.safety_note.setObjectName("muted")
        self.safety_note.setWordWrap(True)
        page_layout.addWidget(self.safety_note)
        self.summary = QFrame()
        self.summary.setObjectName("wizardSummary")
        summary_layout = QVBoxLayout(self.summary)
        summary_layout.setContentsMargins(17, 14, 17, 14)
        summary_layout.setSpacing(4)
        summary_title = QLabel("Your limit")
        summary_title.setObjectName("tiny")
        self.summary_value = QLabel()
        self.summary_value.setObjectName("cardTitle")
        self.summary_detail = QLabel()
        self.summary_detail.setObjectName("muted")
        self.summary_detail.setWordWrap(True)
        summary_layout.addWidget(summary_title)
        summary_layout.addWidget(self.summary_value)
        summary_layout.addWidget(self.summary_detail)
        page_layout.addWidget(self.summary)
        page_layout.addStretch()
        self._update_action_note()
        return page

    def _load_existing(self, existing: TimeLimitRule | None) -> None:
        if not existing:
            return
        self._set_target_type(existing.target_type)
        if existing.target_type == "app":
            app_index = self.app_combo.findData(existing.target)
            if app_index < 0:
                executable_name = existing.target.replace("\\", "/").rsplit("/", 1)[-1]
                self.app_combo.addItem(
                    f"{existing.display_name or existing.target}  ·  {executable_name}",
                    existing.target,
                )
                app_index = self.app_combo.count() - 1
            self.app_combo.setCurrentIndex(app_index)
        else:
            self.site_combo.setCurrentText(existing.target)
        self.allowance.setValue(existing.daily_minutes)
        self.warning.setValue(existing.warning_minutes)
        for index, button in enumerate(self.day_buttons):
            button.setChecked(index in existing.days)
        self._sync_day_preset()
        self.block_button.setChecked(existing.enforcement == "block")
        self.warn_button.setChecked(existing.enforcement == "warn")
        self._update_action_note()

    def _selected_target_type(self) -> str:
        return "website" if self.site_type_button.isChecked() else "app"

    def _set_target_type(self, target_type: str) -> None:
        website = target_type == "website"
        self.site_type_button.setChecked(website)
        self.app_type_button.setChecked(not website)
        self.app_combo.setVisible(not website)
        self.site_combo.setVisible(website)
        if website:
            self.target_prompt.setText("Enter or choose a website")
            self.target_help.setText(
                "This is the only option that needs the companion. LumaGuard receives the domain only—not the full URL or page title."
            )
        else:
            self.target_prompt.setText("Choose an app that is open now")
            self.target_help.setText(
                "Choose Chrome, Edge, Firefox, Vivaldi, Brave, or Opera here to limit the entire browser without installing anything."
            )
        self._update_action_note()

    def _set_allowance(self, minutes: int) -> None:
        self.allowance.setValue(minutes)

    def _sync_allowance_preset(self, minutes: int) -> None:
        for value, button in self.allowance_buttons.items():
            button.setChecked(value == minutes)

    def _set_day_preset(self, preset: str) -> None:
        selections = {
            "every": set(range(7)),
            "weekdays": set(range(5)),
            "weekends": {5, 6},
        }
        if preset in selections:
            for index, button in enumerate(self.day_buttons):
                button.setChecked(index in selections[preset])
        self._sync_day_preset()

    def _sync_day_preset(self) -> None:
        selected = {index for index, button in enumerate(self.day_buttons) if button.isChecked()}
        preset = "custom"
        if selected == set(range(7)):
            preset = "every"
        elif selected == set(range(5)):
            preset = "weekdays"
        elif selected == {5, 6}:
            preset = "weekends"
        for key, button in self.day_preset_buttons.items():
            button.setChecked(key == preset)

    def _selected_enforcement(self) -> str:
        return "warn" if self.warn_button.isChecked() else "block"

    def _update_action_note(self) -> None:
        if not hasattr(self, "safety_note"):
            return
        if self._selected_enforcement() == "warn" and self._selected_target_type() == "website":
            text = (
                "At the limit, LumaGuard blurs the website behind a focused warning. "
                "You can dismiss it or choose a strict block for the rest of today."
            )
        elif self._selected_enforcement() == "warn":
            text = "At the limit, LumaGuard shows a focused popup on the app's monitor without closing it."
        elif self._selected_target_type() == "app":
            text = "At the limit, LumaGuard asks the active app to close normally. Save prompts still work; it is never force-killed."
        else:
            text = "At the limit, the companion replaces that website with your LumaGuard boundary page."
        self.safety_note.setText(text)
        self._update_summary()

    def _target_values(self) -> tuple[str, str]:
        if self._selected_target_type() == "app":
            target = str(self.app_combo.currentData() or "")
            label = self.app_combo.currentText().split("  ·  ", 1)[0]
            return target, label
        from .domains import normalize_domain

        target = normalize_domain(self.site_combo.currentText())
        return target, target

    def _days_description(self) -> str:
        selected = [index for index, button in enumerate(self.day_buttons) if button.isChecked()]
        if selected == list(range(7)):
            return "every day"
        if selected == list(range(5)):
            return "weekdays"
        if selected == [5, 6]:
            return "weekends"
        return ", ".join(self.DAY_LABELS[index] for index in selected)

    def _update_summary(self) -> None:
        if not hasattr(self, "summary_value"):
            return
        try:
            _target, label = self._target_values()
        except ValueError:
            label = "Website"
        action = "blocked" if self._selected_enforcement() == "block" else "warning only"
        self.summary_value.setText(f"{label} · {self.allowance.value()} minutes")
        self.summary_detail.setText(f"Applies {self._days_description()} · {action} · {self.warning.value()}-minute warning")

    def _validate_step(self, index: int) -> bool:
        if index == 0:
            if self._selected_target_type() == "app" and not self.app_combo.currentData():
                self.error.setText("Open the app or browser you want to limit, then start this flow again.")
                return False
            if self._selected_target_type() == "website":
                from .domains import normalize_domain

                try:
                    normalize_domain(self.site_combo.currentText())
                except ValueError as exc:
                    self.error.setText(str(exc))
                    return False
        if index == 2 and not any(button.isChecked() for button in self.day_buttons):
            self.error.setText("Choose at least one active day.")
            return False
        return True

    def _next(self) -> None:
        index = self.stack.currentIndex()
        self.error.clear()
        if not self._validate_step(index):
            return
        if index == self.stack.count() - 1:
            self.accept()
            return
        self._set_step(index + 1)

    def _back(self) -> None:
        self.error.clear()
        self._set_step(max(0, self.stack.currentIndex() - 1))

    def _set_step(self, index: int, animate: bool = True) -> None:
        index = max(0, min(self.stack.count() - 1, index))
        self.stack.setCurrentIndex(index)
        headings = (
            ("Choose a target", "Start with the simplest kind of boundary."),
            ("Choose an allowance", "How much focused time should be available each day?"),
            ("Choose the days", "The allowance resets independently on each active day."),
            ("Choose the boundary", "Review it once, then save."),
        )
        self.heading.setText(headings[index][0])
        self.detail.setText(headings[index][1])
        self.step_count.setText(f"Step {index + 1} of 4")
        for step_index, label in enumerate(self.step_labels):
            label.setProperty("current", step_index == index)
            label.setProperty("completed", step_index < index)
            label.style().unpolish(label)
            label.style().polish(label)
        self.back_button.setVisible(index > 0)
        self.next_button.setText("Save limit" if index == 3 else "Continue")
        if index == 3:
            self._update_action_note()
        if animate:
            page = self.stack.currentWidget()
            effect = QGraphicsOpacityEffect(page)
            page.setGraphicsEffect(effect)
            self._page_animation = QPropertyAnimation(effect, b"opacity", self)
            self._page_animation.setDuration(150)
            self._page_animation.setStartValue(0.25)
            self._page_animation.setEndValue(1.0)
            self._page_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._page_animation.finished.connect(lambda: page.setGraphicsEffect(None))
            self._page_animation.start()

    def rule(self) -> TimeLimitRule:
        target_type = self._selected_target_type()
        target, label = self._target_values()
        return TimeLimitRule(
            name=f"{label} daily limit",
            target_type=target_type,
            target=target.lower(),
            display_name=label,
            daily_minutes=self.allowance.value(),
            days=[index for index, button in enumerate(self.day_buttons) if button.isChecked()],
            enforcement=self._selected_enforcement(),
            warning_minutes=self.warning.value(),
            id=self.existing.id if self.existing else TimeLimitRule().id,
        )


class MessageDialog(StyledDialog):
    def __init__(
        self,
        title: str,
        text: str,
        kind: str = "info",
        action: str = "Done",
        cancellable: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(540)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(18)
        eyebrow = {"warning": "ATTENTION", "question": "CONFIRM ACTION"}.get(kind, "LUMAGUARD")
        self.add_header(layout, eyebrow, title, "")

        panel = QFrame()
        panel.setObjectName("dialogPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(19, 17, 19, 18)
        body = QLabel(text)
        body.setObjectName("dialogMessage")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setMinimumWidth(430)
        panel_layout.addWidget(body)
        layout.addWidget(panel)

        footer = QHBoxLayout()
        footer.addStretch()
        if cancellable:
            cancel = QPushButton("Cancel")
            cancel.setObjectName("ghostButton")
            cancel.setMinimumSize(96, 40)
            cancel.clicked.connect(self.reject)
            cancel.setDefault(True)
            footer.addWidget(cancel)
        proceed = QPushButton(action)
        destructive = any(word in action.lower() for word in ("quit", "remove", "delete"))
        proceed.setObjectName("dangerButton" if destructive else "primaryButton")
        proceed.setMinimumSize(112, 40)
        proceed.clicked.connect(self.accept)
        if not cancellable:
            proceed.setDefault(True)
        footer.addWidget(proceed)
        layout.addLayout(footer)


def ask_confirmation(parent: QWidget | None, title: str, text: str, action: str = "Continue") -> bool:
    dialog = MessageDialog(title, text, "question", action, True, parent)
    return dialog.exec() == QDialog.DialogCode.Accepted


def show_message(parent: QWidget | None, title: str, text: str, warning: bool = False) -> None:
    dialog = MessageDialog(title, text, "warning" if warning else "info", "Got it" if warning else "Done", False, parent)
    dialog.exec()
