from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox

import lite_smb_manager.presentation.main_window as main_window_module
from lite_smb_manager.application.services import ConnectionService, ProfileService, StartupService
from lite_smb_manager.domain.models import ConnectionStatus, Profile
from lite_smb_manager.presentation.main_window import MainWindow
from lite_smb_manager.presentation.profile_dialog import ProfileDialog
from tests.fakes import FakeCredentialStore, FakeMapper, FakeRepository, FakeStartup


def build_window() -> tuple[MainWindow, ProfileService, FakeMapper]:
    credentials = FakeCredentialStore()
    profiles = ProfileService(FakeRepository(), credentials)
    mapper = FakeMapper()
    window = MainWindow(
        profiles,
        ConnectionService(profiles, mapper, credentials),
        StartupService(FakeStartup()),
        logging.getLogger("ui-test"),
    )
    return window, profiles, mapper


def test_main_window_starts_with_empty_table(qtbot: object) -> None:
    window, _, _ = build_window()
    qtbot.addWidget(window)
    window.show()
    assert window.table.rowCount() == 0
    assert not window.action_buttons["connect"].isEnabled()


def test_profile_dialog_validates_and_password_toggle_works(qtbot: object) -> None:
    dialog = ProfileDialog()
    qtbot.addWidget(dialog)
    dialog.name_edit.setText("NAS")
    dialog.remote_edit.setText(r"\\server\share")
    dialog.drive_edit.setText("N:")
    dialog.password_edit.setText("secret")
    assert dialog.password_edit.echoMode().name == "Password"
    qtbot.mouseClick(dialog.show_password_button, Qt.MouseButton.LeftButton)
    assert dialog.password_edit.echoMode().name == "Normal"
    assert dialog.profile_value().drive_letter.value == "N:"


def test_list_updates_after_profile_creation(qtbot: object) -> None:
    window, profiles, _ = build_window()
    qtbot.addWidget(window)
    profiles.create(Profile.new(name="NAS", remote_path=r"\\server\share", drive_letter="N:"))
    window.refresh_table()
    assert window.table.rowCount() == 1
    window.table.selectRow(0)
    assert window.action_buttons["edit"].isEnabled()


def test_background_connect_refreshes_status_without_blocking(qtbot: object) -> None:
    window, profiles, mapper = build_window()
    qtbot.addWidget(window)
    profile = profiles.create(
        Profile.new(name="NAS", remote_path=r"\\server\share", drive_letter="N:")
    )
    window.refresh_table()
    window.table.selectRow(0)
    window._connect_selected()
    qtbot.waitUntil(lambda: mapper.mappings.get("N:") == profile.remote_path.value, timeout=3000)
    qtbot.waitUntil(lambda: window.table.item(0, 5).text() == "已连接", timeout=3000)


def test_delete_cancel_keeps_profile(qtbot: object, monkeypatch: object) -> None:
    window, profiles, _ = build_window()
    qtbot.addWidget(window)
    profile = profiles.create(
        Profile.new(name="NAS", remote_path=r"\\server\share", drive_letter="N:")
    )
    window.refresh_table()
    window.table.selectRow(0)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    window._delete_selected()
    assert profiles.get(profile.id).id == profile.id


def test_close_to_tray_hides_window(qtbot: object) -> None:
    window, _, _ = build_window()
    qtbot.addWidget(window)
    window.show()
    window.close()
    assert not window.isVisible()
    window._quitting = True
    window.close()


def _add_two_profiles(profiles: ProfileService) -> tuple[Profile, Profile]:
    first = profiles.create(
        Profile.new(name="alpha", remote_path=r"\\server\alpha", drive_letter="N:")
    )
    second = profiles.create(
        Profile.new(name="nas", remote_path=r"\\server\nas", drive_letter="O:")
    )
    return first, second


def _click_row(qtbot: object, window: MainWindow, row: int) -> None:
    item = window.table.item(row, 1)
    assert item is not None
    qtbot.mouseClick(
        window.table.viewport(),
        Qt.MouseButton.LeftButton,
        pos=window.table.visualItemRect(item).center(),
    )


