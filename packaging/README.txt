LiteSMB Manager v1.0.1
=======================

Windows 10/11 x64 SMB 网络驱动器管理器。

1. 双击 LiteSMBManager.exe，以普通用户身份运行。
2. 新建配置，填写示例形式的 UNC：\\nas.example\media，以及空闲盘符。
3. 如需保存密码，应用只使用 Windows Credential Manager；不要把密码写入导出文件或 Issue。
4. 连接后使用“刷新”核对真实 Windows 映射；“断开”只处理所选且属于该配置的盘符。

本包未进行代码签名，Windows SmartScreen 可能显示未知发布者提示。请仅从项目 GitHub Release 下载，使用
SHA256SUMS.txt 校验 ZIP，且不要关闭 Defender 或 SmartScreen。

许可证：项目自有代码为 MIT（LICENSE）；第三方组件与许可证见 THIRD_PARTY_NOTICES.md。
配置在 %APPDATA%\LiteSMBManager，日志在 %LOCALAPPDATA%\LiteSMBManager\logs。
