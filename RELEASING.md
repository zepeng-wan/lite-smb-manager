# 发布流程

以下流程用于创建新版本，旧标签和已发布附件必须保持不可变。

1. 在 `pyproject.toml` 更新版本号，并同步 `src/lite_smb_manager/__init__.py` 与 `CHANGELOG.md`。
2. 运行 `.\scripts\test.ps1`、`.\scripts\security-scan.ps1` 和 `.\scripts\pre-publish-scan.ps1`。
3. 运行 `.\scripts\package.ps1`，生成 `release/` 下的 ZIP、`SHA256SUMS.txt` 和 Release Notes。
4. 在隔离目录解压 ZIP 并启动其中的 EXE；确认 ZIP 不含缓存、测试、配置、日志和凭据。
5. 审查待提交文件后提交；不要提交 `build/`、`dist/` 或 `release/`。
6. 推送通过审核的 `main`，等待 GitHub Actions 通过。
7. 创建指向通过 CI 的提交的 annotated tag，例如 `v1.0.1`，再推送标签。
8. 以该既有标签创建 Draft Release，上传 ZIP 与 `SHA256SUMS.txt`，使用 `release/RELEASE_NOTES-v<version>.md`。
9. 下载 Draft 附件并重新计算 SHA-256；确认标题、标签、目标提交、附件大小和 Release Notes。
10. 发布为 Latest（非预发布），再验证 Release 页面、标签和附件下载。

使用 PowerShell 校验下载文件：

```powershell
Get-FileHash .\LiteSMBManager-v<version>-windows-x64.zip -Algorithm SHA256
```

没有代码签名证书时，必须在 Release Notes 说明 SmartScreen 可能提示未知发布者；不得伪造签名或建议用户关闭
Defender/SmartScreen。发布失败时停止，不移动标签、不强推、不替换同名附件；修复后发布新的补丁版本。
