from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from .constants import ACCENTS


PALETTES = {
    "dark": {
        "bg": "#0A0B12",
        "sidebar": "#0E0F18",
        "surface": "#13151F",
        "surface_alt": "#10121A",
        "surface_hover": "#202230",
        "surface_pressed": "#1B1D29",
        "hero_a": "#171927",
        "hero_b": "#151722",
        "hero_c": "#201B32",
        "selected": "#211F32",
        "selected_surface": "#191829",
        "input": "#0E1018",
        "border": "#242633",
        "border_strong": "#343645",
        "text": "#F4F3FA",
        "text_soft": "#BEBECB",
        "muted": "#9293A4",
        "faint": "#77798D",
        "disabled": "#666879",
        "accent_text": "#0A0B12",
        "tag": "#20222E",
        "tag_text": "#A8A9B8",
        "scroll": "#343544",
        "menu_hover": "#292B3A",
        "danger_bg": "#2B1820",
        "danger_border": "#552A38",
    },
    "light": {
        "bg": "#F5F6FA",
        "sidebar": "#FFFFFF",
        "surface": "#FFFFFF",
        "surface_alt": "#F7F8FB",
        "surface_hover": "#ECEEF4",
        "surface_pressed": "#E2E5ED",
        "hero_a": "#FFFFFF",
        "hero_b": "#F8F7FC",
        "hero_c": "#F0ECFF",
        "selected": "#EEEAFE",
        "selected_surface": "#F8F6FF",
        "input": "#F8F9FC",
        "border": "#E1E3EA",
        "border_strong": "#C9CDD8",
        "text": "#20212A",
        "text_soft": "#4F5260",
        "muted": "#6B6E7B",
        "faint": "#8B8E9A",
        "disabled": "#A7AAB4",
        "accent_text": "#FFFFFF",
        "tag": "#F0F1F5",
        "tag_text": "#646775",
        "scroll": "#C8CBD5",
        "menu_hover": "#ECEEF4",
        "danger_bg": "#FFF0F3",
        "danger_border": "#F5C2CC",
    },
}


def colors(mode: str = "dark") -> dict[str, str]:
    return PALETTES.get(mode, PALETTES["dark"])


