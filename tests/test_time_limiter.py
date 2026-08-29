from datetime import date, datetime
import time

from lumaguard.models import AppSettings, TimeLimitRule
from lumaguard.storage import UsageStore
from lumaguard.time_limiter import TimeLimitEngine
from lumaguard.win_activity import WindowsApp


def _weekday():
    return datetime.now().weekday()


def test_foreground_app_time_is_counted_and_flushed(tmp_path):
    rule = TimeLimitRule(target="focus.exe", days=[_weekday()], daily_minutes=10)
    settings = AppSettings(time_limits=[rule])
    app = WindowsApp(99, 10, r"C:\Tools\focus.exe", "focus.exe", "Focus")
    engine = TimeLimitEngine(lambda: settings, UsageStore(tmp_path / "usage.db"), preview=True, app_provider=lambda: app)
    for _ in range(3):
        engine.tick()
    assert engine.used_seconds(rule.id) == 3
    engine.flush()
    assert engine.store.seconds_for_rule(rule.id) == 3


def test_reset_usage_clears_stored_and_pending_time_for_only_that_rule(tmp_path):
    first = TimeLimitRule(target="focus.exe", days=[_weekday()], daily_minutes=10)
    second = TimeLimitRule(target="other.exe", days=[_weekday()], daily_minutes=10)
    settings = AppSettings(time_limits=[first, second])
    app = WindowsApp(99, 10, r"C:\Tools\focus.exe", "focus.exe", "Focus")
    store = UsageStore(tmp_path / "usage.db")
    store.add_seconds(first.id, 20)
    store.add_seconds(second.id, 7)
    engine = TimeLimitEngine(lambda: settings, store, preview=True, app_provider=lambda: app)
    engine.tick()
    engine.reset_usage(first.id)
    assert engine.used_seconds(first.id) == 0
    assert engine.used_seconds(second.id) == 7


def test_warning_event_identifies_counted_window(tmp_path):
    rule = TimeLimitRule(target="focus.exe", days=[_weekday()], daily_minutes=1, warning_minutes=1)
    settings = AppSettings(time_limits=[rule])
    app = WindowsApp(99, 10, r"C:\Tools\focus.exe", "focus.exe", "Focus")
    events = []
    engine = TimeLimitEngine(
        lambda: settings, UsageStore(tmp_path / "usage.db"), preview=True, app_provider=lambda: app
    )
    engine.limit_event.connect(lambda kind, title, detail, hwnd: events.append((kind, title, detail, hwnd)))
    engine.tick()
    assert len(events) == 1
    assert events[0][3] == 99


def test_reset_usage_allows_warning_to_fire_again(tmp_path):
    rule = TimeLimitRule(target="focus.exe", days=[_weekday()], daily_minutes=1, warning_minutes=1)
    settings = AppSettings(time_limits=[rule])
    app = WindowsApp(99, 10, r"C:\Tools\focus.exe", "focus.exe", "Focus")
    events = []
    engine = TimeLimitEngine(
        lambda: settings, UsageStore(tmp_path / "usage.db"), preview=True, app_provider=lambda: app
    )
    engine.limit_event.connect(lambda *_args: events.append(True))
    engine.tick()
    engine.reset_usage(rule.id)
    engine.tick()
    assert len(events) == 2


def test_inactive_day_does_not_count(tmp_path):
    rule = TimeLimitRule(target="focus.exe", days=[(_weekday() + 1) % 7])
    settings = AppSettings(time_limits=[rule])
    app = WindowsApp(99, 10, r"C:\Tools\focus.exe", "focus.exe", "Focus")
    engine = TimeLimitEngine(lambda: settings, UsageStore(tmp_path / "usage.db"), preview=True, app_provider=lambda: app)
    engine.tick()
    assert engine.used_seconds(rule.id) == 0


