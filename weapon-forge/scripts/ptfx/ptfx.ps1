[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('inspect', 'census', 'decompile', 'build', 'roundtrip', 'defaults', 'ranges', 'lint', 'stats', 'sprites', 'recipes', 'preview', 'textures', 'new', 'themes')]
    [string]$Mode,
    [string]$Path,
    [string]$Name,
    [string]$Theme,
    [string]$Colors,
    [string]$Spec,
    [string]$Out,
    [string[]]$Roots,
    [string]$Defaults,
    [switch]$Full,
    [switch]$AllowDerived,
    [string]$DumpSpec,
    [string]$Core,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'ptfx-lib.ps1')
Import-PtfxLib

if (-not $Defaults) { $Defaults = Join-Path $PSScriptRoot 'ptfx-defaults.json' }
$RangesPath = Join-Path $PSScriptRoot 'ptfx-ranges.json'

# The preview draws the game's own sheets when it can read a core.ypt. Looked up once, then remembered.
function Find-GameCore {
    if ($Core) { return (Resolve-Path -LiteralPath $Core).ProviderPath }
    $memo = Join-Path $env:TEMP 'weapon-forge-ptfx\core-path.txt'
    if (Test-Path -LiteralPath $memo) {
        $p = (Get-Content -LiteralPath $memo -TotalCount 1)
        if ($p -eq '-' ) { return $null }
        if ($p -and (Test-Path -LiteralPath $p)) { return $p }
    }
    $root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))))
    $hit = $null
    if ($root -and (Test-Path -LiteralPath $root)) {
        $hit = Get-ChildItem -LiteralPath $root -Recurse -File -Filter 'core.ypt' -ErrorAction SilentlyContinue | Where-Object { -not (Test-Escrowed $_.FullName) } | Sort-Object Length -Descending | Select-Object -First 1
    }
    $dir = Split-Path -Parent $memo
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
    Set-Content -LiteralPath $memo -Value $(if ($hit) { $hit.FullName } else { '-' }) -Encoding utf8
    if ($hit) { return $hit.FullName }
    return $null
}
if ($Mode -in @('build', 'preview')) { [WeaponForge.PtfxPreview]::GameCorePath = Find-GameCore }

function Get-Defaults {
    if (Test-Path -LiteralPath $Defaults) { return [WeaponForge.Defaults]::Load($Defaults) }
    return $null
}

function Get-YptFiles([string[]]$roots) {
    $seen = @{}
    foreach ($r in $roots) {
        foreach ($f in Get-ChildItem -LiteralPath $r -Recurse -File -Filter '*.ypt') {
            if (Test-Escrowed $f.FullName) { continue }
            $sig = '{0}|{1}' -f $f.Name.ToLowerInvariant(), $f.Length
            if ($seen.ContainsKey($sig)) { continue }
            $seen[$sig] = $true
            $f
        }
    }
}

