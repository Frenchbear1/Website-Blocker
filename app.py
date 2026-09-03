from __future__ import annotations

import argparse
import ctypes
import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QLockFile, QStandardPaths, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from website_blocker.constants import APP_ID, APP_NAME
from website_blocker.dialogs import show_message
from website_blocker.main_window import MainWindow
from website_blocker.storage import EventStore, SettingsStore, UsageStore
from website_blocker.system_filter import PreviewSystemFilter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Website blocking and screen-time controls")
    parser.add_argument("--background", action="store_true", help="Start in the system tray")
    parser.add_argument("--preview", action="store_true", help="Use a non-mutating preview filter")
    parser.add_argument("--screenshot", type=Path, help="Save a UI screenshot and exit")
    parser.add_argument(
        "--page", choices=["dashboard", "usage", "profiles", "rules", "schedule", "limits", "settings"], default="dashboard"
    )
    parser.add_argument("--theme", choices=["dark", "light"], help="Override the saved theme for preview or QA")
    return parser.parse_args()


def configure_app(app: QApplication) -> None:
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    font = QFont("Segoe UI Variable", 10)
    app.setFont(font)
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#0A0B12"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#F4F3FA"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#10121A"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#F4F3FA"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#8B7CFF"))
    app.setPalette(palette)
    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except (AttributeError, OSError):
            pass


def should_show_already_running_message(args: argparse.Namespace) -> bool:
    return not args.background


def main() -> int:
    args = parse_args()
    app = QApplication(sys.argv)
    configure_app(app)

    lock_path = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation)) / "website-blocker-app.lock"
    lock = QLockFile(str(lock_path))
    lock.setStaleLockTime(0)
    if not args.preview and not lock.tryLock(100):
        if should_show_already_running_message(args):
            show_message(None, APP_NAME, "Website Blocker is already running in the system tray.")
        return 0

    if args.preview:
        preview_root = Path(tempfile.mkdtemp(prefix="website-blocker-preview-"))
        settings_store = SettingsStore(preview_root / "settings.json")
        event_store = EventStore(preview_root / "events.json")
        usage_store = UsageStore(preview_root / "usage.db")
        window = MainWindow(settings_store, event_store, usage_store, PreviewSystemFilter(), preview=True)
    else:
        window = MainWindow()
    app.aboutToQuit.connect(window.shutdown)

    if args.theme and args.theme != window.settings.theme:
        window.set_preference("theme", args.theme)

    if not args.background or args.screenshot:
        window.show()
        window.navigate(args.page, animate=False)
        QTimer.singleShot(50, window.apply_windows_frame)

    if args.screenshot:
        output = args.screenshot.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)

        def capture() -> None:
            window.grab().save(str(output), "PNG")
            window._force_quit = True
            window.tray.hide()
            app.quit()

        QTimer.singleShot(900, capture)

    exit_code = app.exec()
    if not args.preview:
        lock.unlock()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