def test_website_heartbeat_counts_elapsed_and_blocks(tmp_path):
    rule = TimeLimitRule(
        target_type="website",
        target="example.com",
        display_name="Example",
        days=[_weekday()],
        daily_minutes=1,
        enforcement="block",
    )
    store = UsageStore(tmp_path / "usage.db")
    settings = AppSettings(time_limits=[rule])
    engine = TimeLimitEngine(lambda: settings, store, preview=True, app_provider=lambda: None)
    engine.record_web_heartbeat("chrome", "news.example.com", now=10)
    engine.record_web_heartbeat("chrome", "news.example.com", now=13)
    assert engine.used_seconds(rule.id) == 3
    store.add_seconds(rule.id, 58)
    status = engine.record_web_heartbeat("chrome", "news.example.com", now=16)
    assert status["blocked"] is True
    assert status["remaining_seconds"] == 0
    assert store.recent_sites() == ["news.example.com"]


def test_warn_only_website_returns_one_in_page_notice_at_limit(tmp_path):
    rule = TimeLimitRule(
        target_type="website",
        target="example.com",
        display_name="Example",
        days=[_weekday()],
        daily_minutes=1,
        enforcement="warn",
        warning_minutes=0,
    )
    store = UsageStore(tmp_path / "usage.db")
    store.add_seconds(rule.id, 60)
    engine = TimeLimitEngine(
        lambda: AppSettings(time_limits=[rule]), store, preview=True, app_provider=lambda: None
    )
    first = engine.record_web_heartbeat("vivaldi", "example.com", now=10)
    second = engine.record_web_heartbeat("vivaldi", "example.com", now=13)
    assert first["blocked"] is False
    assert first["notice"]["kind"] == "limit_reached"
    assert "Daily limit reached" in first["notice"]["title"]
    assert "notice" not in second


def test_website_warning_can_be_turned_into_persistent_block_for_today(tmp_path):
    rule = TimeLimitRule(
        target_type="website",
        target="example.com",
        display_name="Example",
        days=[_weekday()],
        daily_minutes=60,
        enforcement="warn",
    )
    path = tmp_path / "usage.db"
    settings = AppSettings(time_limits=[rule])
    engine = TimeLimitEngine(lambda: settings, UsageStore(path), preview=True, app_provider=lambda: None)
    decision = engine.block_site_today("news.example.com")
    assert decision["blocked"] is True
    assert engine.record_web_heartbeat("chrome", "news.example.com", now=10)["blocked"] is True

    reopened = TimeLimitEngine(lambda: settings, UsageStore(path), preview=True, app_provider=lambda: None)
    assert reopened.record_web_heartbeat("chrome", "news.example.com", now=20)["blocked"] is True
    reopened.reset_usage(rule.id)
    assert reopened.record_web_heartbeat("chrome", "news.example.com", now=23)["blocked"] is False


def test_status_check_does_not_add_blocked_page_time(tmp_path):
    rule = TimeLimitRule(target_type="website", target="example.com", days=[_weekday()])
    engine = TimeLimitEngine(
        lambda: AppSettings(time_limits=[rule]), UsageStore(tmp_path / "usage.db"), preview=True, app_provider=lambda: None
    )
    engine.record_web_heartbeat("edge", "example.com", now=10)
    engine.record_web_heartbeat("edge", "example.com", now=15, active=False)
    engine.record_web_heartbeat("edge", "example.com", now=18)
    assert engine.used_seconds(rule.id) == 0


def test_app_block_uses_normal_close_but_preview_never_does(tmp_path):
    rule = TimeLimitRule(
        target="focus.exe", days=[_weekday()], daily_minutes=1, enforcement="block", warning_minutes=0
    )
    settings = AppSettings(time_limits=[rule])
    app = WindowsApp(99, 10, r"C:\Tools\focus.exe", "focus.exe", "Focus")
    store = UsageStore(tmp_path / "usage.db")
    store.add_seconds(rule.id, 60)
    close_requests = []
    preview = TimeLimitEngine(
        lambda: settings,
        store,
        preview=True,
        app_provider=lambda: app,
        close_request=lambda hwnd: close_requests.append(hwnd) or True,
    )
    preview.tick()
    assert close_requests == []

    live = TimeLimitEngine(
        lambda: settings,
        store,
        preview=False,
        app_provider=lambda: app,
        close_request=lambda hwnd: close_requests.append(hwnd) or True,
    )
    live.tick()
    assert close_requests == [99]