switch ($Mode) {
    'census' {
        $files = if ($Path) { @(Get-Item -LiteralPath $Path) } else { @(Get-YptFiles $Roots) }
        $tally = @{ clean = 0; orphans = 0; models = 0; issues = 0; failed = 0 }
        foreach ($f in $files) {
            try {
                $y = [WeaponForge.YptFile]::Parse($f.FullName)
                $st = $y.Status()
                $tally[$st]++
                if ($st -eq 'issues' -or -not $Quiet) {
                    '{0,-7} {1}' -f $st.ToUpper(), $f.FullName
                    if ($st -ne 'clean') { ($y.Census() -split "`n" | Where-Object { $_ } | Select-Object -First 6) | ForEach-Object { '        ' + $_.Trim() } }
                }
            } catch {
                $tally.failed++
                'FAILED  {0}  {1}' -f $f.FullName, $_.Exception.Message
            }
        }
        "RESULT files=$($files.Count) clean=$($tally.clean) orphanData=$($tally.orphans) withModels=$($tally.models) issues=$($tally.issues) failed=$($tally.failed)"
    }
    'inspect' {
        $y = [WeaponForge.YptFile]::Parse((Resolve-Path -LiteralPath $Path).ProviderPath)
        $text = [WeaponForge.YptInspect]::Describe($y)
        if ($Out) { [IO.File]::WriteAllText($Out, $text, (New-Object Text.UTF8Encoding($false))); "wrote $Out" } else { $text }
    }
    'decompile' {
        $y = [WeaponForge.YptFile]::Parse((Resolve-Path -LiteralPath $Path).ProviderPath)
        $d = [WeaponForge.Decompiler]::new($y, [WeaponForge.Defaults]$(if ($Full) { $null } else { Get-Defaults }))
        $d.Full = [bool]$Full
        $json = [WeaponForge.Json]::Write($d.Run(), $true)
        if ($Out) { [IO.File]::WriteAllText($Out, $json, (New-Object Text.UTF8Encoding($false))); "wrote $Out ($($json.Length) chars)" } else { $json }
    }
    'roundtrip' {
        $files = if ($Path) { @(Get-Item -LiteralPath $Path) } else { @(Get-YptFiles $Roots) }
        $defs = Get-Defaults
        $tmp = Join-Path $env:TEMP ('ptfx-rt-' + [Guid]::NewGuid().ToString('N') + '.ypt')
        $pass = 0; $fail = 0; $skip = 0
        foreach ($f in $files) {
            try {
                $a = [WeaponForge.YptFile]::Parse($f.FullName)
                if ($a.HasOpaque) { $skip++; continue }
                $tree = ([WeaponForge.Decompiler]::new($a, [WeaponForge.Defaults]$defs)).Run()
                $text = [WeaponForge.Json]::Write($tree, $false)
                $c = [WeaponForge.Compiler]::new([WeaponForge.Defaults]$defs)
                $parsed = [WeaponForge.Json]::Parse($text)
                $root = $c.Run($parsed)
                [WeaponForge.YptWriter]::Build($root).Save($tmp)
                $b = [WeaponForge.YptFile]::Parse($tmp)
                $diff = [WeaponForge.YptCheck]::Compare($a, $b)
                $clean = ($b.Status() -eq 'clean')
                if ($diff -eq '' -and $clean -and $c.Warnings.Count -eq 0) { $pass++; if (-not $Quiet) { "PASS  $($f.FullName)" } }
                else {
                    $fail++
                    "DIFF  $($f.FullName)  $diff"
                    if (-not $clean) { ($b.Census() -split "`n" | Where-Object { $_ } | Select-Object -First 4) | ForEach-Object { '      ' + $_.Trim() } }
                    $c.Warnings | Select-Object -First 4 | ForEach-Object { "      WARN $_" }
                }
            } catch {
                $fail++
                "FAIL  $($f.FullName)  $($_.Exception.Message)"
            }
        }
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        "RESULT files=$($files.Count) pass=$pass fail=$fail skippedModels=$skip"
    }
    'stats' {
        $st = New-Object WeaponForge.YptStats
        foreach ($f in @(Get-YptFiles $Roots)) {
            try {
                $y = [WeaponForge.YptFile]::Parse($f.FullName)
                if ($y.Status() -eq 'issues') { continue }
                $rel = $f.FullName
                foreach ($r in $Roots) { if ($rel.StartsWith($r, [StringComparison]::OrdinalIgnoreCase)) { $rel = $rel.Substring((Split-Path -Parent $r).Length + 1) } }
                $st.Add($y, $rel)
            } catch { }
        }
        $text = $st.Report(8) + "`n## Files`n" + ($st.FileLines -join "`n")
        if ($Out) { [IO.File]::WriteAllText($Out, $text, (New-Object Text.UTF8Encoding($false))); "wrote $Out" } else { $text }
    }
    'sprites' {
        $names = @(); $gens = @()
        if ($Spec) {
            $design = [WeaponForge.Json]::Parse([IO.File]::ReadAllText((Resolve-Path -LiteralPath $Spec).ProviderPath))
            foreach ($t in $design.Arr('textures')) { if ($t.Obj('gen')) { $names += $t.Str('name'); $gens += $t.Obj('gen') } }
        } else {
            foreach ($s in [WeaponForge.SpriteGen]::Shapes) {
                if ($s -eq 'image') { continue }
                $g = New-Object WeaponForge.JObj
                $g.Add('shape', $s); $g.Add('size', [double]128)
                if ($s -eq 'glyph') { $g.Add('text', [string][char]0x2660) }
                $names += $s; $gens += $g
            }
        }
        if (-not $Out) { $Out = Join-Path $env:TEMP 'ptfx-sprites.png' }
        $n = [WeaponForge.SpriteGen]::RenderSheet([string[]]$names, [WeaponForge.JObj[]]$gens, $Out, 128)
        "wrote $Out ($n sprites)"
    }
    'build' {
        if (-not $Spec) { throw 'build needs -Spec <design.json> and -Out <folder or dict.ypt>' }
        if (-not $Out) { $Out = Split-Path -Parent (Resolve-Path -LiteralPath $Spec).ProviderPath }
        $dump = if ($DumpSpec) { $DumpSpec } else { $null }
        [WeaponForge.PtfxBuild]::RangesPath = $RangesPath
        ([WeaponForge.PtfxBuild]::Build((Resolve-Path -LiteralPath $Spec).ProviderPath, $Defaults, (Join-Path $PSScriptRoot 'ptfx-archetypes.json'), $Out, [bool]$AllowDerived, $dump)) -split "`r?`n" | Where-Object { $_ }
    }
    'textures' {
        if (-not $Path) { throw 'textures needs -Path <file.ypt> and optionally -Out <folder> -Name <texture>' }
        $src = (Resolve-Path -LiteralPath $Path).ProviderPath
        if (Test-Escrowed $src) { throw 'this resource is escrowed (.fxap); its files are not for study' }
        if (-not $Out) { $Out = Join-Path $env:TEMP ('ptfx-tex-' + [IO.Path]::GetFileNameWithoutExtension($src)) }
        $y = [WeaponForge.YptFile]::Parse($src)
        ([WeaponForge.TexDecode]::Export($y, $Out, $(if ($Name) { $Name } else { $null }))) -split "`r?`n" | Where-Object { $_ }
    }
    'lint' {
        if (-not $Path) { throw 'lint needs -Path <file.ypt>' }
        $r = [WeaponForge.Ranges]::Load($RangesPath)
        if (-not $r) { throw "ptfx-ranges.json is missing; run: ptfx.ps1 ranges -Roots <folders with real .ypt files>" }
        $res = [WeaponForge.Linter]::CheckFile((Resolve-Path -LiteralPath $Path).ProviderPath, $r)
        $res.Errors | ForEach-Object { "ERROR $_" }
        $res.Warnings | ForEach-Object { "WARN  $_" }
        if (-not $Quiet) { $res.Notes | ForEach-Object { "NOTE  $_" } }
        $res.Summary()
    }
    'ranges' {
        $b = New-Object WeaponForge.RangeBuilder
        foreach ($f in @(Get-YptFiles $Roots)) {
            try {
                $y = [WeaponForge.YptFile]::Parse($f.FullName)
                if ($y.Status() -eq 'issues') { continue }
                $b.Add($y, ($f.Name -ieq 'core.ypt'))
            } catch { }
        }
        $target = if ($Out) { $Out } else { $RangesPath }
        [IO.File]::WriteAllText($target, $b.Finish(), (New-Object Text.UTF8Encoding($false)))
        "wrote $target from $($b.Files) files"
    }
    'preview' {
        $src = if ($Spec) { $Spec } else { $Path }
        if (-not $src) { throw 'preview needs -Spec <design.json> or -Path <file.ypt>' }
        $src = (Resolve-Path -LiteralPath $src).ProviderPath
        if (-not $Out) { $Out = [IO.Path]::ChangeExtension($src, $null) + '.preview.png' }
        ([WeaponForge.PtfxBuild]::Preview($src, $Defaults, (Join-Path $PSScriptRoot 'ptfx-archetypes.json'), $Out)) -split "`r?`n" | Where-Object { $_ }
    }
    'themes' {
        [WeaponForge.PtfxBuild]::Themes((Join-Path $PSScriptRoot 'ptfx-themes.json'))
    }
    'new' {
        if (-not $Theme -or -not $Name) { throw 'new needs -Theme <theme> -Name <set id>; run ptfx.ps1 themes for the list' }
        if (-not $Out) { $Out = (Get-Location).Path }
        ([WeaponForge.PtfxBuild]::NewFromTheme((Join-Path $PSScriptRoot 'ptfx-themes.json'), $Theme, $Name, $Colors, $Out)) -split "`r?`n" | Where-Object { $_ }
    }
    'recipes' {
        [WeaponForge.PtfxBuild]::Recipes((Join-Path $PSScriptRoot 'ptfx-archetypes.json'))
    }
    'defaults' {
        $b = New-Object WeaponForge.DefaultsBuilder
        foreach ($f in @(Get-YptFiles $Roots)) {
            try {
                $y = [WeaponForge.YptFile]::Parse($f.FullName)
                if (-not $y.Clean() -and -not $y.HasOpaque) { continue }
                $b.Add($y)
            } catch { }
        }
        $target = if ($Out) { $Out } else { $Defaults }
        [IO.File]::WriteAllText($target, $b.Finish(), (New-Object Text.UTF8Encoding($false)))
        "wrote $target from $($b.Files) files"
    }
}
