[CmdletBinding()]
param(
    [string]$Version,
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw '未找到 .venv。请先运行 .\scripts\setup.ps1 -Dev。'
}
Push-Location $projectRoot
try {
    if (-not $Version) {
        $Version = & $pythonExe -c "import pathlib, tomllib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version'])"
        if ($LASTEXITCODE -ne 0 -or -not $Version) { throw '无法从 pyproject.toml 读取版本号。' }
    }
    if (-not $SkipBuild) {
        & (Join-Path $PSScriptRoot 'build.ps1') -Version $Version
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    $sourceDirectory = Join-Path $projectRoot "dist\LiteSMBManager-$Version"
    $sourceExecutable = Join-Path $sourceDirectory "LiteSMBManager-$Version.exe"
    if (-not (Test-Path -LiteralPath $sourceExecutable)) { throw "未找到构建产物：$sourceExecutable" }
    $releaseRoot = Join-Path $projectRoot 'release'
    $packageDirectoryName = "LiteSMBManager-v$Version-windows-x64"
    $packageDirectory = Join-Path $releaseRoot $packageDirectoryName
    $zipPath = Join-Path $releaseRoot "$packageDirectoryName.zip"
    $notesPath = Join-Path $releaseRoot "RELEASE_NOTES-v$Version.md"
    $checksumsPath = Join-Path $releaseRoot 'SHA256SUMS.txt'
    New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null
    if (Test-Path -LiteralPath $packageDirectory) { Remove-Item -LiteralPath $packageDirectory -Recurse -Force }
    if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
    Copy-Item -LiteralPath $sourceDirectory -Destination $packageDirectory -Recurse
    Move-Item -LiteralPath (Join-Path $packageDirectory "LiteSMBManager-$Version.exe") -Destination (Join-Path $packageDirectory 'LiteSMBManager.exe')
    Copy-Item -LiteralPath (Join-Path $projectRoot 'LICENSE') -Destination (Join-Path $packageDirectory 'LICENSE')
    Copy-Item -LiteralPath (Join-Path $projectRoot 'THIRD_PARTY_NOTICES.md') -Destination (Join-Path $packageDirectory 'THIRD_PARTY_NOTICES.md')
    Copy-Item -LiteralPath (Join-Path $projectRoot 'packaging\README.txt') -Destination (Join-Path $packageDirectory 'README.txt')
    Copy-Item -LiteralPath (Join-Path $projectRoot 'assets\licenses') -Destination (Join-Path $packageDirectory 'LICENSES') -Recurse
    Compress-Archive -LiteralPath $packageDirectory -DestinationPath $zipPath -CompressionLevel Optimal
    $hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath $checksumsPath -Value "$hash  $([IO.Path]::GetFileName($zipPath))" -Encoding utf8
    $notes = @"
# LiteSMB Manager v$Version

## 主要内容

- Windows 原生 MPR/WNet SMB 盘符映射、精确断开、刷新和批量操作。
- Windows Credential Manager 可选密码保存、配置导入导出、托盘与登录启动。
- 修复连接完成后的真实状态刷新、表格选择保持和行级操作可用性。

## 安装与升级

解压 ZIP 后运行 `LiteSMBManager.exe`。应用使用 `%APPDATA%\LiteSMBManager` 保存配置；升级不会把密码写入
普通文件。当前包未签名，SmartScreen 可能显示未知发布者提示；请仅从 GitHub Release 下载且不要关闭 Defender 或
SmartScreen。

## 校验

```powershell
Get-FileHash .\$([IO.Path]::GetFileName($zipPath)) -Algorithm SHA256
```

将输出与 `SHA256SUMS.txt` 对比。

## 已知限制

- 仅支持 Windows 10/11 x64 当前用户会话中的 SMB 网络盘。
- 未提供真实 SMB 测试凭据时，真实挂载集成测试保持 SKIPPED。
- 本版本没有代码签名；不会修改 SMB1、SMB 安全策略或无关网络映射。
"@
    Set-Content -LiteralPath $notesPath -Value $notes -Encoding utf8
    $verifyRoot = Join-Path $projectRoot 'build\package-verify'
    if (Test-Path -LiteralPath $verifyRoot) { Remove-Item -LiteralPath $verifyRoot -Recurse -Force }
    Expand-Archive -LiteralPath $zipPath -DestinationPath $verifyRoot
    $verifiedExecutable = Join-Path $verifyRoot "$packageDirectoryName\LiteSMBManager.exe"
    if (-not (Test-Path -LiteralPath $verifiedExecutable)) { throw '发布 ZIP 缺少 LiteSMBManager.exe。' }
    $packageSmokeRoot = Join-Path $projectRoot 'build\smoke-package'
    New-Item -ItemType Directory -Force -Path (Join-Path $packageSmokeRoot 'AppData'), (Join-Path $packageSmokeRoot 'LocalAppData') | Out-Null
    $process = Start-Process -FilePath $verifiedExecutable -WorkingDirectory (Split-Path -Parent $verifiedExecutable) -Environment @{
        APPDATA = (Join-Path $packageSmokeRoot 'AppData')
        LOCALAPPDATA = (Join-Path $packageSmokeRoot 'LocalAppData')
    } -PassThru
    Start-Sleep -Seconds 5
    if ($process.HasExited) { throw "发布 ZIP 中的 EXE 启动失败，退出码：$($process.ExitCode)" }
    Stop-Process -Id $process.Id -Force
    Write-Host "正式发布包验证通过：$zipPath"
    Write-Host "SHA-256：$hash"
}
finally {
    Pop-Location
}
