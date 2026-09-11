from __future__ import annotations

import json
from pathlib import Path

import pytest

from lite_smb_manager.application.errors import ERROR_MESSAGES, user_error_for_code
from lite_smb_manager.application.services import ConnectionService, ProfileService, StartupService
from lite_smb_manager.domain.models import (
    ConnectionStatus,
    Profile,
    RuntimeCredentials,
    ValidationError,
)
from tests.fakes import FakeCredentialStore, FakeMapper, FakeRepository, FakeStartup


def make_profile(name: str = "NAS", drive: str = "N:", auto: bool = False) -> Profile:
    return Profile.new(
        name=name,
        remote_path=rf"\\server\{name.lower()}",
        drive_letter=drive,
        username="alice",
        save_password=True,
        auto_connect=auto,
    )


def make_services() -> tuple[ProfileService, ConnectionService, FakeMapper, FakeCredentialStore]:
    credentials = FakeCredentialStore()
    profiles = ProfileService(FakeRepository(), credentials)
    mapper = FakeMapper()
    return profiles, ConnectionService(profiles, mapper, credentials), mapper, credentials


def test_create_saves_password_only_in_credential_port() -> None:
    profiles, _, _, credentials = make_services()
    saved = profiles.create(make_profile(), "known-test-password")
    assert credentials.read(saved.credential_ref or "") is not None
    assert "known-test-password" not in str(profiles.list_profiles()[0].to_dict())


def test_not_saving_password_deletes_previous_credential() -> None:
    profiles, _, _, credentials = make_services()
    saved = profiles.create(make_profile(), "known-test-password")
    changed = saved.with_updates(save_password=False)
    profiles.update(changed)
    assert changed.credential_ref is not None
    assert credentials.read(changed.credential_ref) is None
    assert profiles.get(saved.id).credential_ref is None


def test_duplicate_has_new_id_and_no_credential() -> None:
    profiles, _, _, _ = make_services()
    original = profiles.create(make_profile(), "password")
    duplicate = profiles.duplicate(original.id, "NAS copy", "O:")
    assert duplicate.id != original.id
    assert duplicate.credential_ref is None
    assert not duplicate.save_password


def test_duplicate_drive_is_rejected() -> None:
    profiles, _, _, _ = make_services()
    profiles.create(make_profile())
    with pytest.raises(ValidationError):
        profiles.create(make_profile("Other", "N:"))


def test_settings_get_update_delete_and_missing_profile() -> None:
    profiles, _, _, credentials = make_services()
    profile = profiles.create(make_profile(), "password")
    profiles.save_settings({"close_to_tray": True})
    assert profiles.settings == {"close_to_tray": True}
    changed = profile.with_updates(name="Renamed")
    assert profiles.update(changed).name == "Renamed"
    profiles.delete(profile.id, delete_credential=True)
    assert credentials.values == {}
    with pytest.raises(Exception, match="找不到"):
        profiles.get(profile.id)


def test_legacy_credential_reference_is_migrated_when_profile_is_updated() -> None:
    credentials = FakeCredentialStore()
    profile = make_profile().with_updates(credential_ref="legacy-target")
    repository = FakeRepository([profile])
    credentials.write("legacy-target", RuntimeCredentials("alice", "password"))
    profiles = ProfileService(repository, credentials)
    saved = profiles.update(profile)
    assert saved.credential_ref is not None
    assert credentials.read(saved.credential_ref) is not None


def test_connect_disconnect_and_conflict_protection() -> None:
    profiles, connections, mapper, _ = make_services()
    profile = profiles.create(make_profile(), "password")
    assert connections.connect(profile.id).status == ConnectionStatus.CONNECTED
    assert connections.disconnect(profile.id).status == ConnectionStatus.DISCONNECTED
    mapper.mappings["N:"] = r"\\other\share"
    result = connections.disconnect(profile.id)
    assert result.status == ConnectionStatus.CONFLICT
    assert mapper.disconnect_calls == ["N:"]


def test_connect_verifies_real_mapping_after_adapter_returns_success() -> None:
    profiles, connections, mapper, _ = make_services()
    profile = profiles.create(make_profile(), "password")
    mapper.connect_without_mapping = True
    result = connections.connect(profile.id)
    assert result.status == ConnectionStatus.DISCONNECTED
    assert "无法确认 Windows 映射状态" in result.message


def test_connected_free_and_reconnect_paths_are_safe() -> None:
    profiles, connections, mapper, _ = make_services()
    profile = profiles.create(make_profile(), "password")
    assert connections.disconnect(profile.id).status == ConnectionStatus.DISCONNECTED
    connections.connect(profile.id)
    assert "已经连接" in connections.connect(profile.id).message
    assert connections.reconnect(profile.id).status == ConnectionStatus.CONNECTED
    mapper.mappings[profile.drive_letter.value] = r"\\other\share"
    assert connections.reconnect(profile.id).status == ConnectionStatus.CONFLICT


