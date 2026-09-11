"""Windows MPR/WNet adapter. No command-line parsing or shell invocation is used."""

from __future__ import annotations

import ctypes
import socket
import sys
from ctypes import POINTER, Structure, byref, create_unicode_buffer, wintypes

from lite_smb_manager.application.errors import user_error_for_code
from lite_smb_manager.application.ports import DriveMapper, MappingInspection, MappingKind
from lite_smb_manager.domain.models import Profile, RuntimeCredentials


class _NetResource(Structure):
    _fields_ = [
        ("dwScope", wintypes.DWORD),
        ("dwType", wintypes.DWORD),
        ("dwDisplayType", wintypes.DWORD),
        ("dwUsage", wintypes.DWORD),
        ("lpLocalName", wintypes.LPWSTR),
        ("lpRemoteName", wintypes.LPWSTR),
        ("lpComment", wintypes.LPWSTR),
        ("lpProvider", wintypes.LPWSTR),
    ]


_RESOURCE_CONNECTED = 1
_RESOURCETYPE_DISK = 1
_CONNECT_UPDATE_PROFILE = 1
_ERROR_MORE_DATA = 234
_ERROR_NOT_CONNECTED = 2250


def normalized_remote_name(remote_path: str) -> str:
    """Compare MPR UNC names without presentation-only Windows differences."""
    return remote_path.replace("/", "\\").rstrip("\\").casefold()


class WindowsMprDriveMapper(DriveMapper):
    """Maps current-user network drives through MPR's Unicode API."""

    def _mpr(self) -> ctypes.WinDLL:
        if sys.platform != "win32":
            raise OSError("Windows MPR API is unavailable on this platform")
        return ctypes.WinDLL("mpr.dll", use_last_error=True)

    def inspect(self, drive_letter: str, expected_remote: str) -> MappingInspection:
        if sys.platform != "win32":
            return MappingInspection(MappingKind.UNKNOWN)
        buffer_length = wintypes.DWORD(512)
        buffer = create_unicode_buffer(buffer_length.value)
        function = self._mpr().WNetGetConnectionW
        function.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, POINTER(wintypes.DWORD)]
        function.restype = wintypes.DWORD
        code = function(drive_letter, buffer, byref(buffer_length))
        if code == 0:
            remote = buffer.value.rstrip("\\")
            if normalized_remote_name(remote) == normalized_remote_name(expected_remote):
                return MappingInspection(MappingKind.EXPECTED, remote)
            return MappingInspection(MappingKind.OCCUPIED, remote)
        if code == _ERROR_MORE_DATA:
            buffer = create_unicode_buffer(buffer_length.value + 1)
            code = function(drive_letter, buffer, byref(buffer_length))
            if code == 0:
                remote = buffer.value.rstrip("\\")
                return MappingInspection(
                    MappingKind.EXPECTED
                    if normalized_remote_name(remote) == normalized_remote_name(expected_remote)
                    else MappingKind.OCCUPIED,
                    remote,
                )
        if code == _ERROR_NOT_CONNECTED:
            return MappingInspection(MappingKind.FREE)
        return MappingInspection(MappingKind.UNKNOWN)

    def connect(self, profile: Profile, credentials: RuntimeCredentials | None) -> None:
        resource = _NetResource()
        resource.dwType = _RESOURCETYPE_DISK
        resource.lpLocalName = profile.drive_letter.value
        resource.lpRemoteName = profile.remote_path.value
        username = credentials.username if credentials else None
        password = credentials.password if credentials else None
        function = self._mpr().WNetAddConnection2W
        function.argtypes = [
            POINTER(_NetResource),
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
        ]
        function.restype = wintypes.DWORD
        code = function(byref(resource), password, username, _CONNECT_UPDATE_PROFILE)
        if code:
            raise user_error_for_code(code)

    def disconnect(self, drive_letter: str) -> None:
        function = self._mpr().WNetCancelConnection2W
        function.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL]
        function.restype = wintypes.DWORD
        code = function(drive_letter, _CONNECT_UPDATE_PROFILE, False)
        if code:
            raise user_error_for_code(code)

    def test_server(self, remote_path: str, timeout_seconds: float = 3.0) -> None:
        server = remote_path[2:].split("\\", 1)[0]
        try:
            with socket.create_connection((server, 445), timeout=timeout_seconds):
                return
        except OSError as error:
            raise user_error_for_code(53) from error
