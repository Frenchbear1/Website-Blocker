import os
from datetime import date, datetime, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QFrame, QPushButton

from website_blocker.constants import DNS_PRESETS
from website_blocker.dialogs import MessageDialog, PinDialog, ScheduleDialog
from website_blocker.main_window import MainWindow
from website_blocker.models import AppSettings, ScreenUsageEntry
from website_blocker.pages import DomainColumn, LimitsPage, ProfilesPage, SchedulePage, SettingsPage
from website_blocker.security import create_pin_hash
from website_blocker.storage import EventStore, SettingsStore, UsageStore
from website_blocker.system_filter import PreviewSystemFilter
from website_blocker.theme import stylesheet
from website_blocker.usage_page import ScreenUsagePage, UsageRow, usage_period
from website_blocker.widgets import ProfileSlider, ProtectionButton, ToggleSwitch


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _options() -> list[tuple[str, str, str]]:
    return [(profile_id, data["name"], data["color"]) for profile_id, data in DNS_PRESETS.items()]


def test_profile_slider_snaps_to_custom_and_emits_activation():
    _app()
    slider = ProfileSlider(_options(), "strong")
    slider.resize(680, 86)
    slider.show()
    activated = QSignalSpy(slider.activated)
    _left, right, y = slider._track_geometry()

    QTest.mouseClick(slider, Qt.MouseButton.LeftButton, pos=QPoint(int(right), int(y)))
    QTest.qWait(180)

    assert slider.selected_id() == "custom"
    assert activated.count() == 1
    assert activated.at(0) == ["custom"]


def test_custom_dns_fields_only_show_for_custom_profile():
    _app()
    page = ProfilesPage(AppSettings(active_profile="strong"))
    assert not page.custom_dns_card.isVisible()

    page._show_profile("custom")
    page.show()

    assert page.custom_dns_card.isVisible()
    assert page.profile_name.text() == "Custom DNS"


def test_domain_column_hides_empty_list_space():
    _app()
    column = DomainColumn("Blocked sites", "example.com", "Block")
    column.set_domains([])
    assert column.list.isHidden()
    assert column.remove_button.isHidden()

    column.set_domains(["example.com"])
    assert not column.list.isHidden()
    assert not column.remove_button.isHidden()
    assert column.list.height() <= 188


def test_protection_button_uses_resume_and_pause_actions():
    _app()
    button = ProtectionButton(active=False)
    assert button.text() == "Resume protection"

    button.set_active(True)

    assert button.text() == "Pause protection"


def test_settings_page_only_shows_remove_pin_when_a_pin_exists():
    _app()
    page = SettingsPage(AppSettings(lock_enabled=False))
    assert page.remove_pin_button.isHidden()

    page.refresh(AppSettings(lock_enabled=True, pin_salt="salt", pin_hash="digest"))

    assert not page.remove_pin_button.isHidden()
    assert page.remove_pin_button.text() == "Remove PIN"


def test_tracking_pages_blur_and_disable_content_when_switched_off():
    _app()
    limits = LimitsPage(AppSettings(limits_enabled=False))
    usage = ScreenUsagePage(AppSettings(screen_usage_enabled=False))

    assert not limits.gated_content.isEnabled()
    assert limits.disabled_blur.isEnabled()
    assert not limits.add_button.isEnabled()
    assert not usage.gated_content.isEnabled()
    assert usage.disabled_blur.isEnabled()

    limits.set_enabled(True)
    usage.set_enabled(True)

    assert limits.gated_content.isEnabled()
    assert not limits.disabled_blur.isEnabled()
    assert usage.gated_content.isEnabled()
    assert not usage.disabled_blur.isEnabled()


def test_screen_usage_icons_float_without_a_container():
    _app()
    row = UsageRow(
        ScreenUsageEntry("app", "notepad.exe", "Notepad", 60, r"C:\Windows\notepad.exe"),
        60,
    )

    assert row.findChild(QFrame, "usageIconBox") is None


