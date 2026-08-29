from __future__ import annotations

from PySide6.QtCore import QAbstractAnimation, Property, QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .constants import ACCENTS


class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(48, 27)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._checked = checked
        self._position = 1.0 if checked else 0.0
        self._animation = QPropertyAnimation(self, b"position", self)
        self._animation.setDuration(170)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, animate: bool = False) -> None:
        checked = bool(checked)
        if self._checked == checked and self._position == (1.0 if checked else 0.0):
            return
        self._checked = checked
        target = 1.0 if checked else 0.0
        if animate:
            self._animation.stop()
            self._animation.setStartValue(self._position)
            self._animation.setEndValue(target)
            self._animation.start()
        else:
            self._position = target
            self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.setChecked(not self._checked, animate=True)
            self.toggled.emit(self._checked)
        super().mouseReleaseEvent(event)

    def get_position(self) -> float:
        return self._position

    def set_position(self, value: float) -> None:
        self._position = value
        self.update()

    position = Property(float, get_position, set_position)

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        light = self.property("theme") == "light"
        off = QColor("#C9CDD8" if light else "#343645")
        on = QColor(self.property("accent") or "#8B7CFF")
        blend = QColor(
            int(off.red() + (on.red() - off.red()) * self._position),
            int(off.green() + (on.green() - off.green()) * self._position),
            int(off.blue() + (on.blue() - off.blue()) * self._position),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(blend)
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 13.5, 13.5)
        painter.setBrush(QColor("#FFFFFF"))
        x = 4 + self._position * (self.width() - self.height())
        painter.drawEllipse(QRectF(x, 4, 19, 19))


