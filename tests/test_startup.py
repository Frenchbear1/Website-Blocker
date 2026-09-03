import subprocess
from argparse import Namespace
from pathlib import Path

from app import should_show_already_running_message
from website_blocker import startup
from website_blocker.startup import TASK_NAMESPACE, application_parts, scheduled_task_xml


def test_automatic_background_launch_exits_silently_if_already_running():
    assert not should_show_already_running_message(Namespace(background=True))


def test_manual_launch_still_explains_that_the_app_is_already_running():
    assert should_show_already_running_message(Namespace(background=False))


def test_explicit_executable_startup_parts():
    program, arguments, working_directory = application_parts(Path(r"C:\Apps\Website Blocker.exe"))
    assert program == Path(r"C:\Apps\Website Blocker.exe").resolve()
    assert arguments == "--background"
    assert working_directory == program.parent


def test_scheduled_task_covers_logon_unlock_resume_and_recovery():
    xml = scheduled_task_xml(
        Path(r"C:\Apps\Website Blocker.exe"),
        "--background",
        Path(r"C:\Apps"),
        r"DESKTOP\person",
    )
    assert f'xmlns="{TASK_NAMESPACE}"' in xml
    assert "<LogonTrigger>" in xml
    assert "<SessionStateChangeTrigger>" in xml
    assert "<StateChange>SessionUnlock</StateChange>" in xml
    assert "Microsoft-Windows-Power-Troubleshooter" in xml
    assert "<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>" in xml
    assert "<RestartOnFailure>" in xml
    assert "<Command>C:\\Apps\\Website Blocker.exe</Command>" in xml
    assert "<Arguments>--background</Arguments>" in xml


def test_scheduled_task_xml_escapes_user_controlled_paths():
    xml = scheduled_task_xml(Path(r"C:\A&B\Website Blocker.exe"), "--background", Path(r"C:\A&B"), "A&B\\person")
    assert "C:\\A&amp;B\\Website Blocker.exe" in xml
    assert "A&amp;B\\person" in xml


def test_task_match_requires_the_current_command_and_all_recovery_triggers(monkeypatch):
    program = Path(r"C:\Apps\Website Blocker.exe")
    xml = scheduled_task_xml(program, "--background", program.parent, r"DESKTOP\person")
    monkeypatch.setattr(
        startup,
        "_run_schtasks",
        lambda _arguments: subprocess.CompletedProcess([], 0, stdout=xml, stderr=""),
    )
    assert startup._task_matches(program, "--background")
    assert not startup._task_matches(Path(r"C:\Apps\New Website Blocker.exe"), "--background")


def test_enabling_startup_creates_task_then_removes_legacy_entry(tmp_path, monkeypatch):
    executable = tmp_path / "Website Blocker.exe"
    executable.write_bytes(b"exe")
    calls = []
    legacy_removed = []
    monkeypatch.setattr(startup, "_task_matches", lambda _program, _arguments: False)
    monkeypatch.setattr(startup, "_current_user", lambda: r"DESKTOP\person")
    monkeypatch.setattr(startup, "_remove_legacy_run_value", lambda: legacy_removed.append(True))
    monkeypatch.setattr(
        startup,
        "_run_schtasks",
        lambda arguments: calls.append(arguments) or subprocess.CompletedProcess([], 0, stdout="ok", stderr=""),
    )
    success, _detail = startup.set_launch_at_startup(True, executable)
    assert success
    assert calls[0][:4] == ["/Create", "/TN", startup.TASK_NAME, "/XML"]
    assert calls[0][-1] == "/F"
    assert legacy_removed == [True]


def test_disabling_startup_queries_then_deletes_task(monkeypatch):
    calls = []
    monkeypatch.setattr(startup, "_remove_legacy_run_value", lambda: None)
    monkeypatch.setattr(
        startup,
        "_run_schtasks",
        lambda arguments: calls.append(arguments) or subprocess.CompletedProcess([], 0, stdout="ok", stderr=""),
    )
    success, _detail = startup.set_launch_at_startup(False)
    assert success
    assert calls == [
        ["/Query", "/TN", startup.TASK_NAME],
        ["/Delete", "/TN", startup.TASK_NAME, "/F"],
    ]
