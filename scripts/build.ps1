[CmdletBinding()]
param(
    [string]$Version
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
    $packageName = "LiteSMBManager-$Version"
    $pyInstallerArgs = @(
        '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed', '--name', $packageName,
        '--add-data', 'src\lite_smb_manager\presentation\assets;lite_smb_manager\presentation\assets',
        'src\lite_smb_manager\bootstrap.py'
    )
    & $pythonExe @pyInstallerArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $executable = Join-Path $projectRoot "dist\$packageName\$packageName.exe"
    if (-not (Test-Path -LiteralPath $executable)) { throw "未找到打包产物：$executable" }
    $smokeRoot = Join-Path $projectRoot 'build\smoke-build'
    New-Item -ItemType Directory -Force -Path (Join-Path $smokeRoot 'AppData'), (Join-Path $smokeRoot 'LocalAppData') | Out-Null
    $process = Start-Process -FilePath $executable -WorkingDirectory (Split-Path -Parent $executable) -Environment @{
        APPDATA = (Join-Path $smokeRoot 'AppData')
        LOCALAPPDATA = (Join-Path $smokeRoot 'LocalAppData')
    } -PassThru
    Start-Sleep -Seconds 3
    if ($process.HasExited) { throw "打包程序启动失败，退出码：$($process.ExitCode)" }
    Stop-Process -Id $process.Id -Force
    Write-Host "打包与启动冒烟测试通过：$executable"
}
finally {
    Pop-Location
}
