[CmdletBinding()]
param(
    [switch]$Dev
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $projectRoot '.venv'
$installedPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
if (Test-Path -LiteralPath $installedPython) {
    & $installedPython -m venv $venvPath
} else {
    $pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
    if (-not $pythonLauncher) {
        throw '未找到 Python 3.12。请安装 64 位 Python 3.12 后重试。'
    }
    & $pythonLauncher.Source -3.12 -m venv $venvPath
}
$pythonExe = Join-Path $venvPath 'Scripts\python.exe'
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -e (Join-Path $projectRoot '.[dev]')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "环境已就绪：$pythonExe"
