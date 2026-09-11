[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw '未找到 .venv。请先运行 .\scripts\setup.ps1 -Dev。'
}
& $pythonExe -m lite_smb_manager.bootstrap
exit $LASTEXITCODE