def _assert_action_parity(window: MainWindow) -> None:
    for key, button in window.action_buttons.items():
        assert button.isEnabled() == window.row_actions[key].isEnabled(), key


def test_clicking_second_row_uses_profile_id_and_enables_disconnected_actions(
    qtbot: object,
) -> None:
    window, profiles, _ = build_window()
    qtbot.addWidget(window)
    first, nas = _add_two_profiles(profiles)
    window.refresh_table()
    window.show()
    assert window._selected_id() is None
    assert not window.action_buttons["edit"].isEnabled()
    _click_row(qtbot, window, 1)
    assert first.id != nas.id
    assert window._selected_id() == nas.id
    for key in ("edit", "copy", "delete", "connect", "test"):
        assert window.action_buttons[key].isEnabled(), key
    for key in ("disconnect", "reconnect", "open"):
        assert not window.action_buttons[key].isEnabled(), key
    _assert_action_parity(window)


def test_connected_row_enables_only_connected_actions_and_menu_parity(qtbot: object) -> None:
    window, profiles, mapper = build_window()
    qtbot.addWidget(window)
    _, nas = _add_two_profiles(profiles)
    mapper.mappings[nas.drive_letter.value] = nas.remote_path.value
    window.refresh_table()
    window.show()
    _click_row(qtbot, window, 1)
    window._refresh_all_statuses()
    qtbot.waitUntil(lambda: window.table.item(1, 5).text() == "已连接", timeout=3000)
    assert window._selected_id() == nas.id
    for key in ("edit", "copy", "delete", "disconnect", "reconnect", "test", "open"):
        assert window.action_buttons[key].isEnabled(), key
    assert not window.action_buttons["connect"].isEnabled()
    _assert_action_parity(window)


def test_connect_completion_refreshes_real_mapping_keeps_selection_and_unblocks(
    qtbot: object,
) -> None:
    window, profiles, mapper = build_window()
    qtbot.addWidget(window)
    profile = profiles.create(
        Profile.new(name="nas", remote_path=r"\\server\nas", drive_letter="N:")
    )
    window.refresh_table()
    window.show()
    _click_row(qtbot, window, 0)
    window._connect_selected()
    qtbot.waitUntil(lambda: mapper.mappings.get("N:") == profile.remote_path.value, timeout=3000)
    qtbot.waitUntil(lambda: window.table.item(0, 5).text() == "已连接", timeout=3000)
    qtbot.waitUntil(lambda: profile.id not in window._busy, timeout=3000)
    assert window._selected_id() == profile.id
    assert window.action_buttons["disconnect"].isEnabled()
    assert not window.action_buttons["connect"].isEnabled()


def test_connect_failure_clears_busy_and_preserves_recoverable_actions(
    qtbot: object, monkeypatch: object
) -> None:
    window, profiles, mapper = build_window()
    qtbot.addWidget(window)
    profile = profiles.create(
        Profile.new(name="nas", remote_path=r"\\server\nas", drive_letter="N:")
    )
    mapper.fail_connect = 1219
    messages: list[str] = []
    monkeypatch.setattr(window, "_show_error", messages.append)
    window.refresh_table()
    window.show()
    _click_row(qtbot, window, 0)
    window._connect_selected()
    qtbot.waitUntil(lambda: profile.id not in window._busy, timeout=3000)
    assert window.table.item(0, 5).text() == "连接失败"
    assert messages and "不会自动断开" in messages[0]
    for key in ("edit", "copy", "delete", "connect", "test"):
        assert window.action_buttons[key].isEnabled(), key


def test_connect_all_updates_success_and_failure_rows_independently(qtbot: object) -> None:
    window, profiles, mapper = build_window()
    qtbot.addWidget(window)
    first, nas = _add_two_profiles(profiles)
    mapper.fail_connect_for_drive[nas.drive_letter.value] = 1219
    window.refresh_table()
    window.show()
    _click_row(qtbot, window, 1)
    window._connect_all()
    qtbot.waitUntil(lambda: not window._bulk_busy, timeout=3000)
    assert mapper.mappings[first.drive_letter.value] == first.remote_path.value
    assert window.table.item(0, 5).text() == "已连接"
    assert window.table.item(1, 5).text() == "连接失败"
    assert window._selected_id() == nas.id
    assert window.action_buttons["connect"].isEnabled()


