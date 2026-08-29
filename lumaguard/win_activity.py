from __future__ import annotations

import ctypes
import os
import shutil
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class WindowsApp:
    hwnd: int
    pid: int
    executable: str
    executable_name: str
    display_name: str


if os.name == "nt":
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    WM_CLOSE = 0x0010

    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL


def _process_path(pid: int) -> str:
    if os.name != "nt" or pid <= 0:
        return ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return buffer.value
    finally:
        kernel32.CloseHandle(handle)


def _app_from_hwnd(hwnd: int) -> WindowsApp | None:
    if os.name != "nt" or not hwnd:
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    executable = _process_path(int(pid.value))
    if not executable:
        return None
    filename = Path(executable).name
    display_name = Path(filename).stem.replace("_", " ").replace("-", " ").strip().title()
    return WindowsApp(int(hwnd), int(pid.value), executable, filename.lower(), display_name or filename)


def foreground_app() -> WindowsApp | None:
    if os.name != "nt":
        return None
    return _app_from_hwnd(int(user32.GetForegroundWindow() or 0))


def list_open_apps() -> list[WindowsApp]:
    if os.name != "nt":
        return []
    found: dict[str, WindowsApp] = {}
    enum_callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def collect(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindowTextLengthW(hwnd) <= 0:
            return True
        app = _app_from_hwnd(int(hwnd))
        if app:
            found.setdefault(app.executable.lower(), app)
        return True

    callback = enum_callback(collect)
    user32.EnumWindows(callback, 0)
    return sorted(found.values(), key=lambda item: item.display_name.lower())


BROWSER_ICON_EXECUTABLES = {
    "brave": "brave.exe",
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
    "firefox": "firefox.exe",
    "opera": "opera.exe",
    "vivaldi": "vivaldi.exe",
}


def _known_executable_paths(filename: str) -> list[Path]:
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    program_files = Path(os.environ.get("ProgramFiles", ""))
    program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", ""))
    windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
    candidates: dict[str, list[Path]] = {
        "brave.exe": [
            local / "BraveSoftware/Brave-Browser/Application/brave.exe",
            program_files / "BraveSoftware/Brave-Browser/Application/brave.exe",
            program_files_x86 / "BraveSoftware/Brave-Browser/Application/brave.exe",
        ],
        "chrome.exe": [
            local / "Google/Chrome/Application/chrome.exe",
            program_files / "Google/Chrome/Application/chrome.exe",
            program_files_x86 / "Google/Chrome/Application/chrome.exe",
        ],
        "code.exe": [
            local / "Programs/Microsoft VS Code/Code.exe",
            program_files / "Microsoft VS Code/Code.exe",
        ],
        "explorer.exe": [windows / "explorer.exe"],
        "firefox.exe": [
            program_files / "Mozilla Firefox/firefox.exe",
            program_files_x86 / "Mozilla Firefox/firefox.exe",
        ],
        "msedge.exe": [
            program_files / "Microsoft/Edge/Application/msedge.exe",
            program_files_x86 / "Microsoft/Edge/Application/msedge.exe",
        ],
        "notepad.exe": [windows / "System32/notepad.exe"],
        "opera.exe": [
            local / "Programs/Opera/opera.exe",
            program_files / "Opera/opera.exe",
        ],
        "vivaldi.exe": [
            local / "Vivaldi/Application/vivaldi.exe",
            program_files / "Vivaldi/Application/vivaldi.exe",
            program_files_x86 / "Vivaldi/Application/vivaldi.exe",
        ],
    }
    return candidates.get(filename, [])


@lru_cache(maxsize=160)
def resolve_executable_path(source: str) -> str:
    """Resolve a stored path, executable name, or browser id to an icon-bearing file."""
    value = os.path.expandvars(str(source or "").strip().strip('"'))
    if not value:
        return ""
    direct = Path(value)
    if direct.is_file():
        return str(direct)
    filename = BROWSER_ICON_EXECUTABLES.get(value.lower(), direct.name.lower())
    if not filename.endswith(".exe"):
        filename += ".exe"

    for app in list_open_apps():
        if app.executable_name.lower() == filename and Path(app.executable).is_file():
            return app.executable

    command_path = shutil.which(filename)
    if command_path and Path(command_path).is_file():
        return command_path

    if os.name == "nt":
        try:
            import winreg

            key_path = rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{filename}"
            views = (0, winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY)
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for view in views:
                    try:
                        with winreg.OpenKey(root, key_path, 0, winreg.KEY_READ | view) as key:
                            registered, _kind = winreg.QueryValueEx(key, None)
                    except OSError:
                        continue
                    registered_path = Path(os.path.expandvars(str(registered).strip().strip('"')))
                    if registered_path.is_file():
                        return str(registered_path)
        except (ImportError, OSError):
            pass

    for candidate in _known_executable_paths(filename):
        if candidate.is_file():
            return str(candidate)
    return ""


def request_close(hwnd: int) -> bool:
    """Ask a window to close normally. This never terminates its process."""
    if os.name != "nt" or not hwnd:
        return False
    return bool(user32.PostMessageW(hwnd, WM_CLOSE, 0, 0))
