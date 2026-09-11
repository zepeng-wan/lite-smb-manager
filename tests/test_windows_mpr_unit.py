from __future__ import annotations

import pytest

from lite_smb_manager.infrastructure.windows_mpr import normalized_remote_name


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (r"\\SERVER\Share", r"\\server\share\\"),
        ("//server/share/", r"\\SERVER\SHARE"),
        (r"\\server\share\folder\\", r"\\SERVER\SHARE\FOLDER"),
    ],
)
def test_normalized_remote_name_ignores_windows_presentation_differences(
    left: str, right: str
) -> None:
    assert normalized_remote_name(left) == normalized_remote_name(right)
