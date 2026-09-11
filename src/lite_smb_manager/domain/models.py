"""Pure value objects and entities used by the application layer."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, cast
from uuid import uuid4


class ValidationError(ValueError):
    """Raised when user-provided profile data is invalid."""


class ConnectionStatus(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    ERROR = "error"
    CONFLICT = "conflict"
    UNKNOWN = "unknown"


STATUS_TEXT: dict[ConnectionStatus, str] = {
    ConnectionStatus.DISCONNECTED: "未连接",
    ConnectionStatus.CONNECTING: "正在连接",
    ConnectionStatus.CONNECTED: "已连接",
    ConnectionStatus.DISCONNECTING: "正在断开",
    ConnectionStatus.ERROR: "连接失败",
    ConnectionStatus.CONFLICT: "存在冲突",
    ConnectionStatus.UNKNOWN: "状态未知",
}


@dataclass(frozen=True, slots=True)
class UncPath:
    """A normalized SMB share path, without a trailing separator."""

    value: str

    @classmethod
    def parse(cls, raw_value: str) -> UncPath:
        value = raw_value.strip().replace("/", "\\")
        while value.endswith("\\"):
            value = value[:-1]
        if not value.startswith("\\\\"):
            raise ValidationError("SMB 地址必须以 \\\\ 开头，例如 \\\\server\\share。")
        parts = value[2:].split("\\")
        if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
            raise ValidationError("SMB 地址必须包含服务器名和共享名。")
        if any(not part.strip() for part in parts):
            raise ValidationError("SMB 地址不能包含空的路径段。")
        if any(char in '<>"|?*' for char in value):
            raise ValidationError("SMB 地址包含 Windows 不允许的字符。")
        return cls("\\\\" + "\\".join(part.strip() for part in parts))

    @property
    def server(self) -> str:
        return self.value[2:].split("\\", 1)[0]

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class DriveLetter:
    """A permitted Windows network drive letter."""

    value: str

    @classmethod
    def parse(cls, raw_value: str) -> DriveLetter:
        value = raw_value.strip().upper()
        if len(value) != 2 or value[0] not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" or value[1] != ":":
            raise ValidationError("盘符必须是单个英文字母加冒号，例如 M:。")
        if value[0] in {"A", "B", "C"}:
            raise ValidationError("A:、B: 和 C: 不能用作网络驱动器盘符。")
        return cls(value)

    def __str__(self) -> str:
        return self.value


def normalize_identity(username: str, domain: str) -> tuple[str, str]:
    """Normalize a username/domain pair while refusing ambiguous double prefixes."""
    clean_user = username.strip()
    clean_domain = domain.strip()
    if "\\" in clean_user:
        prefix, separator, suffix = clean_user.partition("\\")
        if not prefix or not suffix or "\\" in suffix:
            raise ValidationError("用户名格式无效。")
        if clean_domain and clean_domain.casefold() != prefix.casefold():
            raise ValidationError("用户名中的域与单独填写的域不一致。")
        return suffix, prefix
    if "@" in clean_user and clean_domain:
        raise ValidationError("UPN 用户名不能同时填写域或工作组。")
    return clean_user, clean_domain


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class Profile:
    """Serializable SMB profile metadata. It deliberately has no password field."""

    id: str
    name: str
    remote_path: UncPath
    drive_letter: DriveLetter
    username: str
    domain: str
    credential_ref: str | None
    save_password: bool
    auto_connect: bool
    note: str
    created_at: str
    updated_at: str

    @classmethod
    def new(
        cls,
        *,
        name: str,
        remote_path: str,
        drive_letter: str,
        username: str = "",
        domain: str = "",
        save_password: bool = False,
        auto_connect: bool = False,
        note: str = "",
    ) -> Profile:
        timestamp = utc_now()
        normalized_user, normalized_domain = normalize_identity(username, domain)
        clean_name = name.strip()
        if not clean_name:
            raise ValidationError("配置名称不能为空。")
        return cls(
            id=str(uuid4()),
            name=clean_name,
            remote_path=UncPath.parse(remote_path),
            drive_letter=DriveLetter.parse(drive_letter),
            username=normalized_user,
            domain=normalized_domain,
            credential_ref=None,
            save_password=save_password,
            auto_connect=auto_connect,
            note=note.strip(),
            created_at=timestamp,
            updated_at=timestamp,
        )

    @property
    def qualified_username(self) -> str:
        if not self.username:
            return ""
        return f"{self.domain}\\{self.username}" if self.domain else self.username

    def with_updates(self, **changes: object) -> Profile:
        """Create an updated profile, preserving immutable creation time and identifier."""
        changes["updated_at"] = utc_now()
        return replace(self, **cast(Any, changes))

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "remote_path": self.remote_path.value,
            "drive_letter": self.drive_letter.value,
            "username": self.username,
            "domain": self.domain,
            "credential_ref": self.credential_ref,
            "save_password": self.save_password,
            "auto_connect": self.auto_connect,
            "note": self.note,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Profile:
        try:
            raw_username = str(data.get("username", ""))
            raw_domain = str(data.get("domain", ""))
            username, domain = normalize_identity(raw_username, raw_domain)
            profile = cls(
                id=str(data["id"]),
                name=str(data["name"]).strip(),
                remote_path=UncPath.parse(str(data["remote_path"])),
                drive_letter=DriveLetter.parse(str(data["drive_letter"])),
                username=username,
                domain=domain,
                credential_ref=(
                    str(data["credential_ref"]) if data.get("credential_ref") else None
                ),
                save_password=bool(data.get("save_password", False)),
                auto_connect=bool(data.get("auto_connect", False)),
                note=str(data.get("note", "")).strip(),
                created_at=str(data["created_at"]),
                updated_at=str(data["updated_at"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValidationError("配置数据格式无效。") from error
        if not profile.id or not profile.name:
            raise ValidationError("配置缺少标识或名称。")
        return profile


@dataclass(frozen=True, slots=True)
class RuntimeCredentials:
    """Short-lived credentials; its representation never reveals the password."""

    username: str
    password: str

    def __repr__(self) -> str:
        return f"RuntimeCredentials(username={self.username!r}, password=<redacted>)"
