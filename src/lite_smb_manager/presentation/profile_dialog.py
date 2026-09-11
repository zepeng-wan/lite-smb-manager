"""Localized profile editor that never pre-fills a stored password."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from lite_smb_manager.domain.models import Profile, ValidationError


class ProfileDialog(QDialog):
    """Create or edit a profile, returning a password only for the current save action."""

    def __init__(self, parent: QWidget | None = None, profile: Profile | None = None) -> None:
        super().__init__(parent)
        self._profile = profile
        self.setWindowTitle("编辑 SMB 配置" if profile else "新建 SMB 配置")
        self.setMinimumWidth(430)
        form = QFormLayout()
        self.name_edit = QLineEdit(profile.name if profile else "")
        self.remote_edit = QLineEdit(profile.remote_path.value if profile else "")
        self.drive_edit = QLineEdit(profile.drive_letter.value if profile else "")
        self.username_edit = QLineEdit(profile.username if profile else "")
        self.domain_edit = QLineEdit(profile.domain if profile else "")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("留空可保留已保存的密码")
        self.show_password_button = QPushButton("显示")
        self.show_password_button.setCheckable(True)
        self.show_password_button.toggled.connect(self._toggle_password)
        password_layout = QHBoxLayout()
        password_layout.addWidget(self.password_edit)
        password_layout.addWidget(self.show_password_button)
        self.save_password_check = QCheckBox("保存到 Windows 凭据管理器")
        self.save_password_check.setChecked(profile.save_password if profile else False)
        self.auto_connect_check = QCheckBox("应用启动后自动连接")
        self.auto_connect_check.setChecked(profile.auto_connect if profile else False)
        self.note_edit = QTextEdit(profile.note if profile else "")
        self.note_edit.setMaximumHeight(80)
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #b00020;")
        self.error_label.setWordWrap(True)
        form.addRow("名称 *", self.name_edit)
        form.addRow("SMB 地址 *", self.remote_edit)
        form.addRow("盘符 *", self.drive_edit)
        form.addRow("用户名", self.username_edit)
        form.addRow("域或工作组", self.domain_edit)
        form.addRow("密码", password_layout)
        form.addRow("", self.save_password_check)
        form.addRow("", self.auto_connect_check)
        form.addRow("备注", self.note_edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

    def _toggle_password(self, visible: bool) -> None:
        self.password_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )
        self.show_password_button.setText("隐藏" if visible else "显示")

    def profile_value(self) -> Profile:
        base = Profile.new(
            name=self.name_edit.text(),
            remote_path=self.remote_edit.text(),
            drive_letter=self.drive_edit.text(),
            username=self.username_edit.text(),
            domain=self.domain_edit.text(),
            save_password=self.save_password_check.isChecked(),
            auto_connect=self.auto_connect_check.isChecked(),
            note=self.note_edit.toPlainText(),
        )
        if self._profile is None:
            return base
        return Profile(
            id=self._profile.id,
            name=base.name,
            remote_path=base.remote_path,
            drive_letter=base.drive_letter,
            username=base.username,
            domain=base.domain,
            credential_ref=self._profile.credential_ref,
            save_password=base.save_password,
            auto_connect=base.auto_connect,
            note=base.note,
            created_at=self._profile.created_at,
            updated_at=base.updated_at,
        )

    def password_value(self) -> str:
        return self.password_edit.text()

    def _validate_and_accept(self) -> None:
        try:
            self.profile_value()
        except ValidationError as error:
            self.error_label.setText(str(error))
            return
        self.accept()
