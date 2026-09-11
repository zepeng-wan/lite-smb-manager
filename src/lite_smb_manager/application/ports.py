"""Typed boundaries between use cases and external adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from lite_smb_manager.domain.models import Profile, RuntimeCredentials


class MappingKind(StrEnum):
    FREE = "free"
    EXPECTED = "expected"
    OCCUPIED = "occupied"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MappingInspection:
    kind: MappingKind
    remote_path: str | None = None


class ApplicationError(Exception):
    """An expected operation failure with a safe, localized message."""

    def __init__(self, message: str, *, code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class ProfileRepository(Protocol):
    def load(self) -> tuple[list[Profile], dict[str, object]]: ...

    def save(self, profiles: list[Profile], settings: dict[str, object]) -> None: ...


class CredentialStore(Protocol):
    def write(self, target: str, credentials: RuntimeCredentials) -> None: ...

    def read(self, target: str) -> RuntimeCredentials | None: ...

    def delete(self, target: str) -> None: ...


class DriveMapper(Protocol):
    def inspect(self, drive_letter: str, expected_remote: str) -> MappingInspection: ...

    def connect(self, profile: Profile, credentials: RuntimeCredentials | None) -> None: ...

    def disconnect(self, drive_letter: str) -> None: ...

    def test_server(self, remote_path: str, timeout_seconds: float = 3.0) -> None: ...


class StartupManager(Protocol):
    def is_enabled(self) -> bool: ...

    def set_enabled(self, executable: Path, enabled: bool) -> None: ...
