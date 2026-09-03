from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from hashlib import sha256

from PySide6.QtCore import QEasingCurve, QFileInfo, QPointF, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QFileIconProvider,
    QGraphicsBlurEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from .constants import ACCENTS
from .models import AppSettings, ScreenUsageEntry
from .widgets import EmptyState, ToggleSwitch, page_header
from .win_activity import resolve_executable_path


USAGE_COLORS = ("#8B7CFF", "#53D6B5", "#65B8FF", "#FF7A90", "#F4BE61", "#A78BFA", "#2EC4B6")


def _usage_color(target_type: str, target_id: str) -> str:
    digest = sha256(f"{target_type}:{target_id}".encode("utf-8")).digest()
    return USAGE_COLORS[digest[0] % len(USAGE_COLORS)]


@lru_cache(maxsize=160)
def _native_app_icon(source: str) -> QIcon:
    executable = resolve_executable_path(source)
    if not executable:
        return QIcon()
    return QFileIconProvider().icon(QFileInfo(executable))


def usage_time_text(seconds: int) -> str:
    value = max(0, int(seconds))
    hours, remainder = divmod(value, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    if minutes:
        return f"{minutes}m" if not secs else f"{minutes}m {secs}s"
    return f"{secs}s"


@dataclass(frozen=True)
class UsagePeriod:
    start: date
    end: date
    bucket: str
    keys: tuple[str, ...]
    labels: tuple[str, ...]
    title: str
    days: int


def usage_period(range_key: str, first_day: str | None = None, today: date | None = None) -> UsagePeriod:
    current = today or date.today()
    if range_key == "week":
        start = current - timedelta(days=6)
        dates = [start + timedelta(days=index) for index in range(7)]
        return UsagePeriod(
            start,
            current,
            "day",
            tuple(day.isoformat() for day in dates),
            tuple(day.strftime("%a") for day in dates),
            "Last 7 days",
            7,
        )
    if range_key == "month":
        start = current.replace(day=1)
        dates = [start + timedelta(days=index) for index in range((current - start).days + 1)]
        return UsagePeriod(
            start,
            current,
            "day",
            tuple(day.isoformat() for day in dates),
            tuple(str(day.day) for day in dates),
            current.strftime("%B %Y"),
            len(dates),
        )
    if range_key == "all":
        try:
            start = date.fromisoformat(first_day) if first_day else current
        except ValueError:
            start = current
        start = start.replace(day=1)
        months: list[date] = []
        cursor = start
        while cursor <= current:
            months.append(cursor)
            cursor = date(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1)
        return UsagePeriod(
            start,
            current,
            "month",
            tuple(month.strftime("%Y-%m") for month in months),
            tuple(month.strftime("%b %y") for month in months),
            f"Since {start.strftime('%b %Y')}",
            max(1, (current - start).days + 1),
        )
    keys = tuple(f"{current.isoformat()} {hour:02d}" for hour in range(24))
    labels = tuple(
        "12a" if hour == 0 else f"{hour}a" if hour < 12 else "12p" if hour == 12 else f"{hour - 12}p"
        for hour in range(24)
    )
    return UsagePeriod(current, current, "hour", keys, labels, "Today", 1)


class UsageChart(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._data: list[tuple[str, int]] = []
        self._color = "#8B7CFF"
        self._progress = 1.0
        self._hovered = -1
        self._bar_rects: list[QRectF] = []
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(420)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._set_progress)
        self.setMinimumHeight(220)
        self.setMouseTracking(True)

    def set_data(self, data: list[tuple[str, int]], color: str) -> None:
        labels_changed = [item[0] for item in data] != [item[0] for item in self._data]
        scope_changed = color != self._color
        self._data = data
        self._color = color
        if labels_changed or scope_changed:
            self._animation.stop()
            self._progress = 0.0
            self._animation.setStartValue(0.0)
            self._animation.setEndValue(1.0)
            self._animation.start()
        else:
            self._progress = 1.0
            self.update()

    def _set_progress(self, value: object) -> None:
        self._progress = float(value)
        self.update()

    def mouseMoveEvent(self, event):  # noqa: N802
        hovered = next((index for index, rect in enumerate(self._bar_rects) if rect.contains(event.position())), -1)
        if hovered != self._hovered:
            self._hovered = hovered
            self.update()
        if 0 <= hovered < len(self._data):
            label, seconds = self._data[hovered]
            QToolTip.showText(event.globalPosition().toPoint(), f"{label}: {usage_time_text(seconds)}", self)
        else:
            QToolTip.hideText()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._hovered = -1
        QToolTip.hideText()
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        light = self.property("theme") == "light"
        grid = QColor("#E5E7EE" if light else "#292B38")
        text = QColor("#7A7D8B" if light else "#8F91A1")
        plot = QRectF(36, 12, max(1, self.width() - 52), max(1, self.height() - 48))

        painter.setPen(QPen(grid, 1))
        for row in range(4):
            y = plot.top() + plot.height() * row / 3
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

        if not self._data:
            self._bar_rects = []
            return
        maximum = max(1, max(seconds for _label, seconds in self._data))
        slot = plot.width() / len(self._data)
        bar_width = max(3.0, min(30.0, slot * 0.62))
        accent = QColor(self._color)
        self._bar_rects = []
        for index, (_label, seconds) in enumerate(self._data):
            x = plot.left() + slot * index + (slot - bar_width) / 2
            height = max(2.0 if seconds else 0.0, plot.height() * seconds / maximum * self._progress)
            rect = QRectF(x, plot.bottom() - height, bar_width, height)
            self._bar_rects.append(QRectF(x - 2, plot.top(), bar_width + 4, plot.height()))
            fill = QColor(accent)
            fill.setAlpha(255 if index == self._hovered else 205)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, min(4.0, bar_width / 2), min(4.0, bar_width / 2))

        label_step = max(1, math.ceil(len(self._data) / 8))
        painter.setFont(QFont("Segoe UI Variable", 8))
        painter.setPen(text)
        for index, (label, _seconds) in enumerate(self._data):
            if index % label_step and index != len(self._data) - 1:
                continue
            x = plot.left() + slot * index
            painter.drawText(
                QRectF(x, plot.bottom() + 8, slot * label_step, 20),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                label,
            )


