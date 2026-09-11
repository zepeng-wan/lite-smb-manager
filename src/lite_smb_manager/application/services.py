"""Use cases for profile management and safe SMB mapping orchestration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from lite_smb_manager.application.ports import (
    ApplicationError,
    CredentialStore,
    DriveMapper,
    MappingKind,
    ProfileRepository,
    StartupManager,
)
from lite_smb_manager.domain.models import (
    ConnectionStatus,
    Profile,
    RuntimeCredentials,
    ValidationError,
)


def credential_target(profile_id: str) -> str:
    return f"LiteSMBManager/{profile_id}"


@dataclass(frozen=True, slots=True)
class OperationResult:
    profile_id: str
    status: ConnectionStatus
    message: str


class ProfileService:
    """CRUD and import/export service; profiles never carry plaintext passwords."""

    def __init__(self, repository: ProfileRepository, credentials: CredentialStore) -> None:
        self._repository = repository
        self._credentials = credentials
        self._profiles, self._settings = repository.load()

    @property
    def settings(self) -> dict[str, object]:
        return dict(self._settings)

    def list_profiles(self) -> list[Profile]:
        return sorted(self._profiles, key=lambda profile: (profile.name.casefold(), profile.id))

    def get(self, profile_id: str) -> Profile:
        for profile in self._profiles:
            if profile.id == profile_id:
                return profile
        raise ApplicationError("找不到所选配置。")

    def save_settings(self, settings: dict[str, object]) -> None:
        self._settings = dict(settings)
        self._persist()

    def create(self, profile: Profile, password: str = "") -> Profile:
        self._ensure_unique_drive(profile.drive_letter.value)
        saved = self._apply_password_policy(profile, password, old_profile=None)
        self._profiles.append(saved)
        self._persist()
        return saved

    def update(self, profile: Profile, password: str = "") -> Profile:
        old_profile = self.get(profile.id)
        self._ensure_unique_drive(profile.drive_letter.value, excluding_id=profile.id)
        saved = self._apply_password_policy(profile, password, old_profile=old_profile)
        self._profiles = [saved if item.id == saved.id else item for item in self._profiles]
        self._persist()
        return saved

    def duplicate(self, profile_id: str, name: str, drive_letter: str) -> Profile:
        source = self.get(profile_id)
        clone = Profile.new(
            name=name,
            remote_path=source.remote_path.value,
            drive_letter=drive_letter,
            username=source.username,
            domain=source.domain,
            save_password=False,
            auto_connect=False,
            note=source.note,
        )
        return self.create(clone)

    def delete(self, profile_id: str, delete_credential: bool) -> None:
        profile = self.get(profile_id)
        self._profiles = [item for item in self._profiles if item.id != profile_id]
        self._persist()
        if delete_credential and profile.credential_ref:
            self._credentials.delete(profile.credential_ref)

    def export_profiles(self, destination: Path) -> None:
        import json

        exported_profiles = []
        for profile in self.list_profiles():
            data = profile.to_dict()
            data["credential_ref"] = None
            data["save_password"] = False
            exported_profiles.append(data)
        destination.write_text(
            json.dumps(
                {"schema_version": 1, "profiles": exported_profiles}, ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )

    def import_profiles(self, source: Path) -> tuple[int, list[str]]:
        import json

        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("schema_version") != 1:
                raise ValidationError("导入文件的版本不受支持。")
            entries = payload.get("profiles")
            if not isinstance(entries, list):
                raise ValidationError("导入文件缺少配置列表。")
        except (OSError, ValueError) as error:
            raise ApplicationError("无法读取导入文件，请确认文件格式正确。") from error
        messages: list[str] = []
        imported = 0
        existing_ids = {profile.id for profile in self._profiles}
        existing_drives = {profile.drive_letter.value for profile in self._profiles}
        for index, entry in enumerate(entries, start=1):
            try:
                if not isinstance(entry, dict):
                    raise ValidationError("条目不是对象。")
                data = dict(entry)
                data["credential_ref"] = None
                data["save_password"] = False
                profile = Profile.from_dict(data)
                if profile.id in existing_ids or profile.drive_letter.value in existing_drives:
                    raise ValidationError("ID 或盘符与现有配置冲突。")
                self._profiles.append(profile)
                existing_ids.add(profile.id)
                existing_drives.add(profile.drive_letter.value)
                imported += 1
            except ValidationError as error:
                messages.append(f"第 {index} 项未导入：{error}")
        if imported:
            self._persist()
        return imported, messages

    def _apply_password_policy(
        self, profile: Profile, password: str, old_profile: Profile | None
    ) -> Profile:
        old_reference = old_profile.credential_ref if old_profile else None
        reference = credential_target(profile.id)
        if profile.save_password:
            if password:
                self._credentials.write(
                    reference, RuntimeCredentials(profile.qualified_username, password)
                )
            elif old_reference and old_reference != reference:
                existing = self._credentials.read(old_reference)
                if existing:
                    self._credentials.write(reference, existing)
            return replace(profile, credential_ref=reference)
        if old_reference:
            self._credentials.delete(old_reference)
        return replace(profile, credential_ref=None, save_password=False)

    def _ensure_unique_drive(self, drive: str, excluding_id: str | None = None) -> None:
        if any(
            item.drive_letter.value == drive and item.id != excluding_id for item in self._profiles
        ):
            raise ValidationError(f"盘符 {drive} 已被另一个配置使用。")

    def _persist(self) -> None:
        self._repository.save(self._profiles, self._settings)


class ConnectionService:
    """Coordinates MPR operations without touching Qt or Windows APIs directly."""

    def __init__(
        self, profiles: ProfileService, mapper: DriveMapper, credentials: CredentialStore
    ) -> None:
        self._profiles = profiles
        self._mapper = mapper
        self._credentials = credentials

    def status(self, profile_id: str) -> ConnectionStatus:
        profile = self._profiles.get(profile_id)
        inspection = self._mapper.inspect(profile.drive_letter.value, profile.remote_path.value)
        return {
            MappingKind.FREE: ConnectionStatus.DISCONNECTED,
            MappingKind.EXPECTED: ConnectionStatus.CONNECTED,
            MappingKind.OCCUPIED: ConnectionStatus.CONFLICT,
            MappingKind.UNKNOWN: ConnectionStatus.UNKNOWN,
        }[inspection.kind]

    def connect(self, profile_id: str, password: str = "") -> OperationResult:
        profile = self._profiles.get(profile_id)
        current_status = self.status(profile_id)
        if current_status == ConnectionStatus.CONNECTED:
            return OperationResult(profile_id, current_status, "该配置已经连接。")
        if current_status == ConnectionStatus.CONFLICT:
            return OperationResult(
                profile_id, current_status, "目标盘符已被其他映射占用，不会覆盖。"
            )
        credentials = self._credentials_for(profile, password)
        self._mapper.connect(profile, credentials)
        verified_status = self.status(profile_id)
        if verified_status == ConnectionStatus.CONNECTED:
            return OperationResult(
                profile_id, verified_status, "连接成功，已确认 Windows 网络驱动器映射。"
            )
        if verified_status == ConnectionStatus.CONFLICT:
            return OperationResult(
                profile_id, verified_status, "连接后盘符指向了其他共享，请刷新后检查。"
            )
        return OperationResult(
            profile_id, verified_status, "连接请求完成，但无法确认 Windows 映射状态。"
        )

    def disconnect(self, profile_id: str) -> OperationResult:
        profile = self._profiles.get(profile_id)
        inspection = self._mapper.inspect(profile.drive_letter.value, profile.remote_path.value)
        if inspection.kind == MappingKind.FREE:
            return OperationResult(profile_id, ConnectionStatus.DISCONNECTED, "该配置尚未连接。")
        if inspection.kind != MappingKind.EXPECTED:
            return OperationResult(
                profile_id,
                ConnectionStatus.CONFLICT,
                "盘符不是此配置的映射，已拒绝断开以保护其他连接。",
            )
        self._mapper.disconnect(profile.drive_letter.value)
        verified_status = self.status(profile_id)
        if verified_status == ConnectionStatus.DISCONNECTED:
            return OperationResult(profile_id, verified_status, "已断开指定映射。")
        return OperationResult(
            profile_id, verified_status, "断开请求完成，但无法确认 Windows 映射状态。"
        )

    def reconnect(self, profile_id: str, password: str = "") -> OperationResult:
        state = self.status(profile_id)
        if state == ConnectionStatus.CONNECTED:
            disconnected = self.disconnect(profile_id)
            if disconnected.status != ConnectionStatus.DISCONNECTED:
                return disconnected
        elif state == ConnectionStatus.CONFLICT:
            return OperationResult(profile_id, state, "目标盘符冲突，未执行重新连接。")
        return self.connect(profile_id, password)

    def connect_all(self) -> list[OperationResult]:
        results: list[OperationResult] = []
        for profile in self._profiles.list_profiles():
            try:
                results.append(self.connect(profile.id))
            except ApplicationError as error:
                results.append(OperationResult(profile.id, ConnectionStatus.ERROR, error.message))
        return results

    def disconnect_all(self) -> list[OperationResult]:
        results: list[OperationResult] = []
        for profile in self._profiles.list_profiles():
            try:
                results.append(self.disconnect(profile.id))
            except ApplicationError as error:
                results.append(OperationResult(profile.id, ConnectionStatus.ERROR, error.message))
        return results

    def auto_connect(self) -> list[OperationResult]:
        return [
            result
            for profile in self._profiles.list_profiles()
            if profile.auto_connect
            for result in [self._connect_auto(profile)]
        ]

    def test_connection(self, profile_id: str) -> OperationResult:
        profile = self._profiles.get(profile_id)
        self._mapper.test_server(profile.remote_path.value)
        return OperationResult(
            profile_id, self.status(profile_id), "服务器的 SMB 端口可达；这不代表认证成功。"
        )

    def _connect_auto(self, profile: Profile) -> OperationResult:
        try:
            return self.connect(profile.id)
        except ApplicationError as error:
            return OperationResult(profile.id, ConnectionStatus.ERROR, error.message)

    def _credentials_for(self, profile: Profile, password: str) -> RuntimeCredentials | None:
        if password:
            return RuntimeCredentials(profile.qualified_username, password)
        if profile.credential_ref:
            credentials = self._credentials.read(profile.credential_ref)
            if credentials:
                return credentials
        if profile.username:
            raise ApplicationError("此配置需要密码。请编辑配置后输入密码，或勾选保存密码。")
        return None


class StartupService:
    """Current-user Windows login startup use case."""

    def __init__(self, manager: StartupManager) -> None:
        self._manager = manager

    def is_enabled(self) -> bool:
        return self._manager.is_enabled()

    def set_enabled(self, executable: Path, enabled: bool) -> None:
        self._manager.set_enabled(executable, enabled)
