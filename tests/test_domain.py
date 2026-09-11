from __future__ import annotations

import pytest

from lite_smb_manager.domain.models import (
    DriveLetter,
    Profile,
    RuntimeCredentials,
    UncPath,
    ValidationError,
    normalize_identity,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(r"\\server\share\\", r"\\server\share"), (" //192.0.2.8/media ", r"\\192.0.2.8\media")],
)
def test_unc_is_normalized(raw: str, expected: str) -> None:
    assert UncPath.parse(raw).value == expected


@pytest.mark.parametrize(
    "raw", ["C:\\folder", "server", r"\\server", r"\\server\\share", r"\\\\share"]
)
def test_invalid_unc_is_rejected(raw: str) -> None:
    with pytest.raises(ValidationError):
        UncPath.parse(raw)


def test_drive_is_uppercase_and_reserved_drives_are_rejected() -> None:
    assert DriveLetter.parse("m:").value == "M:"
    with pytest.raises(ValidationError):
        DriveLetter.parse("C:")


def test_domain_in_username_is_normalized() -> None:
    assert normalize_identity(r"WORKGROUP\alice", "") == ("alice", "WORKGROUP")
    with pytest.raises(ValidationError):
        normalize_identity(r"ONE\alice", "TWO")


def test_profile_serialization_has_no_password_field() -> None:
    profile = Profile.new(name="NAS", remote_path=r"\\nas\share", drive_letter="N:")
    assert "password" not in profile.to_dict()
    assert "secret" not in repr(RuntimeCredentials("alice", "secret"))