class UsageRow(QFrame):
    selected = Signal(str, str)

    def __init__(
        self,
        entry: ScreenUsageEntry,
        maximum: int,
        selected: bool = False,
        website_browser: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("usageRow")
        self.setProperty("selected", selected)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(13, 11, 14, 11)
        layout.setSpacing(12)
        color = _usage_color(entry.target_type, entry.target_id)
        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(42, 42)
        icon_source = (
            (entry.source_app or website_browser)
            if entry.target_type == "website"
            else (entry.source_app or entry.target_id)
        )
        native_icon = _native_app_icon(icon_source)
        if native_icon.isNull():
            icon.setObjectName("usageIconFallback")
            icon.setText(entry.display_name[:1].upper())
            icon.setStyleSheet(f"color:{color};")
        else:
            icon.setPixmap(native_icon.pixmap(34, 34))
        text = QVBoxLayout()
        text.setSpacing(5)
        title_row = QHBoxLayout()
        name = QLabel(entry.display_name)
        name.setObjectName("cardTitle")
        kind = QLabel("Website" if entry.target_type == "website" else "App")
        kind.setObjectName("tiny")
        title_row.addWidget(name)
        title_row.addWidget(kind)
        title_row.addStretch()
        progress = QProgressBar()
        progress.setRange(0, 1000)
        progress.setValue(int(entry.seconds / max(1, maximum) * 1000))
        progress.setTextVisible(False)
        progress.setFixedHeight(6)
        progress.setStyleSheet(f"QProgressBar::chunk {{ background:{color}; border-radius:3px; }}")
        text.addLayout(title_row)
        text.addWidget(progress)
        duration = QLabel(usage_time_text(entry.seconds))
        duration.setObjectName("usageDuration")
        arrow = QLabel("›")
        arrow.setObjectName("usageArrow")
        layout.addWidget(icon)
        layout.addLayout(text, 1)
        layout.addWidget(duration)
        layout.addWidget(arrow)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.entry.target_type, self.entry.target_id)
        super().mouseReleaseEvent(event)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            _clear_layout(item.layout())


