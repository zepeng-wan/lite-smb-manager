"""Main window; it delegates all SMB and persistence work to application services."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from importlib.resources import files
from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, QProcess, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from lite_smb_manager.application.services import ConnectionService, ProfileService, StartupService
from lite_smb_manager.domain.models import STATUS_TEXT, ConnectionStatus, Profile, ValidationError
from lite_smb_manager.presentation.profile_dialog import ProfileDialog
from lite_smb_manager.presentation.tasks import TaskRunner


class SettingsDialog(QDialog):
    def __init__(self, close_to_tray: bool, startup_enabled: bool, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("应用设置")
        layout = QVBoxLayout(self)
        self.close_to_tray = QCheckBox("关闭主窗口时最小化到系统托盘")
        self.close_to_tray.setChecked(close_to_tray)
        self.startup = QCheckBox("随 Windows 登录启动")
        self.startup.setChecked(startup_enabled)
        layout.addWidget(self.close_to_tray)
        layout.addWidget(self.startup)
        layout.addWidget(QLabel("登录启动使用当前用户设置，不需要管理员权限。"))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class MainWindow(QMainWindow):
    """The interactive desktop shell with non-blocking mapper operations."""

    def __init__(
        self,
        profiles: ProfileService,
        connections: ConnectionService,
        startup: StartupService,
        logger: logging.Logger,
    ) -> None:
        super().__init__()
        self._profiles = profiles
        self._connections = connections
        self._startup = startup
        self._logger = logger
        self._runner = TaskRunner(logger)
        self._busy: set[str] = set()
        self._status_cache: dict[str, ConnectionStatus] = {}
        self._status_generation: dict[str, int] = {}
        self._error_generation: dict[str, int] = {}
        self._bulk_busy = False
        self._quitting = False
        self._close_to_tray = bool(profiles.settings.get("close_to_tray", True))
        self.setWindowTitle("LiteSMB Manager")
        self.setWindowIcon(
            QIcon(str(files("lite_smb_manager.presentation").joinpath("assets/logo.svg")))
        )
        self.resize(980, 540)
        self._build_ui()
        self._build_tray()
        self.refresh_table()
        recovery_warning = profiles.settings.get("recovery_warning")
        if isinstance(recovery_warning, str):
            self.statusBar().showMessage(recovery_warning, 10_000)
        QTimer.singleShot(0, self._refresh_all_statuses)
        QTimer.singleShot(300, self._auto_connect)

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels(
            ["名称", "SMB 地址", "盘符", "用户名", "自动连接", "状态"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.table.currentCellChanged.connect(lambda *_args: self._update_actions())
        self.table.cellClicked.connect(lambda *_args: self._update_actions())
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        action_layout = QHBoxLayout()
        self.action_buttons: dict[str, QPushButton] = {}
        self.row_actions: dict[str, QAction] = {}
        selected_menu = self.menuBar().addMenu("所选配置")
        for key, label, callback in [
            ("new", "新建", self._new_profile),
            ("edit", "编辑", self._edit_selected),
            ("copy", "复制", self._copy_selected),
            ("delete", "删除", self._delete_selected),
            ("connect", "连接", self._connect_selected),
            ("disconnect", "断开", self._disconnect_selected),
            ("reconnect", "重新连接", self._reconnect_selected),
            ("test", "测试连接", self._test_selected),
            ("open", "打开资源管理器", self._open_selected),
        ]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            self.action_buttons[key] = button
            action_layout.addWidget(button)
            action = QAction(label, self)
            action.triggered.connect(callback)
            self.row_actions[key] = action
            selected_menu.addAction(action)
        layout.addLayout(action_layout)
        self.setCentralWidget(central)
        toolbar = QToolBar("全局操作", self)
        self.global_actions: dict[str, QAction] = {}
        for key, label, callback in [
            ("refresh", "刷新", lambda: self._refresh_all_statuses(force=True)),
            ("connect_all", "连接全部", self._connect_all),
            ("disconnect_all", "断开全部", self._disconnect_all),
            ("import", "导入", self._import_profiles),
            ("export", "导出", self._export_profiles),
            ("settings", "设置", self._show_settings),
        ]:
            action = QAction(label, self)
            action.triggered.connect(callback)
            self.global_actions[key] = action
            toolbar.addAction(action)
        self.addToolBar(toolbar)
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("就绪")
        self._update_actions()

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        menu = QMenu(self)
        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self._show_window)
        connect_action = QAction("连接全部", self)
        connect_action.triggered.connect(self._connect_all)
        disconnect_action = QAction("断开全部", self)
        disconnect_action.triggered.connect(self._disconnect_all)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit)
        for action in (show_action, connect_action, disconnect_action, quit_action):
            menu.addAction(action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda _reason: self._show_window())
        self.tray.show()

    def refresh_table(self, selected_profile_id: str | None = None) -> None:
        """Redraw rows from cached real statuses and restore selection by profile ID."""
        preserved_id = (
            selected_profile_id if selected_profile_id is not None else self._selected_id()
        )
        profiles = self._profiles.list_profiles()
        self.table.blockSignals(True)
        self.table.clearContents()
        self.table.setRowCount(len(profiles))
        restored_row: int | None = None
        for row, profile in enumerate(profiles):
            status = self._status_cache.get(profile.id, ConnectionStatus.UNKNOWN)
            values = [
                profile.name,
                profile.remote_path.value,
                profile.drive_letter.value,
                profile.qualified_username,
                "是" if profile.auto_connect else "否",
                STATUS_TEXT[status],
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, profile.id)
                self.table.setItem(row, column, item)
            if profile.id == preserved_id:
                restored_row = row
        self.table.clearSelection()
        if restored_row is not None:
            self.table.setCurrentCell(
                restored_row,
                0,
                QItemSelectionModel.SelectionFlag.ClearAndSelect
                | QItemSelectionModel.SelectionFlag.Rows,
            )
        self.table.blockSignals(False)
        self._update_actions()

    def _safe_status(self, profile_id: str) -> ConnectionStatus:
        try:
            return self._connections.status(profile_id)
        except Exception:
            self._logger.exception("Unable to inspect SMB mapping for profile %s", profile_id)
            return ConnectionStatus.UNKNOWN

    def _selected_id(self) -> str | None:
        selection_model = self.table.selectionModel()
        if selection_model is None:
            return None
        selected_rows = selection_model.selectedRows(0)
        if len(selected_rows) != 1:
            return None
        item = self.table.item(selected_rows[0].row(), 0)
        profile_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return profile_id if isinstance(profile_id, str) else None

    def _update_actions(self) -> None:
        selected = self._selected_id()
        status = self._status_cache.get(selected, ConnectionStatus.UNKNOWN) if selected else None
        enabled = self._compute_action_state(selected, status)
        for key, button in self.action_buttons.items():
            button.setEnabled(enabled[key])
            self.row_actions[key].setEnabled(enabled[key])
        self.global_actions["refresh"].setEnabled(not self._bulk_busy)
        self.global_actions["connect_all"].setEnabled(not self._bulk_busy)
        self.global_actions["disconnect_all"].setEnabled(not self._bulk_busy)
        self.global_actions["import"].setEnabled(not self._bulk_busy)
        self.global_actions["export"].setEnabled(not self._bulk_busy)
        self.global_actions["settings"].setEnabled(not self._bulk_busy)

    def _compute_action_state(
        self, selected_profile_id: str | None, status: ConnectionStatus | None
    ) -> dict[str, bool]:
        state = {key: key == "new" for key in self.action_buttons}
        if selected_profile_id is None:
            return state
        state.update({"edit": True, "copy": True, "delete": True, "test": True})
        if selected_profile_id in self._busy or status in {
            ConnectionStatus.CONNECTING,
            ConnectionStatus.DISCONNECTING,
        }:
            return state
        if status == ConnectionStatus.CONNECTED:
            state.update({"disconnect": True, "reconnect": True, "open": True})
            return state
        state["connect"] = True
        return state

    def _refresh_all_statuses(self, force: bool = False) -> None:
        if self._bulk_busy:
            return
        profiles = self._profiles.list_profiles()

        generations = {
            profile.id: self._status_generation.get(profile.id, 0) for profile in profiles
        }

        def inspect_all() -> dict[str, tuple[ConnectionStatus, int]]:
            return {
                profile.id: (self._safe_status(profile.id), generations[profile.id])
                for profile in profiles
            }

        self._runner.submit(
            inspect_all,
            lambda statuses: self._apply_statuses(statuses, force),
            self._show_error,
            lambda: None,
        )

    def _apply_statuses(self, statuses: object, force: bool = False) -> None:
        if not isinstance(statuses, dict):
            return
        for profile_id, result in statuses.items():
            if not isinstance(profile_id, str) or not isinstance(result, tuple) or len(result) != 2:
                continue
            status, generation = result
            if (
                isinstance(status, ConnectionStatus)
                and isinstance(generation, int)
                and generation == self._status_generation.get(profile_id, 0)
                and (force or self._error_generation.get(profile_id) != generation)
            ):
                self._status_cache[profile_id] = status
        self.refresh_table()

    def _new_profile(self) -> None:
        dialog = ProfileDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._profiles.create(dialog.profile_value(), dialog.password_value())
            self.refresh_table()
            self._refresh_all_statuses()
            self.statusBar().showMessage("配置已保存。", 4000)
        except (ValidationError, Exception) as error:
            self._show_error(str(error))

    def _edit_selected(self) -> None:
        profile_id = self._selected_id()
        if profile_id is None:
            return
        if self._status_cache.get(profile_id) == ConnectionStatus.CONNECTED:
            answer = QMessageBox.question(
                self,
                "编辑已连接配置",
                "该配置当前已连接。修改 SMB 地址或盘符不会改变现有网络映射，是否继续编辑？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        dialog = ProfileDialog(self, self._profiles.get(profile_id))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._profiles.update(dialog.profile_value(), dialog.password_value())
            self._status_cache.pop(profile_id, None)
            self._error_generation.pop(profile_id, None)
            self.refresh_table()
            self._refresh_all_statuses()
            self.statusBar().showMessage("配置已更新。", 4000)
        except (ValidationError, Exception) as error:
            self._show_error(str(error))

    def _copy_selected(self) -> None:
        profile_id = self._selected_id()
        if profile_id is None:
            return
        source = self._profiles.get(profile_id)
        dialog = ProfileDialog(self)
        dialog.name_edit.setText(f"{source.name} 副本")
        dialog.remote_edit.setText(source.remote_path.value)
        dialog.username_edit.setText(source.username)
        dialog.domain_edit.setText(source.domain)
        dialog.note_edit.setText(source.note)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._profiles.create(dialog.profile_value(), dialog.password_value())
            self.refresh_table()
            self._refresh_all_statuses()
        except (ValidationError, Exception) as error:
            self._show_error(str(error))

    def _delete_selected(self) -> None:
        profile_id = self._selected_id()
        if profile_id is None:
            return
        profile = self._profiles.get(profile_id)
        connected_notice = ""
        if self._status_cache.get(profile_id) == ConnectionStatus.CONNECTED:
            connected_notice = "\n\n此配置当前已连接。删除配置不会断开该网络驱动器。"
        answer = QMessageBox.question(
            self,
            "删除配置",
            f"确定删除“{profile.name}”吗？此操作不会断开非本配置的网络驱动器。{connected_notice}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        delete_password = (
            QMessageBox.question(
                self,
                "删除保存的密码",
                "是否同时从 Windows 凭据管理器删除此配置的保存密码？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )
        try:
            self._profiles.delete(profile_id, delete_password)
            self._status_cache.pop(profile_id, None)
            self._error_generation.pop(profile_id, None)
            self.refresh_table()
        except Exception as error:
            self._show_error(str(error))

    def _password_for(self, profile: Profile) -> str | None:
        if profile.credential_ref or not profile.username:
            return ""
        password, accepted = QInputDialog.getText(
            self, "需要密码", "此配置未保存密码，请输入密码：", QLineEdit.EchoMode.Password
        )
        return password if accepted else None

    def _connect_selected(self) -> None:
        profile_id = self._selected_id()
        if profile_id:
            profile = self._profiles.get(profile_id)
            password = self._password_for(profile)
            if password is not None:
                self._run_profile(
                    profile_id, lambda: self._connections.connect(profile_id, password)
                )

    def _disconnect_selected(self) -> None:
        profile_id = self._selected_id()
        if profile_id:
            self._run_profile(profile_id, lambda: self._connections.disconnect(profile_id))

    def _reconnect_selected(self) -> None:
        profile_id = self._selected_id()
        if profile_id:
            profile = self._profiles.get(profile_id)
            password = self._password_for(profile)
            if password is not None:
                self._run_profile(
                    profile_id, lambda: self._connections.reconnect(profile_id, password)
                )

    def _test_selected(self) -> None:
        profile_id = self._selected_id()
        if profile_id:
            self._run_profile(profile_id, lambda: self._connections.test_connection(profile_id))

    def _open_selected(self) -> None:
        profile_id = self._selected_id()
        if profile_id is None:
            return
        profile = self._profiles.get(profile_id)
        if self._status_cache.get(profile_id) != ConnectionStatus.CONNECTED:
            self._show_error("该配置尚未正确连接，无法打开资源管理器。")
            return
        QProcess.startDetached("explorer.exe", [profile.drive_letter.value + "\\"])

    def _run_profile(self, profile_id: str, operation: Callable[[], object]) -> None:
        if profile_id in self._busy:
            return
        self._busy.add(profile_id)
        self._status_generation[profile_id] = self._status_generation.get(profile_id, 0) + 1
        self._update_actions()
        self.statusBar().showMessage("操作正在后台执行…")
        self._runner.submit(
            operation,
            lambda result: self._operation_succeeded(profile_id, result),
            lambda message: self._operation_failed(profile_id, message),
            lambda: self._operation_finished(profile_id),
        )

    def _operation_succeeded(self, profile_id: str, result: object) -> None:
        status = getattr(result, "status", None)
        if isinstance(status, ConnectionStatus):
            self._status_cache[profile_id] = status
            self._error_generation.pop(profile_id, None)
        message = getattr(result, "message", "操作完成。")
        self.statusBar().showMessage(str(message), 5000)

    def _operation_failed(self, profile_id: str, message: str) -> None:
        self._status_cache[profile_id] = ConnectionStatus.ERROR
        self._error_generation[profile_id] = self._status_generation.get(profile_id, 0)
        self._show_error(message)

    def _operation_finished(self, profile_id: str) -> None:
        self._busy.discard(profile_id)
        self.refresh_table(profile_id)

    def _connect_all(self) -> None:
        self._run_bulk(self._connections.connect_all, "连接全部")

    def _disconnect_all(self) -> None:
        self._run_bulk(self._connections.disconnect_all, "断开全部")

    def _auto_connect(self) -> None:
        self._run_bulk(self._connections.auto_connect, "自动连接")

    def _run_bulk(self, operation: Callable[[], object], label: str) -> None:
        if self._bulk_busy:
            return
        self._bulk_busy = True
        for profile in self._profiles.list_profiles():
            self._status_generation[profile.id] = self._status_generation.get(profile.id, 0) + 1
        self._update_actions()
        self.statusBar().showMessage(f"{label}正在后台执行…")
        self._runner.submit(
            operation,
            lambda results: self._bulk_completed(label, results),
            self._show_error,
            self._bulk_finished,
        )

    def _bulk_completed(self, label: str, results: object) -> None:
        values = list(results) if isinstance(results, list) else []
        for result in values:
            profile_id = getattr(result, "profile_id", None)
            status = getattr(result, "status", None)
            if isinstance(profile_id, str) and isinstance(status, ConnectionStatus):
                self._status_cache[profile_id] = status
        success = sum(1 for result in values if result.status == ConnectionStatus.CONNECTED)
        failed = sum(
            1
            for result in values
            if result.status in {ConnectionStatus.ERROR, ConnectionStatus.CONFLICT}
        )
        skipped = len(values) - success - failed
        self.statusBar().showMessage(
            f"{label}完成：成功 {success}，失败 {failed}，跳过 {skipped}。", 7000
        )

    def _bulk_finished(self) -> None:
        self._bulk_busy = False
        self.refresh_table()

    def _import_profiles(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "导入配置", "", "JSON 文件 (*.json)")
        if not filename:
            return
        try:
            imported, messages = self._profiles.import_profiles(Path(filename))
            self.refresh_table()
            detail = "\n".join(messages) if messages else ""
            QMessageBox.information(self, "导入结果", f"已导入 {imported} 个配置。\n{detail}")
        except Exception as error:
            self._show_error(str(error))

    def _export_profiles(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出配置", "smb-config.json", "JSON 文件 (*.json)"
        )
        if not filename:
            return
        try:
            self._profiles.export_profiles(Path(filename))
            self.statusBar().showMessage("已导出配置；导出文件不包含密码。", 5000)
        except Exception as error:
            self._show_error(str(error))

    def _show_settings(self) -> None:
        try:
            startup_enabled = self._startup.is_enabled()
        except Exception:
            startup_enabled = False
        dialog = SettingsDialog(self._close_to_tray, startup_enabled, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._close_to_tray = dialog.close_to_tray.isChecked()
            settings = self._profiles.settings
            settings["close_to_tray"] = self._close_to_tray
            self._profiles.save_settings(settings)
            self._startup.set_enabled(Path(sys.executable), dialog.startup.isChecked())
            self.statusBar().showMessage("设置已保存。", 5000)
        except Exception as error:
            self._show_error(str(error))

    def _show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit(self) -> None:
        self._quitting = True
        self._runner.wait_for_done()
        self.tray.hide()
        self.close()

    def _show_error(self, message: str) -> None:
        self._logger.warning("User-visible operation error: %s", message)
        self.statusBar().showMessage(message, 8000)
        QMessageBox.warning(self, "操作未完成", message)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override name
        if self._close_to_tray and not self._quitting and self.tray.isVisible():
            self.hide()
            self.tray.showMessage("LiteSMB Manager", "程序仍在系统托盘中运行。")
            event.ignore()
            return
        self._runner.wait_for_done()
        self.tray.hide()
        event.accept()
