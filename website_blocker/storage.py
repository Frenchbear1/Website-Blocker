from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .constants import EVENTS_PATH, SETTINGS_PATH, USAGE_DB_PATH
from .models import AppSettings, EventRecord, ScreenUsageEntry


def _atomic_json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


class SettingsStore:
    def __init__(self, path: Path = SETTINGS_PATH):
        self.path = path

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                payload = json.load(stream)
            return AppSettings.from_dict(payload)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        _atomic_json_write(self.path, settings.to_dict())


class EventStore:
    def __init__(self, path: Path = EVENTS_PATH, limit: int = 40):
        self.path = path
        self.limit = limit

    def load(self) -> list[EventRecord]:
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                payload = json.load(stream)
            return [EventRecord.from_dict(item) for item in payload if isinstance(item, dict)]
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return []

    def add(self, event: EventRecord) -> None:
        events = self.load()
        events.insert(0, event)
        _atomic_json_write(self.path, [record.__dict__ for record in events[: self.limit]])


class UsageStore:
    """Small local database containing durations, never URLs or window titles."""

    def __init__(self, path: Path = USAGE_DB_PATH):
        self.path = path
        self._lock = threading.RLock()
        self._initialize()

    @contextmanager
    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS usage (
                    day TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    seconds INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (day, rule_id)
                );
                CREATE TABLE IF NOT EXISTS detected_sites (
                    domain TEXT PRIMARY KEY,
                    last_seen TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS manual_blocks (
                    day TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    PRIMARY KEY (day, rule_id)
                );
                CREATE TABLE IF NOT EXISTS screen_usage (
                    day TEXT NOT NULL,
                    hour INTEGER NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    source_app TEXT NOT NULL DEFAULT '',
                    seconds INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (day, hour, target_type, target_id)
                );
                CREATE INDEX IF NOT EXISTS screen_usage_period_idx
                    ON screen_usage(day, target_type, target_id);
                """
            )
            columns = {
                str(row[1])
                for row in connection.execute("PRAGMA table_info(screen_usage)").fetchall()
            }
            if "source_app" not in columns:
                connection.execute(
                    "ALTER TABLE screen_usage ADD COLUMN source_app TEXT NOT NULL DEFAULT ''"
                )

    @staticmethod
    def _day_key(day: date | str | None = None) -> str:
        if isinstance(day, str):
            return day
        return (day or date.today()).isoformat()

    def add_seconds(self, rule_id: str, seconds: int, day: date | str | None = None) -> None:
        amount = max(0, int(seconds))
        if not rule_id or amount == 0:
            return
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO usage(day, rule_id, seconds) VALUES (?, ?, ?)
                ON CONFLICT(day, rule_id) DO UPDATE SET seconds = seconds + excluded.seconds
                """,
                (self._day_key(day), rule_id, amount),
            )

    def seconds_for_rule(self, rule_id: str, day: date | str | None = None) -> int:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT seconds FROM usage WHERE day = ? AND rule_id = ?",
                (self._day_key(day), rule_id),
            ).fetchone()
        return int(row[0]) if row else 0

    def reset_rule_usage(self, rule_id: str, day: date | str | None = None) -> None:
        """Clear one rule's counter and voluntary block for one local day."""
        if not rule_id:
            return
        with self._lock, self._connect() as connection:
            connection.execute(
                "DELETE FROM usage WHERE day = ? AND rule_id = ?",
                (self._day_key(day), rule_id),
            )
            connection.execute(
                "DELETE FROM manual_blocks WHERE day = ? AND rule_id = ?",
                (self._day_key(day), rule_id),
            )

    def block_rule_for_day(self, rule_id: str, day: date | str | None = None) -> None:
        if not rule_id:
            return
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO manual_blocks(day, rule_id) VALUES (?, ?)",
                (self._day_key(day), rule_id),
            )

    def is_rule_blocked(self, rule_id: str, day: date | str | None = None) -> bool:
        if not rule_id:
            return False
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM manual_blocks WHERE day = ? AND rule_id = ?",
                (self._day_key(day), rule_id),
            ).fetchone()
        return row is not None

    def seconds_for_rules(self, rule_ids: list[str], day: date | str | None = None) -> dict[str, int]:
        if not rule_ids:
            return {}
        placeholders = ",".join("?" for _ in rule_ids)
        params = [self._day_key(day), *rule_ids]
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                f"SELECT rule_id, seconds FROM usage WHERE day = ? AND rule_id IN ({placeholders})", params
            ).fetchall()
        values = {rule_id: 0 for rule_id in rule_ids}
        values.update({str(rule_id): int(seconds) for rule_id, seconds in rows})
        return values

    def total_seconds(self, day: date | str | None = None) -> int:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(SUM(seconds), 0) FROM usage WHERE day = ?", (self._day_key(day),)
            ).fetchone()
        return int(row[0])

    def add_screen_seconds(
        self,
        target_type: str,
        target_id: str,
        display_name: str,
        seconds: int,
        moment: datetime | None = None,
        source_app: str = "",
    ) -> None:
        amount = max(0, int(seconds))
        kind = target_type.strip().lower()
        identifier = target_id.strip().lower()
        label = display_name.strip()[:120]
        icon_source = source_app.strip()[:520]
        if kind not in ("app", "website") or not identifier or not label or amount == 0:
            return
        recorded_at = moment or datetime.now()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO screen_usage(
                    day, hour, target_type, target_id, display_name, source_app, seconds
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(day, hour, target_type, target_id) DO UPDATE SET
                    seconds = seconds + excluded.seconds,
                    display_name = excluded.display_name,
                    source_app = CASE
                        WHEN excluded.source_app <> '' THEN excluded.source_app
                        ELSE screen_usage.source_app
                    END
                """,
                (
                    recorded_at.date().isoformat(),
                    recorded_at.hour,
                    kind,
                    identifier,
                    label,
                    icon_source,
                    amount,
                ),
            )

    def screen_usage_summary(
        self,
        start_day: date | str,
        end_day: date | str,
        target_type: str | None = None,
    ) -> list[ScreenUsageEntry]:
        clauses = ["day BETWEEN ? AND ?"]
        params: list[object] = [self._day_key(start_day), self._day_key(end_day)]
        if target_type in ("app", "website"):
            clauses.append("target_type = ?")
            params.append(target_type)
        where = " AND ".join(clauses)
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT target_type, target_id, MAX(display_name), SUM(seconds), MAX(source_app)
                FROM screen_usage
                WHERE {where}
                GROUP BY target_type, target_id
                ORDER BY SUM(seconds) DESC, MAX(display_name) COLLATE NOCASE
                """,
                params,
            ).fetchall()
        return [
            ScreenUsageEntry(
                str(kind), str(identifier), str(label), int(seconds), str(source_app or "")
            )
            for kind, identifier, label, seconds, source_app in rows
        ]

    def screen_usage_series(
        self,
        start_day: date | str,
        end_day: date | str,
        bucket: str,
        target_type: str | None = None,
        target_id: str | None = None,
        excluded_app_ids: set[str] | None = None,
        exclude_website_blocker_apps: bool = False,
    ) -> dict[str, int]:
        bucket_expression = {
            "hour": "day || ' ' || printf('%02d', hour)",
            "day": "day",
            "month": "substr(day, 1, 7)",
        }.get(bucket)
        if not bucket_expression:
            raise ValueError("Unsupported screen-usage bucket")
        clauses = ["day BETWEEN ? AND ?"]
        params: list[object] = [self._day_key(start_day), self._day_key(end_day)]
        if target_type in ("app", "website"):
            clauses.append("target_type = ?")
            params.append(target_type)
        if target_id:
            clauses.append("target_id = ?")
            params.append(target_id.strip().lower())
        excluded = sorted(
            {item.strip().lower() for item in (excluded_app_ids or set()) if item.strip()}
        )
        if excluded:
            placeholders = ",".join("?" for _item in excluded)
            clauses.append(
                f"NOT (target_type = 'app' AND target_id IN ({placeholders}))"
            )
            params.extend(excluded)
        if exclude_website_blocker_apps:
            clauses.append(
                "NOT (target_type = 'app' AND ("
                "target_id LIKE 'website blocker%.exe' OR "
                "target_id LIKE 'website-blocker%.exe' OR "
                "target_id LIKE 'website_blocker%.exe'))"
            )
        where = " AND ".join(clauses)
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT {bucket_expression} AS bucket_key, SUM(seconds)
                FROM screen_usage
                WHERE {where}
                GROUP BY bucket_key
                ORDER BY bucket_key
                """,
                params,
            ).fetchall()
        return {str(key): int(seconds) for key, seconds in rows}

    def screen_usage_bounds(self) -> tuple[str | None, str | None]:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT MIN(day), MAX(day) FROM screen_usage").fetchone()
        if not row:
            return None, None
        return (str(row[0]) if row[0] else None, str(row[1]) if row[1] else None)

    def record_site(self, domain: str) -> None:
        normalized = domain.strip().lower()
        if not normalized:
            return
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO detected_sites(domain, last_seen) VALUES (?, ?)
                ON CONFLICT(domain) DO UPDATE SET last_seen = excluded.last_seen
                """,
                (normalized, datetime.now().isoformat(timespec="seconds")),
            )

    def recent_sites(self, limit: int = 40) -> list[str]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT domain FROM detected_sites ORDER BY last_seen DESC LIMIT ?", (max(1, int(limit)),)
            ).fetchall()
        return [str(row[0]) for row in rows]
