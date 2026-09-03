# Time Limits — v0.2 Implementation

Website Blocker v0.2 implements local foreground-time limits. Windows applications and browser websites use separate observers because treating them as one source would produce inaccurate totals and weak blocking.

## What can be observed accurately

### Windows applications

The desktop client enumerates currently open top-level windows and their executable processes. Usage counts only while an application's window is in the foreground. Merely running in the background is not meaningful usage for apps such as music players, launchers, and communication tools.

The tracker records only:

- executable identity and friendly application name;
- active seconds in the current local day; and
- the configured rule identifier.

Window titles and document names should not be retained.

### Browser websites

A desktop process cannot reliably enumerate every Chrome, Edge, or Firefox tab or read its domain. HTTPS and browser sandboxing intentionally prevent that. Window titles reveal only an inconsistent label for the foreground tab and are not safe enough for enforcement.

The companion reports only the focused, visible tab's normalized domain through an extension-origin local bridge on `127.0.0.1`. Full URLs, search text, and page titles remain private.

## Rules model

Application and website rules support:

- daily allowance in minutes;
- every day, weekdays, weekends, or individually selected days;
- monitor-centered app warnings and blurred in-page website warnings at configurable thresholds;
- a fresh reset at local midnight;
- an explicit per-rule reset for today's usage, gated by the protection PIN when one is configured; and
- editable, individually enabled rules.

The guided selection flow offers currently open applications and recently detected domains, while also allowing a domain to be entered manually. Selecting a browser as an application provides extensionless whole-browser timing; a companion remains necessary for accurate per-domain timing.

## Enforcement

### Websites

For warn-only rules, the companion covers the focused website with a smaller centered warning and blurs the page behind it. The user can dismiss the warning or choose **Block for today**, which persists locally and immediately redirects to the strict boundary page. Strict rules redirect automatically when the allowance is reached. The desktop app remains the authority for usage totals and policy. Incognito/private windows require the user to explicitly allow the extension there.

### Applications

The current desktop release implements the safe subset of application blocking:

1. warn before the allowance expires;
2. request the application to close normally;
3. reapply the normal close request if the application is foregrounded again.

Force-closing without warning risks losing unsaved work, so it should never be the default.

## Implemented components

1. `TimeLimitEngine` — foreground-window accounting, heartbeat accounting, warnings, and SQLite persistence.
2. `Website Blocker Browser Companion` — Chrome/Edge Manifest V3 and Firefox sources reporting focused-domain time and displaying limit pages.
3. `LimitsPage` — current-app/domain discovery, daily/custom-day rules, live progress, and editing.
4. `BrowserBridge` — extension-origin HTTP on loopback only; no cloud account required.

Future hardening still calls for a signed Windows service, authenticated native messaging, group budgets, allowance history charts, and optional time-of-day windows.

## Privacy and integrity

- Keep usage data on the computer by default.
- Store durations by app identifier/domain, not browsing history.
- Never store full tab URLs or window titles for basic limits.
- Pause accounting while the computer is locked, asleep, or the target is not foregrounded.
- Reconcile extension and service timestamps to avoid double-counting multiple browser windows.
- Sign service and extension updates before enabling tamper-resistant enforcement.
