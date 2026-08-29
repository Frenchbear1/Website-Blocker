# LumaGuard

LumaGuard is a Windows-first, tray-resident browsing boundary app. It combines system DNS filtering with personal domain rules, schedules, foreground app and website time limits, an accountability PIN, pause cooldowns, and a calm desktop interface.

This repository contains the first functional MVP. Filtering is never activated during installation or first launch; the user must explicitly turn it on.

## Included in the MVP

- Native Windows system-tray behavior
- Animated dashboard and seven-screen modern interface
- Optional Screen Usage history with day, week, month, and all-time views
- Color-coded app and website breakdowns with clickable detail graphs
- Balanced, Strong, Private, and Custom DNS profiles
- Strong profile with DNS-enforced SafeSearch support
- Personal block and allow lists layered through a bounded hosts-file section
- Recurring schedules, including overnight windows
- Reliable elevated launch after Windows sign-in, with sleep/unlock and crash recovery
- Slow, salted PIN hashing for accountability locking
- Optional pause cooldown with 16 choices from 1 minute through 1 day
- Bounded pause window that automatically relocks after a configurable 5–120 minutes
- Live dashboard countdown for both cooldown and open pause-window states
- Daily foreground-use limits for open Windows applications
- Daily/custom-day allowances, live usage, and editable rules
- Monitor-centered app warnings plus full-page, background-blurring website warnings
- Website warning actions to dismiss or voluntarily apply the strict block for the rest of today
- Per-limit reset controls that clear only today's usage and require the protection PIN when configured
- Guided four-step limit creation: target, allowance, days, and action
- Explicit whole-browser limits that need no browser extension
- Warning-only or graceful close-and-relock app enforcement (never force termination)
- Chrome/Edge and Firefox companion source for focused-domain time and website limit pages
- Private local browser bridge on `127.0.0.1`; only domains and durations are stored
- Honest browser status: Waiting until a companion checks in, then Connected with the browser name
- Companion toolbar popup with a direct desktop connection check
- SQLite time-limit counters plus persistent hourly Screen Usage history
- Five interface accent colors
- Full dark and light themes, including dialogs and the tray menu
- Local-only settings and activity history
- Reversible DNS snapshots and bounded hosts-file changes

## Run from source

```powershell
Set-Location 'path\to\LumaGuard'
.\scripts\setup.ps1
.\scripts\run.ps1
```

Changing DNS and the Windows hosts file requires administrator rights. The packaged executable requests them automatically. For safe UI development without system changes:

```powershell
.\.venv\Scripts\python.exe app.py --preview
```

## Launch with Windows

The **Launch with Windows** setting registers an elevated Windows scheduled task instead of a normal Startup-folder or registry entry. LumaGuard starts quietly after you sign in following a restart. During ordinary sleep or hibernation, the existing process resumes with Windows; an additional resume/unlock trigger relaunches it if the process is no longer running. The task also retries after an unexpected exit. It does not power on or wake a shut-down computer by itself.

## Build the Windows executable

```powershell
.\scripts\build.ps1
```

The result is `dist\LumaGuard.exe`. Because this prototype is not code-signed, Windows may show an unknown-publisher warning.

## Time limits

Open **Time limits** from the sidebar or tray menu, then choose **Add limit**. A four-step flow asks what to limit, the daily allowance, active days, and whether to warn or block.

Choose **An app or whole browser** to work without any extension. Open Chrome, Edge, Firefox, Vivaldi, Brave, or Opera first and select it from the app list; LumaGuard will count that browser's total foreground time. Windows does not expose the active HTTPS domain reliably outside the browser, so timing one specific website requires the optional companion.

Website rules accept a domain manually and also list domains detected by the companion. Only the foreground app or the focused, visible browser page accrues time. A website warning blurs and disables the page behind a centered card. It can be dismissed, or **Block for today** can immediately switch that rule to the strict boundary page until the local date changes.

For Chrome or Edge, open the extension folder from LumaGuard, enable Developer mode at `chrome://extensions` or `edge://extensions`, choose **Load unpacked**, and select that folder. Firefox development installation steps are in the companion README. Firefox requires a signed add-on for normal permanent installation.

After loading or updating the companion, refresh an ordinary website tab and click the LumaGuard extension icon. Its popup should say **Connected**, and the desktop Time Limits page should change from **Waiting** to **Connected**. "Bridge ready" alone is not reported as a browser connection.

Individual-website limits fail open if LumaGuard is closed. Private/incognito browser windows require explicitly enabling the extension there. App and whole-browser limits do not need an extension, but LumaGuard must remain running. Usage is stored in `%LOCALAPPDATA%\LumaGuard\usage.db`. Each limit card can reset only that rule's current-day counter; if a protection PIN is configured, the PIN is required before the reset is accepted.

## How filtering works

When protection is enabled, LumaGuard:

1. snapshots IPv4 DNS settings for active network adapters;
2. applies the selected family-safe DNS resolver;
3. writes personal rules only inside clearly marked LumaGuard lines in the hosts file, skipping that protected file entirely when no personal rules exist; and
4. clears the Windows DNS cache.

When protection is paused, LumaGuard restores the snapshot and removes only its own hosts-file section. A one-time backup is stored in `%LOCALAPPDATA%\LumaGuard`.

## Honest limitations

This MVP filters domains, not every image or sentence inside a page. HTTPS prevents a system DNS filter from reading full page paths and search text. The Strong profile enforces supported SafeSearch endpoints. A user with administrator access can ultimately bypass a local blocker. Browser Secure DNS, direct IP access, VPNs, alternate operating systems, and some mixed-content platforms need additional hardening in a production release.

App blocking in this release politely sends the foreground window a normal close request every time it is used past its allowance. The app can show a save prompt and is never force-killed. A signed Windows service is still needed for strong relaunch prevention and tamper resistance; until then, LumaGuard must remain running for time limits to be enforced.

## Data and privacy

Settings, usage totals, detected domains, and the short event history remain under `%LOCALAPPDATA%\LumaGuard`. LumaGuard does not store full URLs, search text, page titles, window titles, or page content. DNS providers can receive domain lookups under their own privacy policies; the selected provider is shown in the UI.
