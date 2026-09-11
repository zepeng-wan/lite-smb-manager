from __future__ import annotations

import json
from pathlib import Path

from lite_smb_manager.domain.models import Profile
from lite_smb_manager.infrastructure.json_repository import JsonProfileRepository
from lite_smb_manager.infrastructure.logging_setup import configure_logging, redact


def test_repository_round_trip_and_atomic_metadata(tmp_path: Path) -> None:
    repository = JsonProfileRepository(tmp_path)
    profile = Profile.new(name="NAS", remote_path=r"\\server\share", drive_letter="N:")
    repository.save([profile], {"close_to_tray": True})
    loaded, settings = repository.load()
    assert loaded == [profile]
    assert settings["close_to_tray"] is True
    assert not (tmp_path / "profiles.json.tmp").exists()


def test_schema_zero_is_migrated(tmp_path: Path) -> None:
    profile = Profile.new(name="NAS", remote_path=r"\\server\share", drive_letter="N:")
    (tmp_path / "profiles.json").write_text(
        json.dumps({"profiles": [profile.to_dict()]}), encoding="utf-8"
    )
    loaded, settings = JsonProfileRepository(tmp_path).load()
    assert loaded[0].id == profile.id
    assert settings["close_to_tray"] is True


def test_corrupt_configuration_is_preserved_for_recovery(tmp_path: Path) -> None:
    (tmp_path / "profiles.json").write_text("not-json", encoding="utf-8")
    profiles, settings = JsonProfileRepository(tmp_path).load()
    assert profiles == []
    assert "已创建备份" in str(settings["recovery_warning"])
    assert list(tmp_path.glob("profiles.corrupt.*.json"))


def test_log_redaction_never_writes_known_password(tmp_path: Path) -> None:
    logger = configure_logging(tmp_path)
    logger.info("password=known-test-password")
    for handler in logger.handlers:
        handler.flush()
    content = (tmp_path / "lite-smb-manager.log").read_text(encoding="utf-8")
    assert "known-test-password" not in content
    assert "<redacted>" in content
    assert redact("pwd: hello") == "pwd:<redacted>"
