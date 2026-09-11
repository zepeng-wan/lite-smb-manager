[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    $files = rg --files -g '!.venv/**' -g '!build/**' -g '!dist/**' -g '!.git/**'
    $findings = $files | Select-String -Pattern 'SMB_TEST_PASSWORD\s*=\s*[^\s"'']+', 'password\s*=\s*["''][^"'']{12,}' -CaseSensitive:$false
    if ($findings) {
        $findings | ForEach-Object { Write-Error "疑似敏感信息：$($_.Path):$($_.LineNumber)" }
        exit 1
    }
    Write-Host '未发现疑似硬编码 SMB 密码。'
}
finally {
    Pop-Location
}
