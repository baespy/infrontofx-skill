param(
    [string]$Project,
    [switch]$SkipGlobal
)

$ErrorActionPreference = "Stop"
$source = Split-Path -Parent $MyInvocation.MyCommand.Path
$name = "infrontofx-skill"
$exclude = @(".git", ".github", "node_modules")

function Install-SkillCopy([string]$targetRoot) {
    $target = Join-Path $targetRoot $name
    if (Test-Path $target) {
        Remove-Item -Path $target -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    Get-ChildItem -Path $source -Force | Where-Object { $exclude -notcontains $_.Name } | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $target -Recurse -Force
    }
    Write-Host "[OK] $target" -ForegroundColor Green
}

Write-Host "Installing $name for Antigravity, Claude Code, and OpenAI Codex" -ForegroundColor Cyan

if (-not $SkipGlobal) {
    $userHome = [Environment]::GetFolderPath("UserProfile")
    Install-SkillCopy (Join-Path $userHome ".gemini\config\skills")
    Install-SkillCopy (Join-Path $userHome ".gemini\antigravity\skills")
    Install-SkillCopy (Join-Path $userHome ".claude\skills")
    Install-SkillCopy (Join-Path $userHome ".codex\skills")
}

if ($Project) {
    $agents = Join-Path $Project ".agents"
    Install-SkillCopy (Join-Path $agents "skills")
    $claude = Join-Path $Project ".claude"
    Install-SkillCopy (Join-Path $claude "skills")
    Copy-Item -Path (Join-Path $source "AGENTS.md") -Destination (Join-Path $Project "AGENTS.md") -Force
    Write-Host "[OK] $(Join-Path $Project 'AGENTS.md')" -ForegroundColor Green
    Copy-Item -Path (Join-Path $source "CLAUDE.md") -Destination (Join-Path $Project "CLAUDE.md") -Force
    Write-Host "[OK] $(Join-Path $Project 'CLAUDE.md')" -ForegroundColor Green
}

Write-Host "Done. Skill installed for Antigravity, Claude Code, and Codex." -ForegroundColor Yellow
