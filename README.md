# LiteSMB Manager

LiteSMB Manager 是 Windows 10/11 x64 的轻量 SMB 网络驱动器管理器。它用系统原生
MPR/WNet API 把 `\\服务器\共享` 映射到当前普通用户会话中的盘符，并集中管理多个配置。

> A lightweight Windows SMB drive mapping manager built with Python and PySide6.

界面截图位置为 [`docs/screenshots/`](docs/screenshots/)；源码运行后可按同一目录补充本机截图。
程序图标为项目自行创建的 SVG，不使用 RaiDrive 或其他商业产品的资源。

## 下载与首次使用

从发布包解压 `LiteSMBManager` 文件夹后，双击 `LiteSMBManager.exe`。不要默认以管理员身份
启动：管理员进程创建的网络盘可能不会显示给普通资源管理器。首次打开时：

1. 点击“新建”，填写名称、完整 SMB 地址（例如 `\\nas.example\media`）和空闲盘符。
2. 如共享需要账号，填写用户名、可选域和密码；密码默认隐藏。
3. 勾选“保存到 Windows 凭据管理器”可供之后自动连接使用；未勾选的密码不会写入磁盘。
4. 保存后选择该行并点击“连接”。成功后可点击“打开资源管理器”。

主窗口支持编辑、复制、删除、连接、断开、重新连接、测试、刷新、连接全部和断开全部。删除时
可选择是否精确删除该配置对应的 Windows 凭据。断开操作会先核验盘符是否仍指向配置中的共享，
不会断开其他程序或其他配置的映射。

## 常用功能

- “测试连接”只测试服务器 SMB TCP 445 端口可达性，不把 Ping 当作共享可用或认证成功。
- 勾选“应用启动后自动连接”后，启动完成会在后台尝试连接；已正确连接的配置跳过，盘符冲突不会覆盖。
- 设置中的“随 Windows 登录启动”写入当前用户的 `HKCU\...\Run`，不要求管理员权限。
- 关闭窗口默认隐藏至系统托盘。托盘菜单提供显示、连接全部、断开全部和退出；可在设置中改为完全退出。
- 导出 JSON 不含密码、凭据目标或可恢复秘密。导入前会验证版本和每条数据，冲突/无效条目不会静默覆盖。

## 安全与常见错误

保存的密码仅进入 Windows Credential Manager；配置文件在 `%APPDATA%\LiteSMBManager\profiles.json`，
日志在 `%LOCALAPPDATA%\LiteSMBManager\logs\lite-smb-manager.log`。配置写入采用临时文件和原子替换；
损坏的配置会备份为 `profiles.corrupt.<时间>.json`，而不是阻止应用启动。

| Windows 错误 | 含义与建议 |
| --- | --- |
| 53、64 | 网络路径不可达：检查服务器、网络和 VPN。 |
| 67 | 共享名不存在：核对 `\\服务器\共享`。 |
| 85 | 盘符被占用：换一个空闲盘符，或确认该映射归属。 |
| 86、1326 | 密码或账号错误：重新输入并检查域/工作组。 |
| 1219 | 同一服务器已使用另一组凭据：统一账号或手动检查现有连接。应用绝不会全局断开其他映射。 |
| 2250 | 指定映射已不存在：刷新状态后再操作。 |

应用不会开启 SMB1、修改 SMB 安全策略、执行提升权限或上传任何配置/遥测数据。卸载便携包只需删除
解压目录；若要清除用户数据，请关闭程序后删除上述配置和日志目录，并在 Windows 凭据管理器删除
以 `LiteSMBManager/` 开头的对应凭据。

## 从源码运行、测试与打包

需要 Windows 10/11 x64 和 Python 3.12。PowerShell 中执行：

```powershell
cd C:\path\to\smb-manager
.\scripts\setup.ps1 -Dev
.\scripts\run.ps1
.\scripts\test.ps1
.\scripts\security-scan.ps1
.\scripts\build.ps1
```

`build.ps1` 生成版本化 one-folder 构建；`package.ps1` 生成可上传的 ZIP 和 SHA-256 清单。打包输出不应提交 Git。
真实 SMB 集成测试默认跳过；只有在确认测试盘符空闲且显式设置以下环境变量后，
才运行 ` .\scripts\test.ps1 -Integration`：`SMB_TEST_UNC`、`SMB_TEST_USER`、`SMB_TEST_PASSWORD`、
`SMB_TEST_DRIVE`，以及可选的 `SMB_TEST_DOMAIN`。测试在 `finally` 中只清理自身创建的映射。

更多架构、真实环境验收和实测结果见
[ARCHITECTURE.md](ARCHITECTURE.md)、[VERIFICATION_CHECKLIST.md](VERIFICATION_CHECKLIST.md) 和
[TEST_REPORT.md](TEST_REPORT.md)。贡献、开发、故障排查和后续发布流程分别见
[CONTRIBUTING.md](CONTRIBUTING.md)、[docs/development.md](docs/development.md)、
[docs/troubleshooting.md](docs/troubleshooting.md) 和 [RELEASING.md](RELEASING.md)。

## 已知限制

- 仅支持 Windows 原生 SMB 盘符映射，不支持 SMB 服务端、SMB1、FTP、SFTP、WebDAV 或文件同步。
- 真实挂载取决于用户的网络、共享权限和系统 SMB 客户端；没有真实 SMB 凭据时无法自动替代验证。
- “测试连接”不创建临时盘符，也不验证共享权限；使用“连接”完成真实认证和映射验证。
- 表格选中项以不可变的配置 ID 识别；刷新或后台操作完成后会恢复同一配置的选择。底部按钮和“所选配置”
  菜单共享一套状态规则。连接、断开和刷新后的显示均以 Windows 当前实际映射为准。
- Windows 便携包目前未进行代码签名。Windows SmartScreen 可能显示“未知发布者”提示；请仅从项目的
  GitHub Release 下载，并按发布页 SHA-256 校验文件。不要关闭 Defender 或 SmartScreen。

## 许可证与安全报告

本项目自有源码使用 [MIT License](LICENSE)。PySide6、Qt、Shiboken、Python 与 PyInstaller 等组件的
适用许可证见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。请勿在公开 Issue、日志或截图中提交密码、
Token、私钥、真实 UNC 或用户名；安全问题请按 [SECURITY.md](SECURITY.md) 的方式私下报告。
