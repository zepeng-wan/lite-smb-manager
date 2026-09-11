[CmdletBinding()]
param(
    [string]$Version
)

$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'package.ps1') -Version $Version
exit $LASTEXITCODE
