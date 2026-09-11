# 开发说明

LiteSMB Manager 采用 Python 3.12、PySide6 和 Windows 原生 MPR/WNet API。目录职责及依赖方向见根目录
`ARCHITECTURE.md`。

```powershell
.\scripts\setup.ps1 -Dev
.\scripts\run.ps1
.\scripts\test.ps1
.\scripts\build.ps1
.\scripts\package.ps1
```

`test.ps1` 包含 Ruff、mypy 和 pytest coverage。真实 SMB 集成测试是显式 opt-in：未设置测试环境变量时显示
SKIPPED，这是安全预期而不是通过结果。

不要将用户配置、日志、Windows 凭据、网络地址或打包输出加入 Git。发布详情见 `RELEASING.md`。