def test_accent_choices_are_textless_centered_pills():
    app = _app()
    page = SettingsPage(AppSettings())
    page.setStyleSheet(stylesheet("violet", "light"))
    page.show()
    app.processEvents()

    for button in page.accent_group.buttons():
        assert button.text() == ""
        assert button.size().width() == 62
        assert button.size().height() == 42
        assert button.accessibleName().endswith(" accent")


def test_schedule_toggle_is_compact_and_sits_in_the_header_controls():
    _app()
    page = SchedulePage(AppSettings(schedule_enabled=True))

    assert isinstance(page.master, ToggleSwitch)
    assert page.master.isChecked()
    assert page.add_button.text() == "Add schedule"
    assert page.gated_content.isEnabled()
    assert not page.disabled_blur.isEnabled()

    page.set_enabled(False)

    assert not page.gated_content.isEnabled()
    assert page.disabled_blur.isEnabled()
    assert not page.add_button.isEnabled()


def test_shared_popups_use_roomy_styled_dialog_shells():
    _app()
    message = MessageDialog("Quit Website Blocker?", "Schedules and limits stop running.", "question", "Quit", True)
    pin = PinDialog("Verify PIN", "Enter the current PIN.")
    schedule = ScheduleDialog()

    assert message.objectName() == "modalDialog"
    assert message.minimumWidth() >= 540
    quit_button = next(button for button in message.findChildren(QPushButton) if button.text() == "Quit")
    assert quit_button.objectName() == "dangerButton"
    assert pin.minimumWidth() >= 500
    assert schedule.minimumWidth() >= 560


def test_active_cooldown_change_requires_the_saved_pin(tmp_path, monkeypatch):
    _app()
    salt, digest = create_pin_hash("4827")
    active_deadline = (datetime.now() + timedelta(minutes=20)).isoformat(timespec="seconds")
    settings_store = SettingsStore(tmp_path / "settings.json")
    settings_store.save(
        AppSettings(
            cooldown_minutes=30,
            pause_available_at=active_deadline,
            lock_enabled=True,
            pin_salt=salt,
            pin_hash=digest,
        )
    )
    window = MainWindow(
        settings_store,
        EventStore(tmp_path / "events.json"),
        UsageStore(tmp_path / "usage.db"),
        PreviewSystemFilter(),
        preview=True,
    )

    class FakePinDialog:
        class DialogCode:
            Accepted = 1

        def __init__(self, *_args, **_kwargs):
            self.value = "wrong"

        def exec(self):
            return self.DialogCode.Accepted

    monkeypatch.setattr("website_blocker.main_window.PinDialog", FakePinDialog)
    monkeypatch.setattr("website_blocker.main_window.show_message", lambda *_args, **_kwargs: None)

    window.set_preference("cooldown_minutes", 0)

    assert window.settings.cooldown_minutes == 30
    assert window.settings.pause_available_at == active_deadline

    window.set_preference("pause_window_minutes", 0)

    assert window.settings.pause_window_minutes == 30
    assert window.settings.pause_available_at == active_deadline

    class CorrectPinDialog(FakePinDialog):
        def __init__(self, *_args, **_kwargs):
            self.value = "4827"

    monkeypatch.setattr("website_blocker.main_window.PinDialog", CorrectPinDialog)
    window.set_preference("cooldown_minutes", 0)

    assert window.settings.cooldown_minutes == 0
    assert window.settings.pause_available_at == ""

    window.settings.pause_window_minutes = 0
    window.settings.pause_available_at = (datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds")
    window._reset_close_bound_pause_window()

    assert window.settings.pause_available_at == ""
    window._force_quit = True
    window.tray.hide()
    window.close()


def test_usage_period_builds_complete_day_week_month_and_forever_ranges():
    today = date(2026, 8, 10)

    assert len(usage_period("day", today=today).keys) == 24
    assert usage_period("week", today=today).start.isoformat() == "2026-08-04"
    assert usage_period("month", today=today).days == 10
    forever = usage_period("all", "2026-06-12", today=today)
    assert forever.keys == ("2026-06", "2026-07", "2026-08")
