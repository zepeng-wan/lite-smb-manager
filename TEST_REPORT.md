# 测试报告（v1.0.1）

执行环境：Windows 11 x64（10.0.26200）、Python 3.12.10、PySide6 6.9.3、pytest 8.4.2。
执行日期：2026-09-11。所有命令均在项目根目录执行。

## 回归根因与覆盖缺口

修复前的基线为 **47 passed / 1 skipped，核心覆盖率 92.76%**。这些测试没有捕获本问题，因为 UI
只用 `selectRow(0)` 浅测了“编辑”按钮，未以鼠标/键盘触发表格选择信号、未核验稳定 `profile_id`、未比较
菜单 QAction 与底部按钮，也没有覆盖真实耗时任务的 `finished` 回调、连接失败恢复、批量逐行更新或刷新后
选择保持。

确认的根因有三项：

1. `TaskRunner` 未强引用提交到 `QThreadPool` 的 `_Task`，真实 WNet 任务的 Python 包装对象可能在 GUI
   回调前被回收，导致成功/失败/finished 回调不完整，`_busy` 不能释放。
2. 主窗口原先没有集中且基于连接状态的操作矩阵；底部按钮没有与菜单 QAction 共用状态来源，刷新时也没有
   用配置 ID 恢复选择。
3. WNet 操作返回后没有再次查询实际盘符；UNC 直接比较没有统一处理大小写和末尾反斜杠。并且较早的异步
   刷新可覆盖刚完成操作的显示结果。

## 实际结果

| 检查 | 实际命令 | 结果 |
| --- | --- | --- |
| 格式 | `.venv\Scripts\python.exe -m ruff format --check .` | PASSED，43 个文件已格式化。 |
| 静态检查 | `.venv\Scripts\python.exe -m ruff check .` | PASSED。 |
| 类型检查 | `.venv\Scripts\python.exe -m mypy src` | PASSED，19 个源文件无问题。 |
| 全量测试与覆盖率 | `.venv\Scripts\python.exe -m pytest --cov` | PASSED，60 passed / 1 skipped；核心覆盖率 92.31%（阈值 85%）。Domain 87%，Application 94%。 |
| 新增 UI 回归集 | `.venv\Scripts\python.exe -m pytest tests\test_ui.py -q` | PASSED，14 passed。 |
| 敏感信息扫描 | `.\scripts\security-scan.ps1` | PASSED，未发现疑似硬编码 SMB 密码。 |
| 发布前扫描 | `.\scripts\pre-publish-scan.ps1` | PASSED，候选公开文件与空 Git 历史中未发现 Token、私钥、私网 UNC、个人路径或私网地址。 |
| PowerShell 脚本语法 | `Parser.ParseFile` 检查 `scripts\build.ps1` | PASSED。 |
| 源码启动烟测 | 隔离 `APPDATA` / `LOCALAPPDATA` 后启动 `.venv\Scripts\python.exe -m lite_smb_manager.bootstrap` 3 秒 | PASSED；进程存活后仅终止烟测进程。 |
| PyInstaller | `.\scripts\build.ps1 -Version 1.0.1` | PASSED，生成独立 one-folder 便携包，未覆盖 v1.0.0。 |
| 新 EXE 启动烟测 | 隔离 `APPDATA` / `LOCALAPPDATA` 后启动 v1.0.1 EXE 5 秒 | PASSED；进程存活且确认 `qwindows.dll`，随后仅终止烟测进程。 |
| 正式 ZIP | `.\scripts\package.ps1` | PASSED；生成 ZIP、SHA256SUMS 与 Release Notes，在全新解压目录隔离启动 EXE。 |
| 干净环境安装 | 新建 Python 3.12 虚拟环境后执行 `pip install .[dev]` | PASSED；导入应用并隔离启动源码。 |
| Git 状态 | `git status --short` | PASSED（新初始化仓库，源码均为待首次提交文件；`build` / `dist` 未列入）。 |

## 新增/扩展回归覆盖

- 真实鼠标单击第二行后，以该行 `profile_id` 驱动完整行操作状态；未连接、已连接和错误状态的按钮矩阵。
- 底部按钮与“所选配置”菜单 QAction 的逐项一致性。
- 连接成功后验证真实映射、表格变“已连接”、保留选择、清除 busy 并启用断开。
- 连接失败后显示中文错误、清除 busy 且编辑/复制/删除/重试仍可用。
- “连接全部”中一行成功、一行失败时的独立状态更新。
- 刷新/重建表格后按 `profile_id` 恢复选择；精确断开后重新查询并恢复连接按钮。
- 排序后编辑、复制、删除仍操作被选中配置的不可变 ID；复制生成新 ID 且无凭据。
- 适配器成功返回但实际未产生映射时，服务拒绝宣称已连接；UNC 的大小写、斜杠和末尾分隔符规范化。

## PASSED / FAILED / SKIPPED

- **PASSED**：全部 60 项不依赖真实 SMB 的自动化测试、Ruff、mypy、敏感信息扫描、源码启动烟测、v1.0.1
  PyInstaller 构建、新 EXE 启动烟测、正式 ZIP 和干净环境安装验证。
- **FAILED**：无。
- **SKIPPED**：`tests/test_windows_integration.py::test_real_smb_mapping_lifecycle`。未提供
  `SMB_TEST_UNC`、`SMB_TEST_USER`、`SMB_TEST_PASSWORD`、`SMB_TEST_DRIVE`，因此没有执行真实 SMB 连接或
  断开，也没有读取、打印或修改任何用户现有网络映射。

所有不依赖真实 SMB 服务器的自动化测试已经完成；真实网络驱动器挂载需要用户按照
`VERIFICATION_CHECKLIST.md` 执行最终验证。
