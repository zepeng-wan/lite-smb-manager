from __future__ import annotations

from pathlib import Path

from lite_smb_manager.application.errors import user_error_for_code
from lite_smb_manager.application.ports import (
    ApplicationError,
    MappingInspection,
    MappingKind,
)
from lite_smb_manager.domain.models import Profile, RuntimeCredentials


class FakeRepository:
    def __init__(self, profiles: list[Profile] | None = None) -> None:
        self.profiles = list(profiles or [])
        self.settings: dict[str, object] = {"close_to_tray": False}

    def load(self) -> tuple[list[Profile], dict[str, object]]:
        return list(self.profiles), dict(self.settings)

    def save(self, profiles: list[Profile], settings: dict[str, object]) -> None:
        self.profiles = list(profiles)
        self.settings = dict(settings)


class FakeCredentialStore:
    def __init__(self) -> None:
        self.values: dict[str, RuntimeCredentials] = {}

    def write(self, target: str, credentials: RuntimeCredentials) -> None:
        self.values[target] = credentials

    def read(self, target: str) -> RuntimeCredentials | None:
        return self.values.get(target)

    def delete(self, target: str) -> None:
        self.values.pop(target, None)


class FakeMapper:
    def __init__(self) -> None:
        self.mappings: dict[str, str] = {}
        self.fail_connect: int | None = None
        self.fail_connect_for_drive: dict[str, int] = {}
        self.connect_without_mapping = False
        self.disconnect_calls: list[str] = []

    def inspect(self, drive_letter: str, expected_remote: str) -> MappingInspection:
        remote = self.mappings.get(drive_letter)
        if remote is None:
            return MappingInspection(MappingKind.FREE)
        if remote.casefold() == expected_remote.casefold():
            return MappingInspection(MappingKind.EXPECTED, remote)
        return MappingInspection(MappingKind.OCCUPIED, remote)

    def connect(self, profile: Profile, credentials: RuntimeCredentials | None) -> None:
        if profile.drive_letter.value in self.fail_connect_for_drive:
            raise user_error_for_code(self.fail_connect_for_drive[profile.drive_letter.value])
        if self.fail_connect is not None:
            raise user_error_for_code(self.fail_connect)
        if self.connect_without_mapping:
            return
        self.mappings[profile.drive_letter.value] = profile.remote_path.value

    def disconnect(self, drive_letter: str) -> None:
        self.disconnect_calls.append(drive_letter)
        self.mappings.pop(drive_letter, None)

    def test_server(self, remote_path: str, timeout_seconds: float = 3.0) -> None:
        if "offline" in remote_path:
            raise ApplicationError("模拟不可达")


class FakeStartup:
    def __init__(self) -> None:
        self.enabled = False

    def is_enabled(self) -> bool:
        return self.enabled

    def set_enabled(self, executable: Path, enabled: bool) -> None:
        self.enabled = enabled