class AccentPicker(QPushButton):
    """A centered, custom-painted color pill without font-dependent glyphs."""

    def __init__(self, color: str, name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.color = QColor(color)
        self._hovered = False
        self.setObjectName("accentPicker")
        self.setCheckable(True)
        self.setFixedSize(62, 42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(f"{name.title()} accent")
        self.setToolTip(name.title())

    def enterEvent(self, event):  # noqa: N802
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(3.0, 3.0, -3.0, -5.0)
        if self.isDown():
            rect.adjust(1.0, 1.0, -1.0, -1.0)
        shadow = QColor("#000000")
        shadow.setAlpha(34 if self.property("theme") == "light" else 78)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow)
        shadow_rect = QRectF(rect)
        shadow_rect.translate(0, 2)
        painter.drawRoundedRect(shadow_rect, shadow_rect.height() / 2, shadow_rect.height() / 2)
        fill = self.color.lighter(108) if self._hovered else self.color
        painter.setBrush(fill)
        if self.isChecked():
            light = self.property("theme") == "light"
            painter.setPen(QPen(QColor("#20212A" if light else "#F4F3FA"), 3.0))
        else:
            edge = QColor("#FFFFFF")
            edge.setAlpha(85 if self._hovered else 35)
            painter.setPen(QPen(edge, 1.0))
        radius = rect.height() / 2
        painter.drawRoundedRect(rect, radius, radius)


class ProtectionButton(QPushButton):
    def __init__(self, active: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("protectionButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(190)
        self.setFixedHeight(48)
        self._active = active
        self._hover = 0.0
        self._press = 0.0
        self._ripple = 1.0
        self._ripple_origin = QPointF(self.width() / 2, self.height() / 2)
        self._hover_animation = QPropertyAnimation(self, b"hoverProgress", self)
        self._hover_animation.setDuration(170)
        self._hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._press_animation = QPropertyAnimation(self, b"pressProgress", self)
        self._press_animation.setDuration(130)
        self._press_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._ripple_animation = QPropertyAnimation(self, b"rippleProgress", self)
        self._ripple_animation.setDuration(440)
        self._ripple_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.set_active(active)

    def set_active(self, active: bool) -> None:
        self._active = bool(active)
        self.setText("Pause protection" if self._active else "Resume protection")
        self.setAccessibleName(self.text())
        self.update()

    def get_hover_progress(self) -> float:
        return self._hover

    def set_hover_progress(self, value: float) -> None:
        self._hover = float(value)
        self.update()

    hoverProgress = Property(float, get_hover_progress, set_hover_progress)

    def get_press_progress(self) -> float:
        return self._press

    def set_press_progress(self, value: float) -> None:
        self._press = float(value)
        self.update()

    pressProgress = Property(float, get_press_progress, set_press_progress)

    def get_ripple_progress(self) -> float:
        return self._ripple

    def set_ripple_progress(self, value: float) -> None:
        self._ripple = float(value)
        self.update()

    rippleProgress = Property(float, get_ripple_progress, set_ripple_progress)

    def _animate(self, animation: QPropertyAnimation, start: float, end: float) -> None:
        animation.stop()
        animation.setStartValue(start)
        animation.setEndValue(end)
        animation.start()

    def enterEvent(self, event):  # noqa: N802
        self._animate(self._hover_animation, self._hover, 1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._animate(self._hover_animation, self._hover, 0.0)
        super().leaveEvent(event)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._ripple_origin = event.position()
            self._ripple = 0.0
            self._animate(self._ripple_animation, 0.0, 1.0)
            self._animate(self._press_animation, self._press, 1.0)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._animate(self._press_animation, self._press, 0.0)
        super().mouseReleaseEvent(event)

    @staticmethod
    def _mixed(first: QColor, second: QColor, amount: float) -> QColor:
        value = max(0.0, min(1.0, amount))
        return QColor(
            int(first.red() + (second.red() - first.red()) * value),
            int(first.green() + (second.green() - first.green()) * value),
            int(first.blue() + (second.blue() - first.blue()) * value),
            int(first.alpha() + (second.alpha() - first.alpha()) * value),
        )

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        light = self.property("theme") == "light"
        accent = QColor(self.property("accent") or "#8B7CFF")
        neutral = QColor("#F0F1F5" if light else "#202230")
        neutral_hover = QColor("#E4E6EE" if light else "#2B2D3B")
        background = (
            self._mixed(neutral, neutral_hover, self._hover)
            if self._active
            else self._mixed(accent, accent.lighter(112), self._hover)
        )
        border = QColor("#C9CDD8" if light else "#3A3C4B") if self._active else accent
        foreground = QColor("#343744" if light and self._active else "#F4F3FA")
        inset = 1.5 + self._press * 1.5
        rect = QRectF(inset, inset, self.width() - inset * 2, self.height() - inset * 2)

        painter.setPen(QPen(border, 1.2))
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 12, 12)

        if self._ripple < 1.0:
            painter.save()
            clip = QPainterPath()
            clip.addRoundedRect(rect, 12, 12)
            painter.setClipPath(clip)
            ripple = QColor("#FFFFFF")
            ripple.setAlpha(int(72 * (1.0 - self._ripple)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(ripple)
            radius = max(self.width(), self.height()) * self._ripple
            painter.drawEllipse(self._ripple_origin, radius, radius)
            painter.restore()

        painter.setPen(QPen(foreground, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        icon_x = 25.0 + self._hover * 2.0
        center_y = self.height() / 2
        if self._active:
            painter.drawLine(QPointF(icon_x - 3, center_y - 6), QPointF(icon_x - 3, center_y + 6))
            painter.drawLine(QPointF(icon_x + 3, center_y - 6), QPointF(icon_x + 3, center_y + 6))
        else:
            play = QPainterPath()
            play.moveTo(icon_x - 4, center_y - 7)
            play.lineTo(icon_x + 7, center_y)
            play.lineTo(icon_x - 4, center_y + 7)
            play.closeSubpath()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(foreground)
            painter.drawPath(play)
        painter.setPen(foreground)
        font = QFont("Segoe UI Variable", 10)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(
            QRectF(42, 0, self.width() - 52, self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.text(),
        )


class ProfileSlider(QWidget):
    """A four-stop slider that previews while dragging and commits on release."""

    previewed = Signal(str)
    activated = Signal(str)

    def __init__(
        self,
        options: list[tuple[str, str, str]],
        selected_id: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        if not options:
            raise ValueError("ProfileSlider requires at least one option")
        self.options = options
        self._dragging = False
        self._preview_index = self._index_for(selected_id)
        self._position = float(self._preview_index)
        self._animation = QPropertyAnimation(self, b"position", self)
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setMinimumHeight(86)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName("Protection profile")

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(620, 86)

    def selected_id(self) -> str:
        return self.options[self._preview_index][0]

    def set_selected(self, profile_id: str, emit_preview: bool = False) -> None:
        index = self._index_for(profile_id)
        self._animation.stop()
        self._preview_index = index
        self._position = float(index)
        self.update()
        if emit_preview:
            self.previewed.emit(self.options[index][0])

    def get_position(self) -> float:
        return self._position

    def set_position(self, value: float) -> None:
        self._position = max(0.0, min(float(len(self.options) - 1), float(value)))
        self.update()

    position = Property(float, get_position, set_position)

    def _index_for(self, profile_id: str) -> int:
        return next((index for index, option in enumerate(self.options) if option[0] == profile_id), 0)

    def _track_geometry(self) -> tuple[float, float, float]:
        return 58.0, max(58.0, self.width() - 58.0), 26.0

    def _raw_position(self, x: float) -> float:
        left, right, _ = self._track_geometry()
        if right <= left:
            return 0.0
        return max(0.0, min(float(len(self.options) - 1), (x - left) / (right - left) * (len(self.options) - 1)))

    @staticmethod
    def _magnetized(raw: float) -> float:
        nearest = round(raw)
        distance = abs(raw - nearest)
        if distance < 0.34:
            return nearest + (raw - nearest) * 0.24
        return raw

    def _preview_at(self, x: float) -> None:
        raw = self._raw_position(x)
        self.set_position(self._magnetized(raw))
        index = max(0, min(len(self.options) - 1, int(round(raw))))
        if index != self._preview_index:
            self._preview_index = index
            self.previewed.emit(self.options[index][0])

    def _snap(self, index: int, activate: bool) -> None:
        index = max(0, min(len(self.options) - 1, index))
        if index != self._preview_index:
            self._preview_index = index
            self.previewed.emit(self.options[index][0])
        self._animation.stop()
        self._animation.setStartValue(self._position)
        self._animation.setEndValue(float(index))
        self._animation.start()
        if activate:
            self.activated.emit(self.options[index][0])

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._dragging = True
            self._animation.stop()
            self._preview_at(event.position().x())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._dragging:
            self._preview_at(event.position().x())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._preview_at(event.position().x())
            self._snap(self._preview_index, activate=True)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Down):
            self._snap(self._preview_index - 1, activate=True)
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Up):
            self._snap(self._preview_index + 1, activate=True)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Home:
            self._snap(0, activate=True)
            event.accept()
            return
        if event.key() == Qt.Key.Key_End:
            self._snap(len(self.options) - 1, activate=True)
            event.accept()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        light = self.property("theme") == "light"
        accent = QColor(self.options[self._preview_index][2])
        track = QColor("#D8DAE3" if light else "#303240")
        text = QColor("#777A88" if light else "#9293A4")
        strong_text = QColor("#20212A" if light else "#F4F3FA")
        surface = QColor("#FFFFFF" if light else "#13151F")
        left, right, y = self._track_geometry()
        step = (right - left) / max(1, len(self.options) - 1)
        knob_x = left + step * self._position

        painter.setPen(QPen(track, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(left, y), QPointF(right, y))
        painter.setPen(QPen(accent, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(left, y), QPointF(knob_x, y))

        painter.setPen(Qt.PenStyle.NoPen)
        for index, (_profile_id, _label, color) in enumerate(self.options):
            x = left + step * index
            proximity = max(0.0, 1.0 - abs(self._position - index) / 0.65)
            radius = 6.0 + 3.5 * proximity
            painter.setBrush(QColor(color) if proximity > 0.45 else track)
            painter.drawEllipse(QPointF(x, y), radius, radius)

        painter.setBrush(surface)
        painter.setPen(QPen(accent, 3))
        painter.drawEllipse(QPointF(knob_x, y), 10.5, 10.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawEllipse(QPointF(knob_x, y), 4.5, 4.5)

        font = QFont("Segoe UI Variable", 9)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        for index, (_profile_id, label, _color) in enumerate(self.options):
            x = left + step * index
            painter.setPen(strong_text if index == self._preview_index else text)
            painter.drawText(
                QRectF(x - 68, y + 18, 136, 28),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                label,
            )


class StatusOrb(QWidget):
    def __init__(self, active: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(112, 112)
        self._active = active
        self._pulse = 0.0
        self._animation = QPropertyAnimation(self, b"pulse", self)
        self._animation.setDuration(2200)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setLoopCount(-1)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutSine)

    def set_active(self, active: bool) -> None:
        self._active = active
        self._sync_animation()
        self.update()

    def _sync_animation(self) -> None:
        should_run = self._active and self.isVisible()
        running = self._animation.state() == QAbstractAnimation.State.Running
        if should_run and not running:
            self._animation.start()
        elif not should_run and running:
            self._animation.stop()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self._sync_animation()

    def hideEvent(self, event):  # noqa: N802
        self._animation.stop()
        super().hideEvent(event)

    def get_pulse(self) -> float:
        return self._pulse

    def set_pulse(self, value: float) -> None:
        self._pulse = value
        self.update()

    pulse = Property(float, get_pulse, set_pulse)

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        accent = QColor(self.property("accent") or "#8B7CFF")
        light = self.property("theme") == "light"
        base = accent if self._active else QColor("#9296A3" if light else "#555766")
        pulse = (1 - abs(self._pulse * 2 - 1)) if self._active else 0
        halo = QColor(base)
        halo.setAlpha(int(22 + 26 * pulse))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(center, 47 + 2.5 * pulse, 47 + 2.5 * pulse)
        ring = QColor(base)
        ring.setAlpha(55)
        painter.setBrush(ring)
        painter.drawEllipse(center, 40, 40)
        painter.setBrush(QColor("#FFFFFF" if light else "#13151F"))
        painter.drawEllipse(center, 33, 33)
        pen = QPen(base, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(QRectF(center.x() - 21, center.y() - 21, 42, 42), 38 * 16, 284 * 16)
        painter.drawLine(QPointF(center.x(), center.y() - 25), QPointF(center.x(), center.y() - 5))


class SettingRow(QFrame):
    toggled = Signal(bool)

    def __init__(self, title: str, detail: str, checked: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("settingRow")
        self.setMinimumHeight(76)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 12, 16, 12)
        text = QVBoxLayout()
        text.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        text.addWidget(title_label)
        if detail:
            detail_label = QLabel(detail)
            detail_label.setObjectName("muted")
            detail_label.setWordWrap(True)
            text.addWidget(detail_label)
        layout.addLayout(text, 1)
        self.toggle = ToggleSwitch(checked)
        self.toggle.toggled.connect(self.toggled)
        layout.addWidget(self.toggle)

    def setChecked(self, checked: bool) -> None:
        self.toggle.setChecked(checked)


class MetricCard(QFrame):
    def __init__(self, label: str, value: str, detail: str, color: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(124)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 15)
        layout.setSpacing(6)
        top = QHBoxLayout()
        title = QLabel(label.upper())
        title.setObjectName("tiny")
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {color}; font-size: 11px;")
        top.addWidget(title)
        top.addStretch()
        top.addWidget(dot)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("metric")
        self.detail_label = QLabel(detail)
        self.detail_label.setObjectName("muted")
        layout.addLayout(top)
        layout.addWidget(self.value_label)
        layout.addWidget(self.detail_label)

    def set_value(self, value: str, detail: str | None = None) -> None:
        self.value_label.setText(value)
        if detail is not None:
            self.detail_label.setText(detail)


class EmptyState(QFrame):
    def __init__(self, title: str, detail: str, button_text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("softCard")
        self.setMinimumHeight(150)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(7)
        icon = QLabel("✦")
        icon.setObjectName("accentGlyph")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name = QLabel(title)
        name.setObjectName("cardTitle")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)
        layout.addWidget(name)
        if detail:
            body = QLabel(detail)
            body.setObjectName("muted")
            body.setAlignment(Qt.AlignmentFlag.AlignCenter)
            body.setWordWrap(True)
            layout.addWidget(body)
        self.button = QPushButton(button_text) if button_text else None
        if self.button:
            self.button.setObjectName("ghostButton")
            layout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignCenter)


def add_shadow(widget: QWidget, blur: int = 32, opacity: int = 65, y: int = 8) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y)
    effect.setColor(QColor(0, 0, 0, opacity))
    widget.setGraphicsEffect(effect)


def page_header(eyebrow: str, title: str, subtitle: str) -> tuple[QVBoxLayout, QLabel]:
    layout = QVBoxLayout()
    layout.setSpacing(5)
    title_label = QLabel(title)
    title_label.setObjectName("pageTitle")
    if eyebrow:
        eyebrow_label = QLabel(eyebrow.upper())
        eyebrow_label.setObjectName("eyebrow")
        layout.addWidget(eyebrow_label)
    layout.addWidget(title_label)
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("pageSubtitle")
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)
    return layout, title_label


def configure_accents(root: QWidget, accent_name: str, theme: str = "dark") -> None:
    accent = ACCENTS.get(accent_name, ACCENTS["violet"])
    for widget in root.findChildren(ToggleSwitch):
        widget.setProperty("accent", accent)
        widget.setProperty("theme", theme)
        widget.update()
    for widget in root.findChildren(StatusOrb):
        widget.setProperty("accent", accent)
        widget.setProperty("theme", theme)
        widget.update()
    for widget in root.findChildren(ProtectionButton):
        widget.setProperty("accent", accent)
        widget.setProperty("theme", theme)
        widget.update()
    for widget in root.findChildren(ProfileSlider):
        widget.setProperty("accent", accent)
        widget.setProperty("theme", theme)
        widget.update()
    for widget in root.findChildren(AccentPicker):
        widget.setProperty("theme", theme)
        widget.update()