def apply_palette(app: QApplication, mode: str = "dark") -> None:
    c = colors(mode)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(c["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(c["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(c["input"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(c["surface_alt"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(c["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(c["surface_hover"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(c["text"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(c["surface"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(c["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#8B7CFF"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(c["faint"]))
    app.setPalette(palette)


def menu_stylesheet(mode: str = "dark", accent_name: str = "violet") -> str:
    c = colors(mode)
    accent = ACCENTS.get(accent_name, ACCENTS["violet"])
    return f"""
    QMenu {{
        background-color: {c['surface']};
        color: {c['text']};
        border: 1px solid {c['border_strong']};
        border-radius: 10px;
        padding: 7px;
        font-family: "Segoe UI Variable", "Segoe UI";
        font-size: 12px;
    }}
    QMenu::item {{
        background-color: transparent;
        color: {c['text']};
        border-radius: 7px;
        padding: 9px 30px 9px 12px;
        margin: 1px 0;
    }}
    QMenu::item:selected {{ background-color: {c['selected']}; color: {c['text']}; }}
    QMenu::item:disabled {{ color: {c['disabled']}; }}
    QMenu::separator {{ height: 1px; background: {c['border']}; margin: 6px 7px; }}
    QMenu::icon {{ padding-left: 6px; }}
    """


def stylesheet(accent_name: str = "violet", mode: str = "dark") -> str:
    c = colors(mode)
    accent = ACCENTS.get(accent_name, ACCENTS["violet"])
    accent_hover = "#A99FFF" if accent_name == "violet" else accent
    return f"""
    * {{
        font-family: "Segoe UI Variable", "Segoe UI";
        color: {c['text']};
        outline: none;
    }}
    QMainWindow, QWidget#appRoot, QWidget#pageHost {{ background-color: {c['bg']}; }}
    QDialog {{ background-color: {c['surface']}; color: {c['text']}; }}
    QDialog#modalDialog {{ background-color: {c['bg']}; }}
    QWidget#sidebar {{
        background-color: {c['sidebar']};
        border-right: 1px solid {c['border']};
    }}
    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {c['scroll']}; border-radius: 4px; min-height: 28px; }}
    QScrollBar::handle:vertical:hover {{ background: {c['border_strong']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

    QLabel#brandName {{ font-size: 20px; font-weight: 700; letter-spacing: 0.3px; }}
    QLabel#brandCaption {{ color: {c['faint']}; font-size: 11px; }}
    QLabel#eyebrow {{ color: {accent}; font-size: 11px; font-weight: 700; letter-spacing: 1.6px; }}
    QLabel#pageTitle {{ font-size: 30px; font-weight: 700; }}
    QLabel#pageSubtitle {{ color: {c['muted']}; font-size: 13px; }}
    QLabel#sectionTitle {{ font-size: 17px; font-weight: 650; }}
    QLabel#cardTitle {{ font-size: 14px; font-weight: 650; }}
    QLabel#muted {{ color: {c['muted']}; font-size: 12px; }}
    QLabel#tiny {{ color: {c['faint']}; font-size: 10px; }}
    QLabel#metric {{ font-size: 27px; font-weight: 700; }}
    QLabel#heroTitle {{ font-size: 26px; font-weight: 720; }}
    QLabel#heroSubtitle {{ color: {c['text_soft']}; font-size: 13px; }}
    QLabel#statusOn {{ color: #2C9F7B; font-size: 12px; font-weight: 650; }}
    QLabel#statusOff {{ color: #D94E6A; font-size: 12px; font-weight: 650; }}
    QLabel#profilePill {{
        background: {c['selected']}; border: 1px solid {c['border_strong']}; border-radius: 9px;
        padding: 6px 10px; color: {c['text_soft']}; font-size: 11px;
    }}
    QLabel#accentTile {{ background: {c['selected']}; color: {accent}; border-radius: 9px; font-size: 15px; }}
    QLabel#accentGlyph {{ color: {accent}; font-size: 24px; }}
    QLabel#tagPill {{ background: {c['tag']}; color: {c['tag_text']}; border-radius: 7px; padding: 4px 7px; font-size: 10px; }}
    QLabel#infoBadge {{ background: {c['selected']}; color: {accent}; border-radius: 12px; font-weight: 700; }}
    QLabel#dayBadge {{ background: {c['surface_alt']}; color: {c['faint']}; border-radius: 6px; font-size: 9px; }}
    QLabel#dayBadge[active="true"] {{ background: {c['selected']}; color: {accent}; }}
    QLabel#countdownIcon {{ background: {c['selected']}; color: {accent}; border-radius: 10px; font-size: 17px; }}
    QLabel#countdownPhase {{ color: #C18A21; font-size: 11px; font-weight: 750; letter-spacing: 0.8px; }}
    QLabel#countdownPhase[windowOpen="true"] {{ color: #2C9F7B; }}
    QLabel#countdownValue {{ color: {c['text']}; font-size: 24px; font-weight: 750; font-family: "Cascadia Mono", "Consolas"; }}
    QLabel#dialogEyebrow {{ color: {accent}; font-size: 10px; font-weight: 800; letter-spacing: 1.4px; }}
    QLabel#dialogTitle {{ color: {c['text']}; font-size: 22px; font-weight: 740; }}
    QLabel#dialogBody {{ color: {c['muted']}; font-size: 12px; line-height: 1.45; }}
    QLabel#dialogMessage {{ color: {c['text_soft']}; font-size: 13px; line-height: 1.55; }}
    QLabel#dialogFieldLabel {{ color: {c['faint']}; font-size: 10px; font-weight: 750; letter-spacing: 0.8px; }}
    QLabel#dialogError {{ color: #FF7A90; font-size: 11px; font-weight: 650; }}

    QFrame#card, QFrame#metricCard, QFrame#settingRow, QFrame#listCard {{
        background-color: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 16px;
    }}
    QFrame#heroCard {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {c['hero_a']}, stop:0.62 {c['hero_b']}, stop:1 {c['hero_c']});
        border: 1px solid {c['border_strong']};
        border-radius: 22px;
    }}
    QFrame#heroCard[active="true"] {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {c['hero_a']}, stop:0.7 {c['hero_b']}, stop:1 {'#EAFBF6' if mode == 'light' else '#13231F'});
        border-color: {'#A8E8D5' if mode == 'light' else '#285E50'};
    }}
    QFrame#profileCard {{
        background-color: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 18px;
    }}
    QFrame#profileDetailCard {{
        background-color: {c['selected_surface']};
        border: 1px solid {accent};
        border-radius: 16px;
    }}
    QFrame#profileCard[selected="true"] {{
        background-color: {c['selected_surface']};
        border: 2px solid {accent};
    }}
    QFrame#softCard {{
        background-color: {c['surface_alt']};
        border: 1px solid {c['border']};
        border-radius: 13px;
    }}
    QFrame#dialogPanel {{
        background-color: {c['surface']}; border: 1px solid {c['border_strong']}; border-radius: 16px;
    }}
    QFrame#countdownCard {{
        background-color: {c['surface_alt']}; border: 1px solid #E0B65F; border-radius: 13px;
    }}
    QFrame#countdownCard[phase="window"] {{ border-color: #53BFA0; }}
    QFrame#wizardPanel {{
        background-color: {c['surface_alt']}; border: 1px solid {c['border']}; border-radius: 14px;
    }}
    QFrame#wizardSummary {{
        background-color: {c['selected_surface']}; border: 1px solid {accent}; border-radius: 14px;
    }}
    QFrame#usageControls {{
        background-color: {c['surface_alt']}; border: 1px solid {c['border']}; border-radius: 13px;
    }}
    QFrame#usageChartCard {{
        background-color: {c['surface']}; border: 1px solid {c['border']}; border-radius: 18px;
    }}
    QFrame#usageRow {{
        background-color: {c['surface']}; border: 1px solid {c['border']}; border-radius: 14px;
    }}
    QFrame#usageRow:hover {{ background-color: {c['surface_hover']}; border-color: {c['border_strong']}; }}
    QFrame#usageRow[selected="true"] {{ background-color: {c['selected_surface']}; border: 2px solid {accent}; }}
    QLabel#usageIconFallback {{
        background: transparent; border: none; font-size: 16px; font-weight: 760;
    }}
    QLabel#usageTotal {{ font-size: 29px; font-weight: 760; }}
    QLabel#usageDuration {{ font-size: 13px; font-weight: 700; min-width: 70px; }}
    QLabel#usageArrow {{ color: {c['faint']}; font-size: 24px; }}

    QPushButton {{
        background-color: {c['surface_hover']};
        border: 1px solid {c['border_strong']};
        border-radius: 10px;
        min-height: 18px;
        padding: 9px 14px;
        font-size: 12px;
        font-weight: 600;
    }}
    QPushButton:hover {{ background-color: {c['menu_hover']}; border-color: {c['border_strong']}; }}
    QPushButton:pressed {{ background-color: {c['surface_pressed']}; }}
    QPushButton:disabled {{ color: {c['disabled']}; background-color: {c['surface_alt']}; border-color: {c['border']}; }}
    QPushButton#primaryButton {{
        background-color: {accent};
        color: {c['accent_text']};
        border: none;
        padding: 11px 18px;
        font-weight: 700;
    }}
    QPushButton#primaryButton:hover {{ background-color: {accent_hover}; }}
    QPushButton#primaryButton:disabled {{ background-color: {c['surface_alt']}; color: {c['disabled']}; border: 1px solid {c['border']}; }}
    QPushButton#protectionButton {{ background: transparent; border: none; min-height: 0; padding: 0; }}
    QPushButton#dangerButton {{ background-color: {c['danger_bg']}; color: #D94E6A; border-color: {c['danger_border']}; }}
    QPushButton#ghostButton {{ background: transparent; border-color: {c['border_strong']}; }}
    QPushButton#linkButton {{ background: transparent; border: none; color: {accent}; min-height: 0; padding: 4px; text-align: left; }}
    QPushButton#chartNavButton {{
        background-color: {c['surface_alt']}; border: 1px solid {c['border_strong']};
        border-radius: 10px; min-width: 38px; max-width: 38px; min-height: 34px; max-height: 34px;
        padding: 0 0 3px 0; color: {accent}; font-size: 25px; font-weight: 650;
    }}
    QPushButton#chartNavButton:hover {{ background-color: {c['selected']}; border-color: {accent}; }}
    QPushButton#navButton {{
        background: transparent;
        border: none;
        border-radius: 11px;
        color: {c['muted']};
        text-align: left;
        padding: 10px 13px;
        font-size: 13px;
        font-weight: 550;
    }}
    QPushButton#navButton:hover {{ background-color: {c['surface_alt']}; color: {c['text_soft']}; }}
    QPushButton#navButton:checked {{ background-color: {c['selected']}; color: {c['text']}; }}
    QPushButton#themeButton {{ min-width: 76px; }}
    QPushButton#themeButton:checked {{ background-color: {c['selected']}; border: 2px solid {accent}; color: {c['text']}; }}
    QPushButton#accentPicker {{
        min-width: 62px; max-width: 62px; min-height: 42px; max-height: 42px;
        padding: 0; border: none; background: transparent;
    }}
    QPushButton#segmentButton {{
        background: transparent; border: none; border-radius: 8px; min-height: 16px; padding: 7px 13px;
        color: {c['muted']};
    }}
    QPushButton#segmentButton:hover {{ background-color: {c['surface_hover']}; color: {c['text']}; }}
    QPushButton#segmentButton:checked {{ background-color: {c['surface']}; color: {c['text']}; border: 1px solid {c['border_strong']}; }}
    QPushButton#wizardChoice {{
        background-color: {c['surface_alt']}; border: 1px solid {c['border_strong']}; border-radius: 14px;
        padding: 14px 17px; text-align: left; font-size: 13px; line-height: 1.5;
    }}
    QPushButton#wizardChoice:hover {{ background-color: {c['surface_hover']}; }}
    QPushButton#wizardChoice:checked {{ background-color: {c['selected_surface']}; border: 2px solid {accent}; }}
    QPushButton#wizardPill, QPushButton#wizardDay {{
        background-color: {c['surface_alt']}; border: 1px solid {c['border_strong']}; border-radius: 10px;
        padding: 10px 8px;
    }}
    QPushButton#wizardPill:checked, QPushButton#wizardDay:checked {{
        background-color: {c['selected']}; border: 2px solid {accent}; color: {c['text']};
    }}
    QLabel#wizardStep {{
        background-color: {c['surface_alt']}; color: {c['faint']}; border: 1px solid {c['border']};
        border-radius: 9px; padding: 6px 8px; font-size: 10px; font-weight: 650;
    }}
    QLabel#wizardStep[current="true"] {{ background-color: {c['selected']}; color: {accent}; border-color: {accent}; }}
    QLabel#wizardStep[completed="true"] {{ color: #2C9F7B; border-color: #53BFA0; }}

    QLineEdit, QTimeEdit, QSpinBox, QComboBox {{
        background-color: {c['input']};
        border: 1px solid {c['border_strong']};
        border-radius: 10px;
        padding: 9px 11px;
        selection-background-color: {accent};
        color: {c['text']};
        font-size: 12px;
    }}
    QLineEdit:focus, QTimeEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {accent}; }}
    QLineEdit::placeholder {{ color: {c['faint']}; }}
    QComboBox::drop-down {{ border: none; width: 28px; }}
    QComboBox QAbstractItemView {{
        background-color: {c['surface']}; color: {c['text']};
        border: 1px solid {c['border_strong']};
        border-radius: 8px; padding: 5px;
        selection-background-color: {c['selected']}; selection-color: {c['text']};
    }}
    QSpinBox::up-button, QSpinBox::down-button, QTimeEdit::up-button, QTimeEdit::down-button {{ width: 0; }}

    QListWidget {{ background: transparent; border: none; padding: 0; color: {c['text']}; }}
    QListWidget::item {{
        background-color: {c['surface_alt']};
        border: 1px solid {c['border']};
        border-radius: 10px;
        padding: 10px 12px;
        margin-bottom: 5px;
    }}
    QListWidget::item:selected {{ background-color: {c['selected']}; border-color: {accent}; color: {c['text']}; }}
    QProgressBar {{ background: {c['surface_alt']}; border: none; border-radius: 4px; }}
    QProgressBar::chunk {{ background: {accent}; border-radius: 4px; }}
    QCheckBox {{ color: {c['text_soft']}; spacing: 8px; font-size: 12px; }}
    QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px; border: 1px solid {c['border_strong']}; background: {c['surface_alt']}; }}
    QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; }}

    QToolTip {{ background-color: {c['surface']}; color: {c['text']}; border: 1px solid {c['border_strong']}; padding: 6px; }}
    {menu_stylesheet(mode, accent_name)}
    """
