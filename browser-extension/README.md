# LumaGuard Browser Companion

This extension counts only the focused, visible website domain. It never sends full URLs, searches, page titles, or page content. All communication stays on `127.0.0.1` and fails open if the LumaGuard desktop app is not running.

## Vivaldi, Chrome, Edge, Brave, or Opera

1. Keep LumaGuard running.
2. Open the browser's Extensions page (`vivaldi://extensions`, `chrome://extensions`, or `edge://extensions`).
3. Turn on Developer mode.
4. Choose **Load unpacked** and select this folder.
5. Refresh an ordinary website tab.
6. Click the LumaGuard extension icon. It should say **Connected**.

Once connected, the toolbar shield follows the accent selected in the desktop app. Reload the unpacked extension after updating LumaGuard so the bundled icon files are available.

The Time Limits page says **Waiting** until a companion checks in, then changes to **Connected**. If it keeps waiting, use the extension popup's **Check again** button and confirm the desktop app is running.

Warn-only website rules display a centered in-page LumaGuard card and blur the site behind it. **Dismiss warning** restores the page. **Block for today** immediately opens the strict boundary page and keeps the rule blocked until the local date changes or that rule's usage is reset from the desktop app.

## Firefox development build

Copy `manifest-firefox.json` over `manifest.json`, then load the folder temporarily from `about:debugging`. Firefox requires signed extensions for permanent normal installation.
