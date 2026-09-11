"""Windows per-user data locations."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "LiteSMBManager"


def roaming_data_dir() -> Path:
    return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_NAME


def local_data_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_NAME
