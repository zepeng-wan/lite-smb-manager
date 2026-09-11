"""Minimal Windows Credential Manager adapter using ctypes."""

from __future__ import annotations

import ctypes
import sys
from ctypes import POINTER, Structure, byref, c_void_p, cast, wintypes

from lite_smb_manager.application.ports import ApplicationError, CredentialStore
from lite_smb_manager.domain.models import RuntimeCredentials


class _Credential(Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", ctypes.c_byte * 8),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", c_void_p),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


_CREDENTIAL_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2


class WindowsCredentialStore(CredentialStore):
    """Persists password material only in the current user's Credential Manager."""

    def _advapi(self) -> ctypes.WinDLL:
        if sys.platform != "win32":
            raise ApplicationError("密码保存仅支持 Windows Credential Manager。")
        return ctypes.WinDLL("Advapi32.dll", use_last_error=True)

    def write(self, target: str, credentials: RuntimeCredentials) -> None:
        encoded = credentials.password.encode("utf-16-le")
        blob = ctypes.create_string_buffer(encoded)
        item = _Credential()
        item.Type = _CREDENTIAL_GENERIC
        item.TargetName = target
        item.CredentialBlobSize = len(encoded)
        item.CredentialBlob = cast(blob, c_void_p)
        item.Persist = _CRED_PERSIST_LOCAL_MACHINE
        item.UserName = credentials.username
        function = self._advapi().CredWriteW
        function.argtypes = [POINTER(_Credential), wintypes.DWORD]
        function.restype = wintypes.BOOL
        if not function(byref(item), 0):
            raise ApplicationError("无法保存 Windows 凭据。", code=ctypes.get_last_error())

    def read(self, target: str) -> RuntimeCredentials | None:
        output = POINTER(_Credential)()
        library = self._advapi()
        function = library.CredReadW
        function.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            POINTER(POINTER(_Credential)),
        ]
        function.restype = wintypes.BOOL
        if not function(target, _CREDENTIAL_GENERIC, 0, byref(output)):
            code = ctypes.get_last_error()
            if code == 1168:
                return None
            raise ApplicationError("无法读取 Windows 凭据。", code=code)
        try:
            item = output.contents
            password = ctypes.string_at(item.CredentialBlob, item.CredentialBlobSize).decode(
                "utf-16-le"
            )
            return RuntimeCredentials(item.UserName or "", password)
        finally:
            library.CredFree(output)

    def delete(self, target: str) -> None:
        function = self._advapi().CredDeleteW
        function.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        function.restype = wintypes.BOOL
        if not function(target, _CREDENTIAL_GENERIC, 0):
            code = ctypes.get_last_error()
            if code != 1168:
                raise ApplicationError("无法删除 Windows 凭据。", code=code)
