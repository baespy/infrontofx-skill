param(
    [ValidateSet('antigravity', 'codex', 'all')]
    [string]$Tool = 'all',
    [switch]$Check,
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'

$pack = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).ProviderPath
$manifest = Get-Content -Raw -LiteralPath (Join-Path $pack '.claude-plugin\plugin.json') | ConvertFrom-Json
$subSkills = @($manifest.skills | ForEach-Object { ($_ -replace '^\./', '').Trim('/') } | Where-Object { $_ })
$skipDirs = @('.git', '.github', '.cursor', '__pycache__', 'node_modules')
$utf8 = New-Object Text.UTF8Encoding $false
$homeDir = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
$onWindows = $env:OS -eq 'Windows_NT'
$status = 0

function Get-PackFiles([string]$root) {
    $map = @{}
    if (-not (Test-Path -LiteralPath $root)) { return $map }
    $root = (Get-Item -LiteralPath $root -Force).FullName
    foreach ($f in Get-ChildItem -LiteralPath $root -Recurse -File -Force) {
        $rel = $f.FullName.Substring($root.Length).TrimStart('\', '/')
        $parts = $rel -split '[\\/]'
        if (@($parts | Where-Object { $skipDirs -contains $_ }).Count -gt 0) { continue }
        $map[$rel] = $f.FullName
    }
    $map
}

function Copy-Tree([string]$from, [string]$to) {
    $files = Get-PackFiles $from
    foreach ($rel in $files.Keys) {
        $dest = Join-Path $to $rel
        New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
        [IO.File]::Copy($files[$rel], $dest, $true)
    }
}

function Find-Bash {
    if (-not $onWindows) { return 'bash' }
    $candidates = New-Object Collections.Generic.List[string]
    $onPath = Get-Command bash -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch '\\System32\\' } | Select-Object -First 1
    if ($onPath) { $candidates.Add($onPath.Source) }
    $git = Get-Command git -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($git) { $candidates.Add((Join-Path (Split-Path (Split-Path $git.Source -Parent) -Parent) 'bin\bash.exe')) }
    $candidates.Add((Join-Path $env:ProgramFiles 'Git\bin\bash.exe'))
    $candidates.Add((Join-Path $env:LOCALAPPDATA 'Programs\Git\bin\bash.exe'))
    $found = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
    if (-not $found) { throw 'Git Bash not found; install Git for Windows' }
    if ($found -match ' ') {
        $short = (New-Object -ComObject Scripting.FileSystemObject).GetFile($found).ShortPath
        if ($short -match ' ') { throw "Git Bash path has spaces and no short name: $found" }
        return $short
    }
    $found
}

function Build-Stage([string]$name, [string]$stage) {
    if ($name -eq 'antigravity') {
        Copy-Tree $pack (Join-Path $stage 'skills\infrontofx')
        foreach ($sub in $subSkills) {
            Copy-Tree (Join-Path $pack $sub) (Join-Path $stage "skills\$sub")
        }
        $plugin = [ordered]@{
            name        = 'infrontofx-skill'
            description = $manifest.description
            version     = $manifest.version
            repository  = 'https://github.com/baespy/infrontofx-skill'
        }
        [IO.File]::WriteAllText((Join-Path $stage 'plugin.json'), ($plugin | ConvertTo-Json), $utf8)
        $command = (Find-Bash) + ' ./skills/infrontofx/hooks/skill-router.sh'
        $hooks = '{"infrontofx-skill-router":{"PreInvocation":[{"type":"command","command":' + (ConvertTo-Json $command) + ',"timeout":5}]}}'
        [IO.File]::WriteAllText((Join-Path $stage 'hooks.json'), $hooks, $utf8)
    }
    else {
        Copy-Tree $pack $stage
    }
}

function Get-Target([string]$name) {
    if ($name -eq 'antigravity') { return Join-Path $homeDir '.gemini\config\plugins\infrontofx-skill' }
    $codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $homeDir '.codex' }
    Join-Path $codexHome 'skills\infrontofx'
}

