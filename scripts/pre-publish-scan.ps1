[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    if (Get-Command rg -ErrorAction SilentlyContinue) {
        $files = rg --files --hidden -g '!.git/**' -g '!发布要求.md'
    }
    else {
        $files = Get-ChildItem -LiteralPath $projectRoot -Recurse -Force -File -ErrorAction SilentlyContinue |
            Where-Object {
                $_.FullName -notmatch '[\\/]\.git[\\/]' -and $_.Name -ne '发布要求.md'
            } |
            ForEach-Object FullName
    }
    $patterns = @(
        '(?i)github_pat_[a-z0-9_]{20,}',
        '(?i)gh[pousr]_[a-z0-9_]{20,}',
        '(?i)AKIA[0-9A-Z]{16}',
        '(?i)-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
        '\\\\(?:10\.|172\.(?:1[6-9]|2[0-9]|3[0-1])\.|192\.168\.)',
        '(?i)C:\\Users\\',
        '(?i)C:\\my_folder\\'
    )
    $findings = $files | Select-String -Pattern $patterns
    if ($findings) {
        $findings | ForEach-Object { Write-Error "疑似公开敏感信息：$($_.Path):$($_.LineNumber)" }
        exit 1
    }
    $history = git rev-parse --verify HEAD 2>$null
    if ($LASTEXITCODE -eq 0 -and $history) {
        $historyFindings = git log --all -p --no-ext-diff | Select-String -Pattern $patterns
        if ($historyFindings) {
            $historyFindings | ForEach-Object { Write-Error "Git 历史疑似敏感信息：$($_.LineNumber)" }
            exit 1
        }
    }
    $global:LASTEXITCODE = 0
    Write-Host '发布前敏感信息与 Git 历史扫描通过。'
}
finally {
    Pop-Location
}
