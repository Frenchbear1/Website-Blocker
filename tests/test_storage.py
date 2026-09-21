import sqlite3
from datetime import datetime

from website_blocker.models import AppSettings, EventRecord, ScheduleRule, TimeLimitRule
from website_blocker.storage import EventStore, SettingsStore, UsageStore


def test_settings_round_trip(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    settings = AppSettings(
        active_profile="balanced",
        theme="light",
        screen_usage_enabled=True,
        pause_window_minutes=45,
        blocked_domains=["example.com"],
        schedules=[ScheduleRule(name="Night", days=[0, 2], start="22:00", end="06:00")],
        time_limits=[TimeLimitRule(name="Writing", target="writer.exe", daily_minutes=30)],
    )
    store.save(settings)
    loaded = store.load()
    assert loaded.active_profile == "balanced"
    assert loaded.theme == "light"
    assert loaded.pause_window_minutes == 45
    assert loaded.screen_usage_enabled is True
    assert loaded.blocked_domains == ["example.com"]
    assert loaded.schedules[0].name == "Night"
    assert loaded.schedules[0].days == [0, 2]
    assert loaded.time_limits[0].name == "Writing"
    assert loaded.time_limits[0].daily_minutes == 30


def test_event_store_keeps_newest_first_and_honors_limit(tmp_path):
    store = EventStore(tmp_path / "events.json", limit=2)
    store.add(EventRecord("info", "First", "one"))
    store.add(EventRecord("info", "Second", "two"))
    store.add(EventRecord("info", "Third", "three"))
    assert [event.title for event in store.load()] == ["Third", "Second"]


def test_event_store_clear_removes_recent_activity(tmp_path):
    store = EventStore(tmp_path / "events.json")
    store.add(EventRecord("success", "Saved", "Detail"))

    store.clear()

    assert store.load() == []


def test_usage_store_accumulates_by_rule_and_day(tmp_path):
    store = UsageStore(tmp_path / "usage.db")
    store.add_seconds("one", 12, "2026-08-09")
    store.add_seconds("one", 8, "2026-08-09")
    store.add_seconds("two", 5, "2026-08-09")
    assert store.seconds_for_rule("one", "2026-08-09") == 20
    assert store.seconds_for_rules(["one", "two", "missing"], "2026-08-09") == {
        "one": 20,
        "two": 5,
        "missing": 0,
    }
    assert store.total_seconds("2026-08-09") == 25


def test_usage_store_resets_only_one_rule_and_day(tmp_path):
    store = UsageStore(tmp_path / "usage.db")
    store.add_seconds("one", 12, "2026-08-09")
    store.add_seconds("one", 8, "2026-08-10")
    store.add_seconds("two", 5, "2026-08-10")
    store.block_rule_for_day("one", "2026-08-10")
    store.block_rule_for_day("one", "2026-08-09")
    store.reset_rule_usage("one", "2026-08-10")
    assert store.seconds_for_rule("one", "2026-08-10") == 0
    assert store.seconds_for_rule("one", "2026-08-09") == 12
    assert store.seconds_for_rule("two", "2026-08-10") == 5
    assert not store.is_rule_blocked("one", "2026-08-10")
    assert store.is_rule_blocked("one", "2026-08-09")


def test_usage_store_persists_voluntary_daily_blocks(tmp_path):
    path = tmp_path / "usage.db"
    UsageStore(path).block_rule_for_day("rule-one", "2026-08-10")
    reopened = UsageStore(path)
    assert reopened.is_rule_blocked("rule-one", "2026-08-10")
    assert not reopened.is_rule_blocked("rule-one", "2026-08-11")


def test_usage_store_recent_sites(tmp_path):
    store = UsageStore(tmp_path / "usage.db")
    store.record_site("example.com")
    store.record_site("focus.test")
    assert set(store.recent_sites()) == {"example.com", "focus.test"}


def test_screen_usage_summarizes_filters_and_buckets(tmp_path):
    store = UsageStore(tmp_path / "usage.db")
    store.add_screen_seconds(
        "app",
        "code.exe",
        "Visual Studio Code",
        120,
        datetime(2026, 8, 9, 10),
        r"C:\Apps\Code.exe",
    )
    store.add_screen_seconds("app", "code.exe", "Visual Studio Code", 60, datetime(2026, 8, 10, 11))
    store.add_screen_seconds("website", "example.com", "example.com", 90, datetime(2026, 8, 10, 11))

    all_rows = store.screen_usage_summary("2026-08-09", "2026-08-10")
    app_rows = store.screen_usage_summary("2026-08-09", "2026-08-10", "app")

    assert [(row.target_id, row.seconds) for row in all_rows] == [("code.exe", 180), ("example.com", 90)]
    assert all_rows[0].source_app == r"C:\Apps\Code.exe"
    assert [(row.target_id, row.seconds) for row in app_rows] == [("code.exe", 180)]
    assert store.screen_usage_series("2026-08-09", "2026-08-10", "day") == {
        "2026-08-09": 120,
        "2026-08-10": 150,
    }
    assert store.screen_usage_series(
        "2026-08-10", "2026-08-10", "hour", "website", "example.com"
    ) == {"2026-08-10 11": 90}
    assert store.screen_usage_series(
        "2026-08-09",
        "2026-08-10",
        "day",
        excluded_app_ids={"code.exe"},
    ) == {"2026-08-10": 90}
    assert store.screen_usage_bounds() == ("2026-08-09", "2026-08-10")


def test_screen_usage_schema_adds_icon_source_to_existing_database(tmp_path):
    path = tmp_path / "usage.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE screen_usage (
                day TEXT NOT NULL,
                hour INTEGER NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                display_name TEXT NOT NULL,
                seconds INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (day, hour, target_type, target_id)
            )
            """
        )

    store = UsageStore(path)
    store.add_screen_seconds(
        "website",
        "example.com",
        "example.com",
        15,
        datetime(2026, 8, 10, 11),
        "vivaldi",
    )

    rows = store.screen_usage_summary("2026-08-10", "2026-08-10")
    assert rows[0].source_app == "vivaldi"