def test_companion_presence_expires(tmp_path):
    engine = TimeLimitEngine(
        lambda: AppSettings(), UsageStore(tmp_path / "usage.db"), preview=True, app_provider=lambda: None
    )
    engine.record_companion_presence("vivaldi", now=100)
    assert engine.connected_companions(now=150) == ["vivaldi"]
    assert engine.connected_companions(now=191) == []


def test_screen_usage_tracks_only_the_foreground_app_without_a_limit(tmp_path):
    settings = AppSettings(screen_usage_enabled=True)
    app = WindowsApp(10, 20, r"C:\Apps\Code.exe", "code.exe", "Code")
    engine = TimeLimitEngine(
        lambda: settings,
        UsageStore(tmp_path / "usage.db"),
        preview=True,
        app_provider=lambda: app,
    )

    for _ in range(4):
        engine.tick()

    rows = engine.screen_usage_summary(date.today().isoformat(), date.today().isoformat())
    assert [(row.target_id, row.display_name, row.seconds) for row in rows] == [
        ("code.exe", "Visual Studio Code", 4)
    ]


def test_idle_tick_skips_foreground_window_inspection(tmp_path):
    calls = []
    engine = TimeLimitEngine(
        lambda: AppSettings(screen_usage_enabled=False, time_limits=[]),
        UsageStore(tmp_path / "usage.db"),
        preview=True,
        app_provider=lambda: calls.append(True),
    )

    engine.tick()

    assert calls == []


def test_screen_usage_ignores_system_host_processes(tmp_path):
    settings = AppSettings(screen_usage_enabled=True)
    app = WindowsApp(10, 20, r"C:\Windows\ApplicationFrameHost.exe", "applicationframehost.exe", "Host")
    engine = TimeLimitEngine(
        lambda: settings,
        UsageStore(tmp_path / "usage.db"),
        preview=True,
        app_provider=lambda: app,
    )

    engine.tick()

    assert engine.screen_usage_summary(date.today().isoformat(), date.today().isoformat()) == []


def test_screen_usage_never_tracks_or_displays_lumaguard_itself(tmp_path):
    settings = AppSettings(screen_usage_enabled=True)
    app = WindowsApp(
        10,
        20,
        r"C:\Apps\LumaGuard-0.4.5.exe",
        "lumaguard-0.4.5.exe",
        "LumaGuard 0.4.5",
    )
    store = UsageStore(tmp_path / "usage.db")
    engine = TimeLimitEngine(
        lambda: settings,
        store,
        preview=True,
        app_provider=lambda: app,
    )

    engine.tick()
    store.add_screen_seconds(
        "app", "lumaguard-0.4.4.exe", "LumaGuard 0.4.4", 30
    )

    today = date.today().isoformat()
    assert engine.screen_usage_summary(today, today) == []
    assert engine.screen_usage_series(today, today, "hour") == {}


def test_focused_website_keeps_complete_browser_usage_for_apps_view(tmp_path):
    settings = AppSettings(screen_usage_enabled=True)
    browser = WindowsApp(10, 20, r"C:\Apps\chrome.exe", "chrome.exe", "Chrome")
    engine = TimeLimitEngine(
        lambda: settings,
        UsageStore(tmp_path / "usage.db"),
        preview=True,
        app_provider=lambda: browser,
    )
    now = time.monotonic()

    engine.record_web_heartbeat("chrome", "example.com", now=now)
    engine.tick()
    engine.record_web_heartbeat("chrome", "example.com", now=now + 3)
    engine.tick()

    rows = engine.screen_usage_summary(date.today().isoformat(), date.today().isoformat())
    assert [(row.target_type, row.target_id, row.seconds) for row in rows] == [
        ("website", "example.com", 3),
        ("app", "chrome.exe", 2),
    ]
    assert rows[0].source_app == "chrome"
    assert rows[1].source_app == r"C:\Apps\chrome.exe"

    app_rows = engine.screen_usage_summary(
        date.today().isoformat(), date.today().isoformat(), "app"
    )
    assert [(row.target_id, row.seconds) for row in app_rows] == [("chrome.exe", 2)]

    de_duplicated = engine.screen_usage_series(
        date.today().isoformat(),
        date.today().isoformat(),
        "hour",
        exclude_browser_apps=True,
    )
    assert sum(de_duplicated.values()) == 3