def test_status_refresh_restores_selection_by_profile_id(qtbot: object) -> None:
    window, profiles, mapper = build_window()
    qtbot.addWidget(window)
    _, nas = _add_two_profiles(profiles)
    mapper.mappings[nas.drive_letter.value] = nas.remote_path.value
    window.refresh_table()
    window.show()
    _click_row(qtbot, window, 1)
    window._refresh_all_statuses()
    qtbot.waitUntil(lambda: window.table.item(1, 5).text() == "已连接", timeout=3000)
    assert window._selected_id() == nas.id
    assert window.action_buttons["disconnect"].isEnabled()


def test_disconnect_selected_verifies_mapping_and_reenables_connect(qtbot: object) -> None:
    window, profiles, mapper = build_window()
    qtbot.addWidget(window)
    profile = profiles.create(
        Profile.new(name="nas", remote_path=r"\\server\nas", drive_letter="N:")
    )
    mapper.mappings[profile.drive_letter.value] = profile.remote_path.value
    window._status_cache[profile.id] = ConnectionStatus.CONNECTED
    window.refresh_table()
    window.show()
    _click_row(qtbot, window, 0)
    window._disconnect_selected()
    qtbot.waitUntil(lambda: not mapper.mappings, timeout=3000)
    qtbot.waitUntil(lambda: window.table.item(0, 5).text() == "未连接", timeout=3000)
    assert mapper.disconnect_calls == [profile.drive_letter.value]
    assert window.action_buttons["connect"].isEnabled()
    assert not window.action_buttons["disconnect"].isEnabled()


class _TextSink:
    def setText(self, value: str) -> None:  # noqa: N802 - Qt-compatible fake field method
        self.value = value


class _FakeProfileDialog:
    """Accept deterministic editor values without relying on a modal Qt dialog."""

    seen_profiles: list[Profile | None] = []

    def __init__(self, parent: object, profile: Profile | None = None) -> None:
        self._profile = profile
        self.seen_profiles.append(profile)
        self.name_edit = _TextSink()
        self.remote_edit = _TextSink()
        self.username_edit = _TextSink()
        self.domain_edit = _TextSink()
        self.note_edit = _TextSink()

    def exec(self) -> int:
        return int(QDialog.DialogCode.Accepted)

    def profile_value(self) -> Profile:
        if self._profile is not None:
            return self._profile.with_updates(note="edited through selected profile id")
        return Profile.new(
            name="nas copy",
            remote_path=r"\\server\nas-copy",
            drive_letter="P:",
        )

    def password_value(self) -> str:
        return ""


def test_edit_copy_and_delete_apply_to_selected_profile_id_after_sorting(
    qtbot: object, monkeypatch: object
) -> None:
    window, profiles, _ = build_window()
    qtbot.addWidget(window)
    first, nas = _add_two_profiles(profiles)
    window.refresh_table()
    window.show()
    _click_row(qtbot, window, 1)
    _FakeProfileDialog.seen_profiles = []
    monkeypatch.setattr(main_window_module, "ProfileDialog", _FakeProfileDialog)

    window._edit_selected()
    assert _FakeProfileDialog.seen_profiles == [nas]
    assert profiles.get(nas.id).note == "edited through selected profile id"
    assert profiles.get(first.id).note == ""

    window._copy_selected()
    copies = [profile for profile in profiles.list_profiles() if profile.name == "nas copy"]
    assert len(copies) == 1
    assert copies[0].id not in {first.id, nas.id}
    assert copies[0].credential_ref is None

    window.refresh_table(nas.id)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    window._delete_selected()
    assert profiles.get(first.id).id == first.id
    assert all(profile.id != nas.id for profile in profiles.list_profiles())
