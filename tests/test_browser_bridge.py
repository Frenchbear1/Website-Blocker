import json
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

from website_blocker.browser_bridge import BrowserBridge, _allowed_origin
from website_blocker.models import AppSettings, TimeLimitRule
from website_blocker.storage import UsageStore
from website_blocker.time_limiter import TimeLimitEngine


def test_bridge_accepts_extension_and_omitted_origins():
    assert _allowed_origin("chrome-extension://example")
    assert _allowed_origin("moz-extension://example")
    assert _allowed_origin("")


def test_bridge_rejects_ordinary_web_origins():
    assert not _allowed_origin("https://example.com")
    assert not _allowed_origin("http://127.0.0.1:9000")


def test_bridge_accepts_block_for_today_decision(tmp_path):
    rule = TimeLimitRule(
        target_type="website",
        target="example.com",
        days=[datetime.now().weekday()],
        enforcement="warn",
    )
    engine = TimeLimitEngine(
        lambda: AppSettings(time_limits=[rule], accent="rose"),
        UsageStore(tmp_path / "usage.db"),
        preview=True,
        app_provider=lambda: None,
    )
    bridge = BrowserBridge(engine, port=0)
    assert bridge.start()
    try:
        port = bridge.server.server_address[1]
        request = Request(
            f"http://127.0.0.1:{port}/decision",
            data=json.dumps({"browser": "chrome", "domain": "example.com", "action": "block_today"}).encode(),
            headers={"Content-Type": "application/json", "X-Website-Blocker-Companion": "1"},
            method="POST",
        )
        with urlopen(request, timeout=3) as response:
            payload = json.loads(response.read())
        assert payload["ok"] is True
        assert payload["blocked"] is True
        assert payload["accent"] == "rose"
        assert payload["accent_color"] == "#FF7A90"
        assert engine.record_web_heartbeat("chrome", "example.com", now=10)["blocked"] is True
    finally:
        bridge.stop()


def test_extension_manifests_ship_real_toolbar_icons():
    extension_root = Path(__file__).resolve().parents[1] / "browser-extension"
    for manifest_name, action_key in (("manifest.json", "action"), ("manifest-firefox.json", "browser_action")):
        manifest = json.loads((extension_root / manifest_name).read_text(encoding="utf-8"))
        assert manifest["icons"]["128"] == "icons/violet-128.png"
        for icon_path in manifest[action_key]["default_icon"].values():
            assert (extension_root / icon_path).is_file()
