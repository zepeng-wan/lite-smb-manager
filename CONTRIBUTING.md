# 贡献指南

感谢关注 LiteSMB Manager。提交前请确保不包含任何真实 SMB 地址、用户名、密码、Token、私钥、用户配置或日志。

## 开发环境

项目目标为 Windows 10/11 x64 与 Python 3.12。使用 PowerShell：

```powershell
.\scripts\setup.ps1 -Dev
.\scripts\run.ps1
```

代码采用 `src` 布局。Domain 必须保持纯 Python；Application 只能依赖 Domain 和端口；Infrastructure 实现端口；
Presentation 不直接调用 Windows WNet、Credential Manager 或配置文件。

## 提交前检查

```powershell
.\scripts\test.ps1
.\scripts\security-scan.ps1
```

请保持代码注释使用英文、用户界面与用户文档使用简体中文，并遵守 Ruff 与 mypy。建议使用聚焦、可审查的
提交，例如 `fix: preserve table selection after status refresh`。

## Windows SMB 集成测试

真实测试默认安全跳过。只有在拥有授权测试共享、确认测试盘符空闲且愿意让测试精确清理**测试自身创建**的映射时，
才设置 `SMB_TEST_UNC`、`SMB_TEST_USER`、`SMB_TEST_PASSWORD`、`SMB_TEST_DRIVE`（可选
`SMB_TEST_DOMAIN`）并运行：

```powershell
.\scripts\test.ps1 -Integration
```

不要使用正在工作的盘符，不要把环境变量值、测试输出或截图提交到 Git。

## Pull Request

每个 Pull Request 应说明问题、实现方式、测试命令和结果。若改动影响 Windows 映射、凭据、日志、导出或打包，
请明确安全影响和回归覆盖。不要提交 `build/`、`dist/`、`release/`、`.venv/`、缓存或本地配置。
