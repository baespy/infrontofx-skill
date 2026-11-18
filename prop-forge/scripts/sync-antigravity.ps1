param(
    [switch]$Check,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$source = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).ProviderPath
$claudeDir = Split-Path $source -Parent
while ($claudeDir -and (Split-Path $claudeDir -Leaf) -ne '.claude') {
    $claudeDir = Split-Path $claudeDir -Parent
}
if (-not $claudeDir -or $source.Substring($claudeDir.Length + 1) -notmatch '^skills\\') {
    throw "run this from the .claude/skills copy; $source is not the source of truth"
}
$workspace = Split-Path $claudeDir -Parent
$skillName = Split-Path $source -Leaf
$target = Join-Path $workspace (Join-Path '.agents\skills' $skillName)

function Listing([string]$root) {
    $map = @{}
    if (Test-Path -LiteralPath $root) {
        foreach ($f in Get-ChildItem -LiteralPath $root -Recurse -File -Force) {
            $rel = $f.FullName.Substring($root.Length + 1)
            if ($rel -match '(^|\\)__pycache__(\\|$)') { continue }
            $map[$rel] = $f
        }
    }
    $map
}

$src = Listing $source
$dst = Listing $target

$copy = New-Object Collections.Generic.List[string]
$newerInTarget = New-Object Collections.Generic.List[string]
foreach ($rel in $src.Keys) {
    if (-not $dst.ContainsKey($rel)) { $copy.Add($rel); continue }
    if ($src[$rel].Length -eq $dst[$rel].Length -and (Get-FileHash -LiteralPath $src[$rel].FullName).Hash -eq (Get-FileHash -LiteralPath $dst[$rel].FullName).Hash) { continue }
    if ($dst[$rel].LastWriteTimeUtc -gt $src[$rel].LastWriteTimeUtc) { $newerInTarget.Add($rel) }
    $copy.Add($rel)
}
$remove = @($dst.Keys | Where-Object { -not $src.ContainsKey($_) })

Write-Output ("source files {0}, to copy {1}, to remove {2}, edited in target {3}" -f $src.Count, $copy.Count, $remove.Count, $newerInTarget.Count)
foreach ($r in $newerInTarget) { Write-Output "  newer in .agents copy: $r" }
foreach ($r in $remove) { Write-Output "  only in .agents copy: $r" }
if ($Check) { if ($copy.Count -or $remove.Count) { exit 1 } else { exit 0 } }

if (($newerInTarget.Count -or $remove.Count) -and -not $Force) {
    throw "the .agents copy has edits that a sync would lose; move them into .claude/skills/infrontofx/$skillName first, or pass -Force"
}

foreach ($rel in $copy) {
    $to = Join-Path $target $rel
    New-Item -ItemType Directory -Force -Path (Split-Path $to -Parent) | Out-Null
    [IO.File]::Copy($src[$rel].FullName, $to, $true)
}
foreach ($rel in $remove) { Remove-Item -LiteralPath (Join-Path $target $rel) -Force }
Write-Output "synced to $target"
