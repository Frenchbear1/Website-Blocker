from website_blocker.system_filter import (
    END_MARKER,
    NRPT_RULE_COMMENT,
    START_MARKER,
    PreviewSystemFilter,
    SystemFilter,
    render_allowed_dns_script,
    render_hosts_content,
)
from website_blocker.models import AppSettings


def test_render_hosts_adds_bounded_rules_without_touching_existing_lines():
    original = "127.0.0.1 localhost\n# user's note\n"
    result = render_hosts_content(original, ["example.com"], [])
    assert "127.0.0.1 localhost" in result
    assert "# user's note" in result
    assert f"{START_MARKER}\n" in result
    assert "0.0.0.0 example.com" in result
    assert "0.0.0.0 www.example.com" in result
    assert END_MARKER in result


def test_render_hosts_replaces_old_section_and_allow_wins():
    original = render_hosts_content("127.0.0.1 localhost\n", ["old.example"], [])
    result = render_hosts_content(original, ["new.example", "allowed.example"], ["allowed.example"])
    assert "old.example" not in result
    assert "new.example" in result
    assert "allowed.example" not in result
    assert result.count(START_MARKER) == 1


def test_preview_filter_never_requires_admin():
    engine = PreviewSystemFilter()
    assert engine.enable(AppSettings()).success
    assert engine.disable().success


def test_hosts_write_is_skipped_when_there_are_no_personal_rules(tmp_path):
    hosts = tmp_path / "hosts"
    backup = tmp_path / "hosts.backup"
    original = b"127.0.0.1 localhost\r\n"
    hosts.write_bytes(original)
    engine = SystemFilter(tmp_path / "state.json", hosts, backup)

    assert engine._write_hosts([], []) is False
    assert hosts.read_bytes() == original
    assert not backup.exists()


def test_hosts_rules_are_written_and_removed_in_place(tmp_path):
    hosts = tmp_path / "hosts"
    backup = tmp_path / "hosts.backup"
    hosts.write_text("127.0.0.1 localhost\n", encoding="utf-8")
    engine = SystemFilter(tmp_path / "state.json", hosts, backup)

    assert engine._write_hosts(["example.com"], []) is True
    assert START_MARKER in hosts.read_text(encoding="utf-8")
    assert backup.exists()
    assert engine._write_hosts([], []) is True
    assert START_MARKER not in hosts.read_text(encoding="utf-8")


def test_allowed_domains_get_bounded_unfiltered_dns_rules():
    script = render_allowed_dns_script(["Allowed.Example", "https://second.example/path"])

    assert f"Comment -eq '{NRPT_RULE_COMMENT}'" in script
    assert "@('allowed.example','.allowed.example')" in script
    assert "@('second.example','.second.example')" in script
    assert "'1.1.1.1','1.0.0.1'" in script
    assert "Clear-DnsClientCache" in script
