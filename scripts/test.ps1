[CmdletBinding()]
param(
    [switch]$Integration
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw '未找到 .venv。请先运行 .\scripts\setup.ps1 -Dev。'
}
Push-Location $projectRoot
try {
    & $pythonExe -m ruff format --check .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $pythonExe -m ruff check .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $pythonExe -m mypy src
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $arguments = @('-m', 'pytest', '--cov')
    if ($Integration) { $arguments += '-m'; $arguments += 'integration' }
    & $pythonExe @arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
