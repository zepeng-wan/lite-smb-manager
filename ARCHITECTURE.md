# 架构说明

## 目录与依赖

```text
src/lite_smb_manager/
├── domain/          纯值对象、配置实体、验证和状态枚举
├── application/     用例、端口、Windows 错误到中文提示的映射
├── infrastructure/  JSON、日志、Credential Manager、MPR、Run 注册表适配器
├── presentation/    PySide6 窗口、表单、托盘和后台任务执行器
└── bootstrap.py     唯一组合根
```

依赖仅沿 `Presentation → Application → Domain` 方向流动；`Infrastructure` 实现
Application 定义的 Protocol，`bootstrap.py` 负责注入。Domain 不导入 Qt、Windows API、文件系统或网络。
UI 不直接调用 Windows 挂载、凭据、注册表或 JSON 文件。

## 关键设计与安全决策

1. Windows 挂载器只封装 Unicode `WNetAddConnection2W`、`WNetGetConnectionW` 和
   `WNetCancelConnection2W`，不解析本地化 `net use` 输出，也不调用 shell。
2. `Profile` 无密码字段；密码只在 `RuntimeCredentials` 中短暂存活，其 `repr` 始终脱敏。
   保存密码时由 `WindowsCredentialStore` 写到 `LiteSMBManager/<profile-id>`，普通 JSON 与导出文件
   只存元数据。
3. `JsonProfileRepository` 使用 UTF-8、schema v1、临时文件 + `fsync` + `os.replace`；读取损坏时
   将原文件移为带时间戳的 `.corrupt` 备份。
4. 每次断开前重新查询盘符。只有 MPR 返回“盘符指向此配置期望 UNC”时才断开，因此 1219 或盘符冲突
   不会触发广泛清理。
5. Qt `TaskRunner` 把连接、断开、测试和批量操作放进 `QThreadPool`，并强引用活动 `QRunnable` 直到
   `finished` 回调完成，避免真实 MPR 调用完成后 Python 包装对象过早回收。结果通过 Qt signal 回 GUI 线程。
   同一配置被加入 `_busy` 集合，冲突按钮被禁用。
6. `ConnectionService` 在 WNet 连接或断开返回后立即再次调用 `inspect`；只有真实盘符映射与规范化后的
   期望 UNC 一致才显示“已连接”。UNC 比较忽略大小写、斜杠方向和末尾反斜杠。
7. `MainWindow` 以 `profile_id` 保存和恢复选择，状态缓存有操作代次，防止较早的后台刷新覆盖刚完成的
   成功或失败结果。按钮和“所选配置”菜单 QAction 由同一集中状态计算函数更新。
8. 关闭到托盘默认开启并可设置；退出会等待已提交任务完成。登录启动仅写当前用户 Run 键，绝不提升权限。
9. 选择 one-folder PyInstaller 包以提高 Qt 插件可靠性。`build.ps1` 从 `pyproject.toml` 读取版本并执行隔离
   EXE 启动烟测；`package.ps1` 将已验证构建组装为无源码、无用户数据的 ZIP，附带许可证、第三方声明、哈希和
   隔离解压启动验证。

## 数据与诊断

配置位于 `%APPDATA%\LiteSMBManager\profiles.json`，日志位于
`%LOCALAPPDATA%\LiteSMBManager\logs\lite-smb-manager.log`。日志使用 1 MB × 3 的滚动策略，并在
写入前过滤常见 `password=`、`passwd=`、`pwd=` 形式的秘密。日志可包含 Windows 错误码，不记录密码。

## 测试边界

单元/UI 测试以 fake 端口覆盖业务流程和 offscreen Qt；这些并不宣称 MPR 真实挂载成功。真实集成测试
只能在原生 Windows、显式提供环境变量且测试盘符空闲时运行。详细结果以 `TEST_REPORT.md` 为准。
