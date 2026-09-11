"""Composition root for the Windows desktop application."""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from lite_smb_manager.application.services import ConnectionService, ProfileService, StartupService
from lite_smb_manager.infrastructure.json_repository import JsonProfileRepository
from lite_smb_manager.infrastructure.logging_setup import configure_logging
from lite_smb_manager.infrastructure.paths import local_data_dir, roaming_data_dir
from lite_smb_manager.infrastructure.windows_credentials import WindowsCredentialStore
from lite_smb_manager.infrastructure.windows_mpr import WindowsMprDriveMapper
from lite_smb_manager.infrastructure.windows_startup import WindowsStartupManager
from lite_smb_manager.presentation.main_window import MainWindow


def build_window() -> MainWindow:
    """Build every adapter and application service in one explicit composition root."""
    logger = configure_logging(local_data_dir() / "logs")
    repository = JsonProfileRepository(roaming_data_dir())
    credentials = WindowsCredentialStore()
    profiles = ProfileService(repository, credentials)
    connections = ConnectionService(profiles, WindowsMprDriveMapper(), credentials)
    return MainWindow(profiles, connections, StartupService(WindowsStartupManager()), logger)


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("LiteSMB Manager")
    try:
        window = build_window()
    except Exception as error:
        logging.getLogger("lite_smb_manager").exception("Application startup failed")
        QMessageBox.critical(None, "LiteSMB Manager", f"应用无法启动：{error}")
        return 1
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