def test_connect_all_continues_after_failure() -> None:
    profiles, connections, mapper, _ = make_services()
    first = profiles.create(make_profile("First", "N:"), "password")
    second = profiles.create(make_profile("Second", "O:"), "password")
    mapper.mappings[first.drive_letter.value] = r"\\external\share"
    results = connections.connect_all()
    assert [result.status for result in results] == [
        ConnectionStatus.CONFLICT,
        ConnectionStatus.CONNECTED,
    ]
    assert mapper.mappings[second.drive_letter.value] == second.remote_path.value


def test_auto_connect_includes_only_enabled_profiles() -> None:
    profiles, connections, mapper, _ = make_services()
    disabled = profiles.create(make_profile("Off", "N:", False), "password")
    enabled = profiles.create(make_profile("On", "O:", True), "password")
    results = connections.auto_connect()
    assert [result.profile_id for result in results] == [enabled.id]
    assert disabled.drive_letter.value not in mapper.mappings


def test_auto_connect_failure_and_disconnect_all_continue() -> None:
    profiles, connections, mapper, _ = make_services()
    auto = profiles.create(make_profile("Auto", "N:", True), "password")
    other = profiles.create(make_profile("Other", "O:"), "password")
    mapper.fail_connect = 1219
    assert connections.auto_connect()[0].status == ConnectionStatus.ERROR
    mapper.fail_connect = None
    mapper.mappings[auto.drive_letter.value] = auto.remote_path.value
    mapper.mappings[other.drive_letter.value] = r"\\external\share"
    results = connections.disconnect_all()
    assert [result.status for result in results] == [
        ConnectionStatus.DISCONNECTED,
        ConnectionStatus.CONFLICT,
    ]


def test_explicit_password_anonymous_and_port_test_paths() -> None:
    profiles, connections, _, _ = make_services()
    named = profiles.create(make_profile(), "")
    assert connections.connect(named.id, "one-time").status == ConnectionStatus.CONNECTED
    anonymous = profiles.create(
        Profile.new(name="Guest", remote_path=r"\\guest\share", drive_letter="O:")
    )
    assert connections.connect(anonymous.id).status == ConnectionStatus.CONNECTED
    assert "端口可达" in connections.test_connection(anonymous.id).message


def test_missing_unsaved_password_requires_user_action() -> None:
    profiles, connections, _, _ = make_services()
    profile = Profile.new(
        name="NAS", remote_path=r"\\server\share", drive_letter="N:", username="alice"
    )
    saved = profiles.create(profile)
    with pytest.raises(Exception, match="需要密码"):
        connections.connect(saved.id)


@pytest.mark.parametrize("code", sorted(ERROR_MESSAGES))
def test_documented_windows_errors_are_localized(code: int) -> None:
    assert user_error_for_code(code).message == ERROR_MESSAGES[code]


def test_1219_is_advice_only_and_never_disconnects_other_mappings() -> None:
    profiles, connections, mapper, _ = make_services()
    profile = profiles.create(make_profile(), "password")
    mapper.fail_connect = 1219
    with pytest.raises(Exception) as caught:
        connections.connect(profile.id)
    assert "不会自动断开" in str(caught.value)
    assert mapper.disconnect_calls == []


def test_export_strips_credential_references_and_passwords(tmp_path: Path) -> None:
    profiles, _, _, _ = make_services()
    profiles.create(make_profile(), "known-test-password")
    destination = tmp_path / "export.json"
    profiles.export_profiles(destination)
    payload = destination.read_text(encoding="utf-8")
    assert "known-test-password" not in payload
    assert "LiteSMBManager/" not in payload


def test_import_reports_bad_entry_but_accepts_good_entry(tmp_path: Path) -> None:
    source = tmp_path / "import.json"
    good = make_profile().to_dict()
    source.write_text(
        json.dumps({"schema_version": 1, "profiles": [good, "bad"]}), encoding="utf-8"
    )
    profiles, _, _, _ = make_services()
    imported, messages = profiles.import_profiles(source)
    assert imported == 1
    assert len(messages) == 1


def test_import_rejects_invalid_document_and_reports_conflicts(tmp_path: Path) -> None:
    profiles, _, _, _ = make_services()
    profile = profiles.create(make_profile())
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps({"schema_version": 9, "profiles": []}), encoding="utf-8")
    with pytest.raises(Exception, match="无法读取"):
        profiles.import_profiles(invalid)
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        json.dumps({"schema_version": 1, "profiles": [profile.to_dict()]}), encoding="utf-8"
    )
    imported, messages = profiles.import_profiles(duplicate)
    assert imported == 0
    assert len(messages) == 1


def test_startup_service_delegates_to_current_user_adapter(tmp_path: Path) -> None:
    adapter = FakeStartup()
    service = StartupService(adapter)
    service.set_enabled(tmp_path / "LiteSMBManager.exe", True)
    assert service.is_enabled()