function Move-OldCodexCopies([string]$target) {
    $skillsDir = Split-Path $target -Parent
    if (-not (Test-Path -LiteralPath $skillsDir)) { return 0 }
    $ours = @('infrontofx') + $subSkills
    $moved = 0
    $backup = Join-Path (Split-Path $skillsDir -Parent) ('skills-backup\infrontofx-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    foreach ($dir in Get-ChildItem -LiteralPath $skillsDir -Directory -Force) {
        if ($dir.Name -eq (Split-Path $target -Leaf) -or $dir.Name.StartsWith('.')) { continue }
        $skillFile = Join-Path $dir.FullName 'SKILL.md'
        if (-not (Test-Path -LiteralPath $skillFile)) { continue }
        $head = (Get-Content -LiteralPath $skillFile -TotalCount 5) -join "`n"
        $named = [regex]::Match($head, '(?m)^name:\s*(\S+)')
        if ($named.Success -and $ours -contains $named.Groups[1].Value) {
            New-Item -ItemType Directory -Force -Path $backup | Out-Null
            Move-Item -LiteralPath $dir.FullName -Destination (Join-Path $backup $dir.Name)
            $moved++
        }
    }
    if ($moved) { Write-Output "  moved $moved old copies to $backup" }
}

function Compare-Trees([string]$a, [string]$b) {
    $left = Get-PackFiles $a
    $right = Get-PackFiles $b
    $diff = 0
    foreach ($rel in $left.Keys) {
        if (-not $right.ContainsKey($rel)) { $diff++; continue }
        if ((Get-FileHash -LiteralPath $left[$rel]).Hash -ne (Get-FileHash -LiteralPath $right[$rel]).Hash) { $diff++ }
    }
    foreach ($rel in $right.Keys) { if (-not $left.ContainsKey($rel)) { $diff++ } }
    $diff
}

function Invoke-Validate([string]$target) {
    $agy = Get-Command agy -ErrorAction SilentlyContinue | Select-Object -First 1
    $agyPath = if ($agy) { $agy.Source } else { Join-Path $homeDir '.gemini\bin\agy.exe' }
    if (-not (Test-Path -LiteralPath $agyPath)) { return }
    $report = & $agyPath plugin validate $target 2>&1 | Out-String
    $counts = [regex]::Match($report, 'skills \d+.*')
    $verdict = if ($LASTEXITCODE -eq 0) { 'ok' } else { 'FAILED' }
    Write-Output ("  agy plugin validate: {0} {1}" -f $verdict, $counts.Value.Trim())
    if ($LASTEXITCODE -ne 0) { Write-Output $report; $script:status = 1 }
}

$tools = if ($Tool -eq 'all') { @('antigravity', 'codex') } else { @($Tool) }
foreach ($name in $tools) {
    $target = Get-Target $name
    if ($Uninstall) {
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
            Write-Output "${name}: removed $target"
        }
        else {
            Write-Output "${name}: not installed"
        }
        continue
    }
    $stage = Join-Path ([IO.Path]::GetTempPath()) ("infrontofx-$name-" + [guid]::NewGuid().ToString('N'))
    try {
        Build-Stage $name $stage
        $diff = Compare-Trees $stage $target
        if ($Check) {
            if ($diff -gt 0) {
                Write-Output "${name}: stale or missing ($diff files differ) at $target"
                $status = 1
            }
            else {
                Write-Output "${name}: up to date at $target"
            }
            continue
        }
        if ($diff -eq 0) {
            Write-Output "${name}: already up to date at $target"
        }
        else {
            if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
            New-Item -ItemType Directory -Force -Path (Split-Path $target -Parent) | Out-Null
            Move-Item -LiteralPath $stage -Destination $target
            $count = if ($name -eq 'antigravity') { "$($subSkills.Count + 1) skills and the routing hook" } else { 'the pack as one skill folder' }
            Write-Output "${name}: installed v$($manifest.version) ($count) at $target"
        }
        if ($name -eq 'codex') { Move-OldCodexCopies $target }
        if ($name -eq 'antigravity') { Invoke-Validate $target }
    }
    finally {
        if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
    }
}
exit $status
