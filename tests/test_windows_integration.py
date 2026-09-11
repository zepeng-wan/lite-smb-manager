"""Opt-in real SMB test; it never runs against a user mapping by default."""

from __future__ import annotations

import os
import sys

import pytest

from lite_smb_manager.application.ports import MappingKind
from lite_smb_manager.domain.models import Profile, RuntimeCredentials
from lite_smb_manager.infrastructure.windows_mpr import WindowsMprDriveMapper


@pytest.mark.integration
def test_real_smb_mapping_lifecycle() -> None:
    required = ["SMB_TEST_UNC", "SMB_TEST_USER", "SMB_TEST_PASSWORD", "SMB_TEST_DRIVE"]
    missing = [name for name in required if not os.environ.get(name)]
    if sys.platform != "win32":
        pytest.skip("真实 SMB 集成测试需要原生 Windows。")
    if missing:
        pytest.skip("缺少真实 SMB 测试条件：" + ", ".join(missing))
    profile = Profile.new(
        name="integration",
        remote_path=os.environ["SMB_TEST_UNC"],
        drive_letter=os.environ["SMB_TEST_DRIVE"],
        username=os.environ["SMB_TEST_USER"],
        domain=os.environ.get("SMB_TEST_DOMAIN", ""),
    )
    mapper = WindowsMprDriveMapper()
    before = mapper.inspect(profile.drive_letter.value, profile.remote_path.value)
    if before.kind != MappingKind.FREE:
        pytest.skip("指定测试盘符已被占用；为保护现有映射不执行测试。")
    created = False
    try:
        mapper.connect(
            profile,
            RuntimeCredentials(profile.qualified_username, os.environ["SMB_TEST_PASSWORD"]),
        )
        created = True
        assert (
            mapper.inspect(profile.drive_letter.value, profile.remote_path.value).kind
            == MappingKind.EXPECTED
        )
    finally:
        if created:
            mapper.disconnect(profile.drive_letter.value)
