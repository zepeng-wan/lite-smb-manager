"""Atomic, versioned JSON persistence without credentials."""

from __future__ import annotations

import json
import os
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from lite_smb_manager.application.ports import ApplicationError, ProfileRepository
from lite_smb_manager.domain.models import Profile, ValidationError

SCHEMA_VERSION = 1


class JsonProfileRepository(ProfileRepository):
    """Stores only profile metadata using write-to-temp then atomic replacement."""

    def __init__(self, data_directory: Path) -> None:
        self._data_directory = data_directory
        self._path = data_directory / "profiles.json"

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> tuple[list[Profile], dict[str, object]]:
        if not self._path.exists():
            return [], {"close_to_tray": True}
        try:
            raw = self._path.read_text(encoding="utf-8")
            if not raw.strip():
                return [], {"close_to_tray": True}
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValidationError("配置根对象无效。")
            payload = self._migrate(payload)
            raw_profiles = payload.get("profiles", [])
            if not isinstance(raw_profiles, list):
                raise ValidationError("配置列表无效。")
            profiles = [Profile.from_dict(cast(dict[str, object], entry)) for entry in raw_profiles]
            settings = payload.get("settings", {"close_to_tray": True})
            if not isinstance(settings, dict):
                raise ValidationError("应用设置无效。")
            return profiles, dict(settings)
        except (OSError, ValueError, TypeError, ValidationError):
            backup = self._backup_corrupt_file()
            message = "配置文件损坏，已创建备份并使用空配置。"
            if backup is None:
                message = "配置文件损坏且无法备份，请检查用户数据目录。"
            return [], {"close_to_tray": True, "recovery_warning": message}

    def save(self, profiles: list[Profile], settings: dict[str, object]) -> None:
        self._data_directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "settings": settings,
            "profiles": [profile.to_dict() for profile in profiles],
        }
        temporary = self._path.with_suffix(".json.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._path)
        except OSError as error:
            with suppress(OSError):
                temporary.unlink(missing_ok=True)
            raise ApplicationError("无法安全写入配置文件，请检查磁盘空间和权限。") from error

    def _migrate(self, payload: dict[str, object]) -> dict[str, object]:
        version = payload.get("schema_version", 0)
        if version == SCHEMA_VERSION:
            return payload
        if version == 0 and isinstance(payload.get("profiles"), list):
            return {
                "schema_version": 1,
                "settings": {"close_to_tray": True},
                "profiles": payload["profiles"],
            }
        raise ValidationError("配置文件版本不受支持。")

    def _backup_corrupt_file(self) -> Path | None:
        if not self._path.exists():
            return None
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        backup = self._path.with_name(f"profiles.corrupt.{timestamp}.json")
        try:
            os.replace(self._path, backup)
            return backup
        except OSError:
            return None
