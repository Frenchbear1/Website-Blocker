from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "LumaGuard"
APP_VERSION = "0.4.6"
APP_ID = "LumaGuard.Desktop"


def app_data_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return root / APP_NAME


SETTINGS_PATH = app_data_dir() / "settings.json"
STATE_PATH = app_data_dir() / "filter-state.json"
EVENTS_PATH = app_data_dir() / "events.json"
USAGE_DB_PATH = app_data_dir() / "usage.db"
HOSTS_BACKUP_PATH = app_data_dir() / "hosts.pre-lumaguard.bak"
BROWSER_BRIDGE_HOST = "127.0.0.1"
BROWSER_BRIDGE_PORT = 17843

DNS_PRESETS = {
    "balanced": {
        "name": "Balanced",
        "subtitle": "Adult sites blocked, everyday sites stay available",
        "primary": "185.228.168.10",
        "secondary": "185.228.169.10",
        "provider": "CleanBrowsing Adult",
        "safe_search": False,
        "blocks_mixed": False,
        "color": "#8B7CFF",
    },
    "strong": {
        "name": "Strong",
        "subtitle": "SafeSearch, mixed-content, proxy and adult blocking",
        "primary": "185.228.168.168",
        "secondary": "185.228.169.168",
        "provider": "CleanBrowsing Family",
        "safe_search": True,
        "blocks_mixed": True,
        "color": "#FF7A90",
    },
    "private": {
        "name": "Private",
        "subtitle": "Fast adult and malware domain protection",
        "primary": "1.1.1.3",
        "secondary": "1.0.0.3",
        "provider": "Cloudflare Family",
        "safe_search": False,
        "blocks_mixed": False,
        "color": "#53D6B5",
    },
    "custom": {
        "name": "Custom DNS",
        "subtitle": "Use DNS servers you choose",
        "primary": "",
        "secondary": "",
        "provider": "Custom",
        "safe_search": False,
        "blocks_mixed": False,
        "color": "#65B8FF",
    },
}

ACCENTS = {
    "violet": "#8B7CFF",
    "rose": "#FF7A90",
    "mint": "#53D6B5",
    "blue": "#65B8FF",
    "amber": "#F4BE61",
}

COOLDOWN_OPTIONS = (
    ("No delay", 0),
    ("1 minute", 1),
    ("2 minutes", 2),
    ("3 minutes", 3),
    ("5 minutes", 5),
    ("10 minutes", 10),
    ("15 minutes", 15),
    ("20 minutes", 20),
    ("30 minutes", 30),
    ("45 minutes", 45),
    ("1 hour", 60),
    ("90 minutes", 90),
    ("2 hours", 120),
    ("4 hours", 240),
    ("8 hours", 480),
    ("12 hours", 720),
    ("1 day", 1440),
)

PAUSE_WINDOW_OPTIONS = (
    ("Until window closes", 0),
    ("5 minutes", 5),
    ("10 minutes", 10),
    ("15 minutes", 15),
    ("20 minutes", 20),
    ("30 minutes", 30),
    ("45 minutes", 45),
    ("1 hour", 60),
    ("90 minutes", 90),
    ("2 hours", 120),
)