class ScreenUsagePage(QScrollArea):
    tracking_toggled = Signal(bool)
    view_changed = Signal()

    def __init__(self, settings: AppSettings, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.range_key = "day"
        self.type_filter = "all"
        self._selected: tuple[str, str] | None = None

        self.body = QWidget()
        self.body.setObjectName("pageHost")
        self.layout = QVBoxLayout(self.body)
        self.layout.setContentsMargins(34, 30, 34, 34)
        self.layout.setSpacing(18)
        self.setWidget(self.body)

        top = QHBoxLayout()
        header, _ = page_header("", "Screen Usage", "")
        top.addLayout(header)
        self.master = ToggleSwitch(settings.screen_usage_enabled)
        self.master.setToolTip("Turn focused screen-usage tracking on or off")
        self.master.toggled.connect(self.tracking_toggled)
        top.addWidget(self.master, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addStretch()
        self.layout.addLayout(top)

        self.gated_content = QWidget()
        gated_layout = QVBoxLayout(self.gated_content)
        gated_layout.setContentsMargins(0, 0, 0, 0)
        gated_layout.setSpacing(18)
        self.disabled_blur = QGraphicsBlurEffect(self.gated_content)
        self.disabled_blur.setBlurRadius(3.6)
        self.gated_content.setGraphicsEffect(self.disabled_blur)

        controls = QFrame()
        controls.setObjectName("usageControls")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(8, 7, 8, 7)
        controls_layout.setSpacing(5)
        self.range_group = QButtonGroup(self)
        self.range_group.setExclusive(True)
        for label, key in (("Day", "day"), ("Week", "week"), ("Month", "month"), ("All time", "all")):
            button = QPushButton(label)
            button.setObjectName("segmentButton")
            button.setCheckable(True)
            button.setChecked(key == self.range_key)
            button.clicked.connect(lambda checked=False, value=key: self._set_range(value))
            self.range_group.addButton(button)
            controls_layout.addWidget(button)
        controls_layout.addStretch()
        self.capture_note = QLabel()
        self.capture_note.setObjectName("tiny")
        controls_layout.addWidget(self.capture_note)
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("All activity", "all")
        self.filter_combo.addItem("Apps", "app")
        self.filter_combo.addItem("Websites", "website")
        self.filter_combo.currentIndexChanged.connect(self._set_filter)
        controls_layout.addWidget(self.filter_combo)

        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(18)
        self.chart_card = QFrame()
        self.chart_card.setObjectName("usageChartCard")
        chart_layout = QVBoxLayout(self.chart_card)
        chart_layout.setContentsMargins(20, 18, 20, 16)
        chart_layout.setSpacing(8)
        summary = QHBoxLayout()
        summary_text = QVBoxLayout()
        summary_text.setSpacing(2)
        self.scope_title = QLabel("All activity")
        self.scope_title.setObjectName("sectionTitle")
        self.scope_detail = QLabel()
        self.scope_detail.setObjectName("muted")
        summary_text.addWidget(self.scope_title)
        summary_text.addWidget(self.scope_detail)
        summary.addLayout(summary_text, 1)
        total_column = QVBoxLayout()
        total_column.setSpacing(1)
        self.total_label = QLabel("0s")
        self.total_label.setObjectName("usageTotal")
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.average_label = QLabel()
        self.average_label.setObjectName("tiny")
        self.average_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        total_column.addWidget(self.total_label)
        total_column.addWidget(self.average_label)
        self.show_all = QPushButton("Show all")
        self.show_all.setObjectName("linkButton")
        self.show_all.clicked.connect(self._clear_selection)
        self.show_all.hide()
        summary.addWidget(self.show_all, 0, Qt.AlignmentFlag.AlignTop)
        summary.addLayout(total_column)
        self.chart = UsageChart()
        chart_layout.addLayout(summary)
        chart_layout.addWidget(self.chart)
        content_layout.addWidget(self.chart_card)

        activity_header = QHBoxLayout()
        self.activity_title = QLabel("Apps & websites")
        self.activity_title.setObjectName("sectionTitle")
        self.item_count = QLabel()
        self.item_count.setObjectName("tiny")
        activity_header.addWidget(self.activity_title)
        activity_header.addStretch()
        activity_header.addWidget(self.item_count)
        content_layout.addLayout(activity_header)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(8)
        content_layout.addLayout(self.rows_layout)
        self.empty_state = EmptyState("No usage in this period", "Only focused apps and active website tabs count.")
        content_layout.addWidget(self.empty_state)

        gated_layout.addWidget(controls)
        gated_layout.addWidget(self.content)
        self.layout.addWidget(self.gated_content)
        self.layout.addStretch()
        self.set_enabled(settings.screen_usage_enabled)

    def _set_range(self, value: str) -> None:
        if value == self.range_key:
            return
        self.range_key = value
        self.view_changed.emit()

    def _set_filter(self) -> None:
        value = str(self.filter_combo.currentData() or "all")
        if value == self.type_filter:
            return
        self.type_filter = value
        self._selected = None
        self.view_changed.emit()

    def _select_target(self, target_type: str, target_id: str) -> None:
        self._selected = (target_type, target_id)
        self.view_changed.emit()

    def _clear_selection(self) -> None:
        if self._selected is None:
            return
        self._selected = None
        self.view_changed.emit()

    def selected_target(self) -> tuple[str, str] | None:
        return self._selected

    def clear_selection(self) -> None:
        self._selected = None

    def set_enabled(self, enabled: bool) -> None:
        self.master.setChecked(enabled)
        self.gated_content.setEnabled(enabled)
        self.disabled_blur.setEnabled(not enabled)

    def refresh(
        self,
        settings: AppSettings,
        rows: list[ScreenUsageEntry],
        series: list[tuple[str, int]],
        period_title: str,
        period_days: int,
        connected_browsers: list[str],
    ) -> None:
        self.set_enabled(settings.screen_usage_enabled)
        if not settings.screen_usage_enabled:
            return
        self.capture_note.setText(
            "App focus + website domains"
            if connected_browsers
            else "App focus · companion needed for websites"
        )
        selected = next(
            (
                entry
                for entry in rows
                if self._selected and (entry.target_type, entry.target_id) == self._selected
            ),
            None,
        )
        if self._selected and not selected:
            self._selected = None
        all_total = sum(entry.seconds for entry in rows)
        total = selected.seconds if selected else all_total
        color = _usage_color(selected.target_type, selected.target_id) if selected else ACCENTS.get(settings.accent, "#8B7CFF")
        self.scope_title.setText(selected.display_name if selected else "All activity")
        self.scope_detail.setText(
            f"{'Website' if selected and selected.target_type == 'website' else 'App'} · {period_title} · "
            f"{round(selected.seconds / max(1, all_total) * 100)}% of activity"
            if selected
            else f"Focused apps and websites · {period_title}"
        )
        self.total_label.setText(usage_time_text(total))
        self.average_label.setText("Day total" if period_days == 1 else f"{usage_time_text(total // max(1, period_days))} daily average")
        self.show_all.setVisible(selected is not None)
        self.chart.setProperty("theme", settings.theme)
        self.chart.set_data(series, color)

        _clear_layout(self.rows_layout)
        maximum = max((entry.seconds for entry in rows), default=1)
        website_browser = connected_browsers[0] if connected_browsers else ""
        for entry in rows[:50]:
            row = UsageRow(
                entry,
                maximum,
                selected=bool(selected and (entry.target_type, entry.target_id) == (selected.target_type, selected.target_id)),
                website_browser=website_browser,
            )
            row.selected.connect(self._select_target)
            self.rows_layout.addWidget(row)
        self.empty_state.setVisible(not rows)
        self.item_count.setText(f"{len(rows)} item" if len(rows) == 1 else f"{len(rows)} items")
        self.activity_title.setText(
            "Apps" if self.type_filter == "app" else "Websites" if self.type_filter == "website" else "Apps & websites"
        )
