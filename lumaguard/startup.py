from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

from .constants import APP_NAME


TASK_NAME = "LumaGuard Startup"
TASK_NAMESPACE = "http://schemas.microsoft.com/windows/2004/02/mit/task"
LEGACY_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
CREATE_NO_WINDOW = 0x08000000


def application_parts(executable: Path | None = None) -> tuple[Path, str, Path]:
    """Return the executable, arguments, and working directory for startup."""
    if executable is not None:
        resolved = executable.resolve()
        return resolved, "--background", resolved.parent
    if getattr(sys, "frozen", False):
        resolved = Path(sys.executable).resolve()
        return resolved, "--background", resolved.parent
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    interpreter = (pythonw if pythonw.exists() else Path(sys.executable)).resolve()
    entry = (Path(__file__).resolve().parent.parent / "app.py").resolve()
    return interpreter, f'"{entry}" --background', entry.parent


def application_command(executable: Path | None = None) -> str:
    program, arguments, _working_directory = application_parts(executable)
    return f'"{program}" {arguments}'


def _run_schtasks(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["schtasks.exe", *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        check=False,
    )


def _current_user() -> str:
    result = subprocess.run(
        ["whoami.exe"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        check=False,
    )
    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        raise OSError(result.stderr.strip() or "Windows could not identify the signed-in user.")
    return value


def scheduled_task_xml(program: Path, arguments: str, working_directory: Path, user_id: str) -> str:
    program_text = escape(str(program))
    arguments_text = escape(arguments)
    working_text = escape(str(working_directory))
    user_text = escape(user_id)
    # The power-resume trigger covers sleep/hibernate even when Windows does not
    # lock the session. MultipleInstancesPolicy prevents a second copy when the
    # original process survived the sleep normally.
    resume_subscription = escape(
        "<QueryList><Query Id='0' Path='System'><Select Path='System'>"
        "*[System[Provider[@Name='Microsoft-Windows-Power-Troubleshooter'] and EventID=1]]"
        "</Select></Query></QueryList>"
    )
    return f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="{TASK_NAMESPACE}">
  <RegistrationInfo>
    <Description>Starts LumaGuard quietly after sign-in and restores it after sleep or an unexpected exit.</Description>
    <URI>\\{TASK_NAME}</URI>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{user_text}</UserId>
    </LogonTrigger>
    <SessionStateChangeTrigger>
      <Enabled>true</Enabled>
      <StateChange>SessionUnlock</StateChange>
      <UserId>{user_text}</UserId>
    </SessionStateChangeTrigger>
    <EventTrigger>
      <Enabled>true</Enabled>
      <Subscription>{resume_subscription}</Subscription>
    </EventTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{user_text}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <DisallowStartOnRemoteAppSession>false</DisallowStartOnRemoteAppSession>
    <UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{program_text}</Command>
      <Arguments>{arguments_text}</Arguments>
      <WorkingDirectory>{working_text}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
'''


def _remove_legacy_run_value() -> None:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, LEGACY_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        try:
            winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass


def _task_matches(program: Path, arguments: str) -> bool:
    result = _run_schtasks(["/Query", "/TN", TASK_NAME, "/XML"])
    if result.returncode != 0:
        return False
    try:
        root = ET.fromstring(result.stdout.lstrip("\ufeff"))
    except ET.ParseError:
        return False
    namespace = {"task": TASK_NAMESPACE}
    command = root.findtext("task:Actions/task:Exec/task:Command", namespaces=namespace) or ""
    task_arguments = root.findtext("task:Actions/task:Exec/task:Arguments", namespaces=namespace) or ""
    has_logon = root.find("task:Triggers/task:LogonTrigger", namespace) is not None
    has_unlock = root.find("task:Triggers/task:SessionStateChangeTrigger", namespace) is not None
    has_resume = root.find("task:Triggers/task:EventTrigger", namespace) is not None
    return (
        os.path.normcase(os.path.abspath(command)) == os.path.normcase(os.path.abspath(str(program)))
        and task_arguments.strip() == arguments.strip()
        and has_logon
        and has_unlock
        and has_resume
    )


def set_launch_at_startup(enabled: bool, executable: Path | None = None) -> tuple[bool, str]:
    if os.name != "nt":
        return False, "Startup registration is available on Windows only."
    try:
        program, arguments, working_directory = application_parts(executable)
        if enabled and not program.exists():
            return False, f"The LumaGuard executable was not found at {program}."

        if enabled and not _task_matches(program, arguments):
            xml_text = scheduled_task_xml(program, arguments, working_directory, _current_user())
            handle, temporary_name = tempfile.mkstemp(prefix="lumaguard-startup-", suffix=".xml")
            os.close(handle)
            temporary_path = Path(temporary_name)
            try:
                temporary_path.write_text(xml_text, encoding="utf-16")
                result = _run_schtasks(["/Create", "/TN", TASK_NAME, "/XML", str(temporary_path), "/F"])
            finally:
                temporary_path.unlink(missing_ok=True)
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip()
                return False, detail or "Windows Task Scheduler rejected the startup task."
        elif not enabled:
            existing = _run_schtasks(["/Query", "/TN", TASK_NAME])
            if existing.returncode == 0:
                result = _run_schtasks(["/Delete", "/TN", TASK_NAME, "/F"])
                if result.returncode != 0:
                    detail = (result.stderr or result.stdout).strip()
                    return False, detail or "Windows could not remove the startup task."

        _remove_legacy_run_value()
        if enabled:
            return True, "LumaGuard will start elevated after sign-in and recover after sleep or an unexpected exit."
        return True, "LumaGuard startup was disabled."
    except (OSError, ValueError) as exc:
        return False, str(exc)
