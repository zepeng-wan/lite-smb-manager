"""Current-user Run-key startup adapter."""

from __future__ import annotations

import sys
from pathlib import Path

from lite_smb_manager.application.ports import ApplicationError, StartupManager

_VALUE_NAME = "LiteSMBManager"


class WindowsStartupManager(StartupManager):
    """Uses HKCU Run, which works without elevated privileges."""

    def _require_windows(self) -> None:
        if sys.platform != "win32":
            raise ApplicationError("随 Windows 登录启动仅支持 Windows。")

    def is_enabled(self) -> bool:
        self._require_windows()
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"
            ) as key:
                winreg.QueryValueEx(key, _VALUE_NAME)
                return True
        except FileNotFoundError:
            return False
        except OSError as error:
            raise ApplicationError("无法读取 Windows 登录启动设置。") from error

    def set_enabled(self, executable: Path, enabled: bool) -> None:
        self._require_windows()
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                if enabled:
                    winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, f'"{executable}"')
                else:
                    try:
                        winreg.DeleteValue(key, _VALUE_NAME)
                    except FileNotFoundError:
                        return
        except OSError as error:
            raise ApplicationError("无法更新 Windows 登录启动设置。") from error
