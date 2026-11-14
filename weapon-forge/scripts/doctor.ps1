param(
    [string]$Workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..\..')).ProviderPath,
    [string]$ServerRoot = ''
)

$ErrorActionPreference = 'Continue'
if (-not $ServerRoot) {
    $ServerRoot = Join-Path $Workspace '[1nfx]'
    if (-not (Test-Path -LiteralPath (Join-Path $ServerRoot '[weapon]'))) {
        $found = @(Get-ChildItem -LiteralPath $Workspace -Directory -Force -ErrorAction SilentlyContinue | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName '[weapon]') } | Select-Object -First 1)
        if ($found) { $ServerRoot = $found[0].FullName }
    }
}

function Row([string]$state, [string]$name, [string]$detail) { Write-Output ('{0,-8} {1,-26} {2}' -f $state, $name, $detail) }
function Exe([string]$name) { $c = Get-Command $name -ErrorAction SilentlyContinue | Where-Object { $_.Length -ne 0 -or $_.CommandType -ne 'Application' } | Select-Object -First 1; if ($c -and $c.Source -notmatch 'WindowsApps') { $c.Source } else { '' } }

$blender = 'C:\Tools\blender-4.2.3-windows-x64\blender.exe'
if (-not (Test-Path -LiteralPath $blender)) {
    $alt = @(foreach ($r in 'C:\Tools', 'C:\Program Files\Blender Foundation') { Get-ChildItem -LiteralPath $r -Recurse -File -Depth 2 -Filter 'blender.exe' -ErrorAction SilentlyContinue | Select-Object -First 1 })
    if ($alt) { $blender = $alt[0].FullName }
}
if (Test-Path -LiteralPath $blender) { Row 'READY' 'Blender' $blender } else { Row 'MISSING' 'Blender' 'forge, import, validate and export scripts need it' }

$extRoot = Join-Path $env:APPDATA 'Blender Foundation\Blender'
$sollumz = @(Get-ChildItem -LiteralPath $extRoot -Recurse -Directory -Force -Depth 5 -ErrorAction SilentlyContinue | Where-Object { $_.Name -ieq 'sollumz' } | Select-Object -First 1)
if ($sollumz) { Row 'READY' 'Sollumz' $sollumz[0].FullName } else { Row 'MISSING' 'Sollumz' 'official .ydr route; ask the user before installing' }
$materia = @(Get-ChildItem -LiteralPath $extRoot -Recurse -Directory -Force -Depth 8 -ErrorAction SilentlyContinue | Where-Object { $_.Name -ieq 'pymateria' } | Select-Object -First 1)
if ($materia) { Row 'READY' 'PyMateria' 'binary .ydr export and import' } else { Row 'MISSING' 'PyMateria' 'without it Sollumz writes CW XML only; user accepts the Cfx licence in Sollumz preferences' }

$cw = @(foreach ($r in 'C:\Tools', (Join-Path $env:USERPROFILE 'Downloads'), (Join-Path $env:USERPROFILE 'Desktop')) { Get-ChildItem -LiteralPath $r -Recurse -File -Force -Depth 3 -Filter 'CodeWalker.exe' -ErrorAction SilentlyContinue | Select-Object -First 1 })
if ($cw) { Row 'READY' 'CodeWalker' $cw[0].FullName } else { Row 'MISSING' 'CodeWalker' 'needed only for .ypt XML editing and CW XML import' }

$tex = Exe 'texconv'
if ($tex) { Row 'READY' 'texconv' $tex } else { Row 'OPTIONAL' 'texconv' 'export_ydr.py can write DDS without it' }

$agy = Join-Path $env:USERPROFILE '.gemini\bin\agy.exe'
if (Test-Path -LiteralPath $agy) { Row 'READY' 'Antigravity CLI' ((& $agy --version) -join ' ') } else { Row 'MISSING' 'Antigravity CLI' $agy }

$mirror = Join-Path $Workspace '.agents\skills\weapon-forge\SKILL.md'
if (Test-Path -LiteralPath $mirror) { Row 'READY' 'Skill for Antigravity' '.agents/skills/weapon-forge' } else { Row 'MISSING' 'Skill for Antigravity' 'run scripts/sync-antigravity.ps1' }

$uv = Exe 'uvx'
if ($uv) { Row 'READY' 'uvx' $uv } else { Row 'MISSING' 'uvx' 'needed for mcp-for-blender; ask the user before installing' }

$cfg = Join-Path $env:USERPROFILE '.gemini\config\mcp_config.json'
$hasBlender = $false
if (Test-Path -LiteralPath $cfg) {
    try {
        $j = Get-Content -LiteralPath $cfg -Raw | ConvertFrom-Json
        if ($j.mcpServers) { $hasBlender = @($j.mcpServers.PSObject.Properties.Name | Where-Object { $_ -match 'blender' }).Count -gt 0 }
    } catch { Row 'WARN' 'mcp_config.json' 'cannot be parsed' }
}
if ($hasBlender) { Row 'READY' 'Antigravity Blender MCP' $cfg } else { Row 'MISSING' 'Antigravity Blender MCP' 'see references/antigravity.md' }

try {
    . (Join-Path $PSScriptRoot 'ptfx\ptfx-lib.ps1')
    Import-PtfxLib
    $defs = Join-Path $PSScriptRoot 'ptfx\ptfx-defaults.json'
    if (Test-Path -LiteralPath $defs) { Row 'READY' 'Particle toolchain' 'ptfx.ps1 themes, new, build, preview, lint, inspect, textures (needs nothing installed)' }
    else { Row 'MISSING' 'Particle defaults' 'run ptfx.ps1 defaults -Roots <folders with .ypt> once' }
    if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'ptfx\ptfx-ranges.json')) { Row 'READY' 'Particle lint data' 'every build is compared with real files' }
    else { Row 'MISSING' 'Particle lint data' 'run ptfx.ps1 ranges -Roots <folders with .ypt> once; until then builds are not checked against real files' }
    foreach ($data in 'ptfx-archetypes.json', 'ptfx-sheets.json', 'ptfx-themes.json') {
        if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot "ptfx\$data"))) { Row 'MISSING' "Particle $data" 'restore it from the skill source' }
    }
    $coreMemo = Join-Path $env:TEMP 'weapon-forge-ptfx\core-path.txt'
    $corePath = if (Test-Path -LiteralPath $coreMemo) { Get-Content -LiteralPath $coreMemo -TotalCount 1 } else { $null }
    if ($corePath -and $corePath -ne '-' -and (Test-Path -LiteralPath $corePath)) { Row 'READY' 'Game core.ypt for previews' $corePath }
    else { Row 'INFO' 'Game core.ypt for previews' 'not located yet; the first build searches the workspace, or pass -Core. Without it previews draw stand-ins for game textures' }
} catch { Row 'MISSING' 'Particle toolchain' ('C# sources failed to compile: ' + $_.Exception.Message) }
$ErrorActionPreference = 'Continue'

$weapon = Join-Path $ServerRoot '[weapon]'
if (Test-Path -LiteralPath $weapon) { Row 'READY' '[weapon]' $weapon } else { Row 'MISSING' '[weapon]' $weapon }
foreach ($n in '1nfx_weaponskin', 'es_extended', '1nfx_inventory', '1nfx_assetsimg') {
    $p = Join-Path $ServerRoot $n
    if (Test-Path -LiteralPath $p) { Row 'READY' $n $p } else { Row 'MISSING' $n 'integration steps 5-11 and check-skin.ps1 need it; pass -ServerRoot' }
}
