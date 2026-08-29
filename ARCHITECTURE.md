# Architecture

## Components

- `app.py` — application bootstrap, single-instance lock, preview and screenshot modes
- `lumaguard/main_window.py` — state orchestration, tray lifecycle, schedule and limit evaluation, and UI actions
- `lumaguard/pages.py` — dashboard, profiles, rules, schedules, time limits, and settings pages
- `lumaguard/usage_page.py` — opt-in Screen Usage ranges, charts, filters, and app/site drill-downs
- `lumaguard/widgets.py` — animated switches, status orb, cards, and shared UI helpers
- `lumaguard/system_filter.py` — validated, reversible DNS and hosts-file operations
- `lumaguard/storage.py` — atomic JSON settings/events plus SQLite duration persistence
- `lumaguard/security.py` — PBKDF2-based PIN creation and verification
- `lumaguard/models.py` — serializable settings, events, schedules, and time-limit rules
- `lumaguard/win_activity.py` — Win32 foreground-window and open-application discovery
- `lumaguard/time_limiter.py` — app/domain accounting, warnings, and graceful enforcement
- `lumaguard/browser_bridge.py` — extension-only local HTTP heartbeat bridge
- `browser-extension/` — Chrome/Edge Manifest V3 and Firefox companion sources

## Safety invariants

- System filtering runs only after explicit activation or an enabled schedule.
- DNS adapter indexes and server addresses are validated before mutation.
- Original DNS values are recorded before the first active change.
- Personal host entries are isolated between two unique marker lines.
- Disabling protection restores the recorded DNS values and removes only marked entries.
- Preview mode substitutes a non-mutating filter implementation.
- Time limits count only foreground/focused activity and never force-terminate an app.
- The browser bridge binds only to `127.0.0.1` and accepts extension-origin requests.
- No full URLs, searches, page/window titles, browsing history, or page content are collected.

## Production direction

A production version should split into three trust boundaries:

1. an unelevated Fluent desktop/tray client;
2. a signed Windows service controlling DNS/WFP policy and tamper resistance; and
3. browser extensions for search-query and mixed-content page decisions.

The service should use authenticated local IPC, signed policy updates, a recovery code held by an accountability partner, and a watchdog that never leaves the network in a partially changed state.

See `TIME_LIMITS.md` for the application and active-browser-tab usage architecture.
