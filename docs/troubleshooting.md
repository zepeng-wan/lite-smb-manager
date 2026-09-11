# 常见问题

## 连接后资源管理器看不到盘符

请以普通用户身份运行应用。管理员进程创建的网络驱动器可能不会显示给普通资源管理器；不要为此关闭 UAC 或修改
系统 SMB 安全策略。点击“刷新”会通过 Windows WNet API 重新读取真实映射。

## 错误 1219

Windows 不允许对同一服务器同时使用不同凭据。请统一账号或检查已有网络连接。应用不会自动断开无关映射。

## SmartScreen 提示

当前发布包未签名，Windows 可能显示未知发布者提示。仅从项目的 GitHub Release 下载，并使用发布页提供的
SHA-256 校验文件；不要关闭 Defender 或 SmartScreen。

## 需要诊断信息

日志在 `%LOCALAPPDATA%\LiteSMBManager\logs`。提交问题前删除密码、真实 UNC、用户名和本地路径。配置文件位于
`%APPDATA%\LiteSMBManager`，不包含明文密码。
