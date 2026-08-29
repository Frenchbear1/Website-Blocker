from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def shield_icon(size: int = 64, color: str = "#8B7CFF", active: bool = True) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    center = size / 2
    path = QPainterPath()
    path.moveTo(center, size * 0.09)
    path.cubicTo(size * 0.42, size * 0.16, size * 0.25, size * 0.19, size * 0.18, size * 0.21)
    path.lineTo(size * 0.18, size * 0.48)
    path.cubicTo(size * 0.18, size * 0.72, size * 0.33, size * 0.86, center, size * 0.94)
    path.cubicTo(size * 0.67, size * 0.86, size * 0.82, size * 0.72, size * 0.82, size * 0.48)
    path.lineTo(size * 0.82, size * 0.21)
    path.cubicTo(size * 0.75, size * 0.19, size * 0.58, size * 0.16, center, size * 0.09)
    painter.setPen(Qt.PenStyle.NoPen)
    fill = QColor(color)
    if not active:
        fill = fill.darker(135)
    painter.setBrush(fill)
    painter.drawPath(path)
    if active:
        pen = QPen(QColor("#0A0B12"), max(2, size * 0.065), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPointF(size * 0.34, size * 0.50), QPointF(size * 0.45, size * 0.61))
        painter.drawLine(QPointF(size * 0.45, size * 0.61), QPointF(size * 0.68, size * 0.36))
    else:
        pen = QPen(QColor("#0A0B12"), max(2, size * 0.06), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(size * 0.42, size * 0.39), QPointF(size * 0.42, size * 0.62))
        painter.drawLine(QPointF(size * 0.58, size * 0.39), QPointF(size * 0.58, size * 0.62))
    painter.end()
    return QIcon(pixmap)


def dot_icon(color: str, size: int = 16) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(QRectF(3, 3, size - 6, size - 6))
    painter.end()
    return QIcon(pixmap)


def _nav_pixmap(name: str, color: str, size: int = 48) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 24.0, size / 24.0)
    pen = QPen(QColor(color), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if name == "dashboard":
        roof = QPainterPath()
        roof.moveTo(3.5, 10.5)
        roof.lineTo(12, 3.8)
        roof.lineTo(20.5, 10.5)
        painter.drawPath(roof)
        home = QPainterPath()
        home.moveTo(5.5, 9.2)
        home.lineTo(5.5, 20)
        home.lineTo(10, 20)
        home.lineTo(10, 14.2)
        home.lineTo(14, 14.2)
        home.lineTo(14, 20)
        home.lineTo(18.5, 20)
        home.lineTo(18.5, 9.2)
        painter.drawPath(home)
    elif name == "usage":
        painter.drawRoundedRect(QRectF(3.5, 3.5, 17, 17), 3, 3)
        painter.drawLine(QPointF(7, 16.5), QPointF(7, 12.5))
        painter.drawLine(QPointF(12, 16.5), QPointF(12, 8))
        painter.drawLine(QPointF(17, 16.5), QPointF(17, 10.5))
    elif name == "profiles":
        for y, knob_x in ((6.0, 8.0), (12.0, 16.0), (18.0, 11.0)):
            painter.drawLine(QPointF(4, y), QPointF(20, y))
            painter.setBrush(QColor(color))
            painter.drawEllipse(QPointF(knob_x, y), 2.1, 2.1)
            painter.setBrush(Qt.BrushStyle.NoBrush)
    elif name == "rules":
        painter.drawEllipse(QRectF(3.5, 3.5, 17, 17))
        painter.drawArc(QRectF(7.5, 3.5, 9, 17), 90 * 16, 180 * 16)
        painter.drawArc(QRectF(7.5, 3.5, 9, 17), -90 * 16, 180 * 16)
        painter.drawLine(QPointF(4.2, 12), QPointF(19.8, 12))
    elif name == "schedule":
        painter.drawRoundedRect(QRectF(3.5, 5.5, 17, 15), 2.4, 2.4)
        painter.drawLine(QPointF(3.8, 10), QPointF(20.2, 10))
        painter.drawLine(QPointF(8, 3.5), QPointF(8, 7.5))
        painter.drawLine(QPointF(16, 3.5), QPointF(16, 7.5))
        painter.drawLine(QPointF(8, 14), QPointF(11, 17))
        painter.drawLine(QPointF(11, 17), QPointF(16.5, 12.5))
    elif name == "limits":
        painter.drawRoundedRect(QRectF(4, 3.5, 16, 17), 3, 3)
        painter.drawLine(QPointF(12, 7), QPointF(12, 12))
        painter.drawLine(QPointF(12, 12), QPointF(15.5, 14))
        painter.drawLine(QPointF(9, 1.8), QPointF(15, 1.8))
    elif name == "settings":
        painter.drawEllipse(QRectF(8.5, 8.5, 7, 7))
        painter.drawEllipse(QRectF(5, 5, 14, 14))
        for x1, y1, x2, y2 in (
            (12, 2.5, 12, 5),
            (12, 19, 12, 21.5),
            (2.5, 12, 5, 12),
            (19, 12, 21.5, 12),
            (5.3, 5.3, 7.1, 7.1),
            (16.9, 16.9, 18.7, 18.7),
            (18.7, 5.3, 16.9, 7.1),
            (7.1, 16.9, 5.3, 18.7),
        ):
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    painter.end()
    return pixmap


def nav_icon(name: str, normal: str, selected: str, size: int = 48) -> QIcon:
    """Return a crisp line icon with a distinct checked state."""

    icon = QIcon()
    normal_pixmap = _nav_pixmap(name, normal, size)
    selected_pixmap = _nav_pixmap(name, selected, size)
    icon.addPixmap(normal_pixmap, QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(selected_pixmap, QIcon.Mode.Normal, QIcon.State.On)
    icon.addPixmap(selected_pixmap, QIcon.Mode.Active, QIcon.State.Off)
    icon.addPixmap(selected_pixmap, QIcon.Mode.Active, QIcon.State.On)
    return icon
