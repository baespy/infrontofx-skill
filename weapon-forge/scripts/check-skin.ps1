param(
    [Parameter(Mandatory = $true)][string]$SkinType,
    [string]$Root = ""
)

if (-not $Root) {
    $cur = Split-Path $PSScriptRoot -Parent
    while ($cur -and (Split-Path $cur -Leaf) -notin @('.claude', '.agents')) {
        $cur = Split-Path $cur -Parent
    }
    $ws = if ($cur) { Split-Path $cur -Parent } else { (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..\..')).ProviderPath }
    foreach ($cand in @(
        (Join-Path $ws 'resources\[resources]'),
        (Join-Path $ws 'resources'),
        (Join-Path $ws '[1nfx]')
    )) {
        if (Test-Path -LiteralPath $cand) { $Root = $cand; break }
    }
    if (-not $Root) { $Root = Join-Path $ws '[1nfx]' }
} else {
    $Root = (Resolve-Path -LiteralPath $Root).ProviderPath
}

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression

function FirstExisting([string[]]$paths) {
    foreach ($p in $paths) {
        if ($p -and (Test-Path -LiteralPath $p)) { return $p }
    }
    return ''
}

$rootParent = Split-Path $Root -Parent
$rootGrand = if ($rootParent) { Split-Path $rootParent -Parent } else { '' }

$skinRes = FirstExisting @(
    (Join-Path $Root '1nfx_weaponskin'),
    (Join-Path $Root '[1nfx]\1nfx_weaponskin'),
    (Join-Path $Root '[resources]\[1nfx]\1nfx_weaponskin'),
    $(if ($rootParent) { Join-Path $rootParent '[1nfx]\1nfx_weaponskin' } else { '' })
)
$weaponRes = FirstExisting @(
    $(if (Test-Path -LiteralPath (Join-Path $Root 'weapon_core')) { $Root } else { '' }),
    (Join-Path $Root '[weapon]'),
    (Join-Path $Root '[resources]\[weapon]'),
    $(if ($rootParent) { Join-Path $rootParent '[weapon]' } else { '' })
)
if (-not $weaponRes) { $weaponRes = Join-Path $Root '[weapon]' }
$dataDir = Join-Path $weaponRes 'weapon_core\data'
$script:fail = 0
$script:warn = 0

function Pass([string]$m) { Write-Output "PASS  $m" }
function Warn([string]$m) { $script:warn++; Write-Output "WARN  $m" }
function Fail([string]$m) { $script:fail++; Write-Output "FAIL  $m" }

function ReadText([string]$p) { [IO.File]::ReadAllText($p) }

if (-not (Test-Path -LiteralPath $weaponRes)) {
    Write-Output "BLOCKED  [weapon] not found under $Root"
    Write-Output 'RESULT blocked: pass -Root pointing at [1nfx], [weapon], or the resources folder'
    exit 2
}

$hasSkinRes = [bool]$skinRes
$itemsFile = FirstExisting @(
    (Join-Path $Root 'es_extended\items.json'),
    (Join-Path $Root '1nfx_core\items.json'),
    (Join-Path $Root '[core]\1nfx_core\items.json'),
    $(if ($rootParent) { Join-Path $rootParent '[core]\1nfx_core\items.json' } else { '' }),
    $(if ($rootGrand) { Join-Path $rootGrand '[core]\1nfx_core\items.json' } else { '' }),
    $(if ($rootParent) { Join-Path $rootParent 'es_extended\items.json' } else { '' })
)
$hasEsx = [bool]$itemsFile
$invFile = FirstExisting @(
    (Join-Path $Root '1nfx_inventory\config\config.item.lua'),
    (Join-Path $Root '[1nfx]\1nfx_inventory\config\config.item.lua'),
    (Join-Path $Root '[resources]\[1nfx]\1nfx_inventory\config\config.item.lua'),
    $(if ($rootParent) { Join-Path $rootParent '[1nfx]\1nfx_inventory\config\config.item.lua' } else { '' })
)
$hasInv = [bool]$invFile
$assetsImgDirResolved = FirstExisting @(
    (Join-Path $Root '1nfx_assetsimg\items'),
    (Join-Path $Root '[1nfx]\1nfx_assetsimg\items'),
    (Join-Path $Root '[resources]\[1nfx]\1nfx_assetsimg\items'),
    $(if ($rootParent) { Join-Path $rootParent '[1nfx]\1nfx_assetsimg\items' } else { '' })
)
$hasAssetsImg = [bool]$assetsImgDirResolved
$pkgDir = Get-ChildItem -LiteralPath $weaponRes -Directory | Where-Object { $_.Name -like 'weapon_*' } | Where-Object {
    if ($_.Name -ieq "weapon_$SkinType") { return $true }
    $p = Join-Path $_.FullName "patches"
    if (Test-Path -LiteralPath $p) {
        $f = Get-ChildItem -LiteralPath $p -File | Where-Object { $_.Name -like '*.skin.lua' -and ((ReadText $_.FullName) -match ('itemSkins\["(?i)' + [regex]::Escape($SkinType) + '"\]')) } | Select-Object -First 1
        return $null -ne $f
    }
    return $false
} | Select-Object -First 1

function Inflate([string]$p) {
    $b = [IO.File]::ReadAllBytes($p)
    if ([Text.Encoding]::ASCII.GetString($b, 0, 4) -ne 'RSC7') { return $null }
    $ms = New-Object IO.MemoryStream(, $b)
    $ms.Position = 16
    $d = New-Object IO.Compression.DeflateStream($ms, [IO.Compression.CompressionMode]::Decompress)
    $o = New-Object IO.MemoryStream
    $d.CopyTo($o)
    return , $o.ToArray()
}

$metaFor = @{
    Poolcue = 'weapons\weaponpoolcue.meta'; Bottle = 'weapons\weaponbottle.meta'; Knuckle = 'weapons\weaponknuckle.meta'
    Machete = 'weapons\weaponmachete.meta'; Revolver = 'weapons\weaponrevolver.meta'; Bat = 'weapons\weapons.meta'; Knife = 'weapons\weapons.meta'
}

$skinFile = $null
if ($hasSkinRes) {
    $skinFile = Get-ChildItem -LiteralPath (Join-Path $skinRes 'config\skins') -File | Where-Object { $_.Name -like '*.lua' -and ((ReadText $_.FullName) -match ('itemSkins\["(?i)' + [regex]::Escape($SkinType) + '"\]')) } | Select-Object -First 1
}
if (-not $skinFile -and $pkgDir -and (Test-Path -LiteralPath (Join-Path $pkgDir.FullName 'patches'))) {
    $skinFile = Get-ChildItem -LiteralPath (Join-Path $pkgDir.FullName 'patches') -File | Where-Object { $_.Name -like '*.skin.lua' } | Select-Object -First 1
}
if (-not $skinFile) { Fail "no config/skins/*.lua or patches/*.skin.lua defines itemSkins[`"$SkinType`"]"; Write-Output "RESULT fail=$script:fail warn=$script:warn"; exit 1 }
Pass "skin config $($skinFile.Name)"
$lua = ReadText $skinFile.FullName

$blockMatch = [regex]::Match($lua, 'itemSkins\["(?i)(' + [regex]::Escape($SkinType) + ')"\]\s*=\s*\{(.*?)\}', 'Singleline')
$SkinType = $blockMatch.Groups[1].Value
$block = $blockMatch.Groups[2].Value
$pairs = [regex]::Matches($block, '(\w+)\s*=\s*"([^"]+)"') | ForEach-Object { [pscustomobject]@{ Weapon = $_.Groups[1].Value; Item = $_.Groups[2].Value } }
if (-not $pairs) { Fail 'itemSkins block is empty' }

$componentsText = ReadText (Join-Path $dataDir 'weaponcomponents.meta')
$archetypesText = ReadText (Join-Path $dataDir 'weaponarchetypes.meta')
if ($pkgDir -and -not $componentsText.Contains("_" + $SkinType.ToUpper())) {
    Warn "weapon_core/data/weaponcomponents.meta does not yet contain $SkinType; falling back to patches/weaponcomponents.insert.xml"
    $patchComp = Join-Path $pkgDir.FullName 'patches\weaponcomponents.insert.xml'
    $patchArch = Join-Path $pkgDir.FullName 'patches\weaponarchetypes.insert.xml'
    if (Test-Path -LiteralPath $patchComp) { $componentsText += "`n" + (ReadText $patchComp) }
    if (Test-Path -LiteralPath $patchArch) { $archetypesText += "`n" + (ReadText $patchArch) }
}
$itemsText = if ($hasEsx) { ReadText $itemsFile } elseif ($pkgDir -and (Test-Path -LiteralPath (Join-Path $pkgDir.FullName 'patches\es_extended.items.insert.json'))) { ReadText (Join-Path $pkgDir.FullName 'patches\es_extended.items.insert.json') } else { "" }
$iconDir = if ($hasAssetsImg) { $assetsImgDirResolved } elseif ($pkgDir -and (Test-Path -LiteralPath (Join-Path $pkgDir.FullName 'assets\items'))) { Join-Path $pkgDir.FullName 'assets\items' } elseif ($pkgDir) { Join-Path $pkgDir.FullName 'source' } else { "" }
$inventoryText = if ($hasInv) { ReadText $invFile } elseif ($pkgDir -and (Test-Path -LiteralPath (Join-Path $pkgDir.FullName 'patches\inventory_use.insert.lua'))) { ReadText (Join-Path $pkgDir.FullName 'patches\inventory_use.insert.lua') } else { "" }

foreach ($f in @('weaponcomponents.meta', 'weaponarchetypes.meta')) {
    try { [void][xml](ReadText (Join-Path $dataDir $f)); Pass "$f well-formed" } catch { Fail "$f XML: $($_.Exception.Message)" }
}

foreach ($p in $pairs) {
    $w = $p.Weapon
    $tag = "[$w]"
    $cfg = ""
    if ($hasSkinRes) {
        $cfgFile = Join-Path $skinRes ("config\weapons\" + $w.ToLower() + ".lua")
        if (-not (Test-Path -LiteralPath $cfgFile)) { Warn "$tag no config/weapons/$($w.ToLower()).lua, skin is inactive"; continue }
        $cfg = ReadText $cfgFile
    } elseif ($pkgDir -and (Test-Path -LiteralPath (Join-Path $pkgDir.FullName 'patches\weapon_config.insert.lua'))) {
        $cfg = ReadText (Join-Path $pkgDir.FullName 'patches\weapon_config.insert.lua')
    }
    $compPattern = if ($hasSkinRes) { '\["' + [regex]::Escape($SkinType) + '"\]\s*=\s*"(COMPONENT_[A-Z0-9_]+)"' } else { '\["' + [regex]::Escape($SkinType) + '"\]\s*=\s*"(COMPONENT_SKIN_' + $w.ToUpper() + '_[A-Z0-9_]+)"' }
    $m = [regex]::Match($cfg, $compPattern)
    if (-not $m.Success) { Fail "$tag weaponTextures map missing"; continue }
    $comp = $m.Groups[1].Value
    Pass "$tag component $comp"

    $cm = [regex]::Match($componentsText, '<Name>' + $comp + '</Name>\s*<Model>([^<]+)</Model>')
    if (-not $cm.Success) { Fail "$tag $comp not in weaponcomponents.meta"; continue }
    $model = $cm.Groups[1].Value

    $metaPath = Join-Path $dataDir $metaFor[$w]
    $metaText = ReadText $metaPath
    $attachPatchName = ((Split-Path $metaPath -Leaf) -replace '\.meta$', '') + '.attach.insert.xml'
    $appliedToMeta = $metaText.Contains("<Name>$comp</Name>")
    if ($pkgDir -and -not $appliedToMeta -and (Test-Path -LiteralPath (Join-Path $pkgDir.FullName ("patches\" + $attachPatchName)))) {
        Warn "$tag $comp not yet applied to $(Split-Path $metaPath -Leaf); falling back to patches/$attachPatchName"
        $metaText += "`n" + (ReadText (Join-Path $pkgDir.FullName ("patches\" + $attachPatchName)))
    }
    if ($metaText.Contains("<Name>$comp</Name>")) {
        Pass "$tag attach point in $(Split-Path $metaPath -Leaf)"
        if ($appliedToMeta) {
            try {
                $xdoc = [xml](ReadText $metaPath)
                $compNodes = $xdoc.SelectNodes("//AttachPoints/Item[Components/Item/Name='$comp']")
                foreach ($cn in $compNodes) {
                    if ($cn.AttachBone -ne 'gun_root') { Fail "$tag $comp attached to $($cn.AttachBone) instead of gun_root in $(Split-Path $metaPath -Leaf)" }
                    if ($cn.Components.Item.Count -gt 12) { Warn "$tag AttachPoint in $(Split-Path $metaPath -Leaf) has $($cn.Components.Item.Count) components (>12 RAGE limit)" }
                }
            } catch { Fail "$tag XML parse $(Split-Path $metaPath -Leaf): $($_.Exception.Message)" }
        }
    } else { Fail "$tag $comp missing from $(Split-Path $metaPath -Leaf) AttachPoints" }
    if ($w -eq 'Revolver') {
        $mk2Path = Join-Path $dataDir 'weapons\weapons_revolver_mk2.meta'
        if (Test-Path -LiteralPath $mk2Path) {
            $mk2Text = ReadText $mk2Path
            if ($mk2Text.Contains("<Name>$comp</Name>")) { Pass "$tag attach point in weapons_revolver_mk2.meta" }
            else { Warn "$tag $comp missing from weapons_revolver_mk2.meta AttachPoints" }
        }
    }

    if ($archetypesText.Contains("<modelName>$model</modelName>")) { Pass "$tag archetype $model" } else { Warn "$tag $model has no weaponarchetypes.meta entry (lodDist falls back)" }

    $ydrPath = [IO.Directory]::GetFiles($weaponRes, "$model.ydr", [IO.SearchOption]::AllDirectories) | Select-Object -First 1
    if (-not $ydrPath) { Fail "$tag $model.ydr not found under [weapon]"; continue }
    $ydr = Get-Item -LiteralPath $ydrPath
    $sizeMb = $ydr.Length / 1MB
    if ($sizeMb -gt 4) { Warn ("$tag $model.ydr is {0:N1} MB; shipped skins average 1.2 MB" -f $sizeMb) } else { Pass ("$tag $model.ydr {0:N2} MB" -f $sizeMb) }

    $raw = Inflate $ydr.FullName
    if ($raw) {
        $sg = [BitConverter]::ToUInt64($raw, 0x10)
        $embedded = $false
        if ($sg -ge 0x50000000) { $embedded = [BitConverter]::ToUInt64($raw, [int64]($sg - 0x50000000) + 8) -ne 0 }
        $ytdFile = Join-Path $ydr.DirectoryName "$model.ytd"
        $ytd = Test-Path -LiteralPath $ytdFile
        if ($ytd) {
            $ytdRaw = Inflate $ytdFile
            if ($ytdRaw -and [BitConverter]::ToUInt16($ytdRaw, 0x28) -lt 1) {
                Fail "$tag companion $model.ytd has 0 textures (corrupt empty .ytd)"
            }
        }
        if ($embedded -or $ytd) { Pass "$tag textures present (embedded=$embedded, ytd=$ytd)" } else { Fail "$tag no embedded textures and no $model.ytd" }
    }

    if ($itemsText) {
        if ($itemsText.Contains("`"$($p.Item)`"")) { Pass "$tag item $($p.Item) in items.json" } else { Fail "$tag item $($p.Item) missing from items.json" }
    }
    if ($inventoryText) {
        if ($inventoryText.Contains("`"$($p.Item)`"")) { Pass "$tag inventory use action" } else { Warn "$tag $($p.Item) not in 1nfx_inventory action.use, no use button in inventory" }
    }
    $iconOk = (Test-Path -LiteralPath (Join-Path $iconDir "$($p.Item).png")) -or (Test-Path -LiteralPath (Join-Path $iconDir ("icon_" + $w.ToLower() + ".png")))
    $assetsImgDir = if ($assetsImgDirResolved) { $assetsImgDirResolved } else { Join-Path $Root '1nfx_assetsimg\items' }
    if (Test-Path -LiteralPath $assetsImgDir) {
        if (-not (Test-Path -LiteralPath (Join-Path $assetsImgDir "$($p.Item).png"))) {
            Warn "$tag $($p.Item).png missing from 1nfx_assetsimg/items"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $assetsImgDir "$comp.png"))) {
            Warn "$tag $comp.png missing from 1nfx_assetsimg/items"
        } else {
            Pass "$tag component icon $comp.png"
        }
    }
    if ($iconOk) { Pass "$tag icon $($p.Item).png" } else { Warn "$tag icon $($p.Item).png missing" }
}

$effectDir = if ($hasSkinRes) { Join-Path $skinRes 'html\img\effect' } elseif ($pkgDir) { Join-Path $pkgDir.FullName 'assets\effect' } else { "" }
foreach ($m in [regex]::Matches($lua, '(image|sound)\s*=\s*"([^"]+)"')) {
    $file = $m.Groups[2].Value
    if ($file -notmatch '^[\w.-]+$') { Fail "file name rejected by NUI validFile: $file"; continue }
    $found = (Test-Path -LiteralPath (Join-Path $effectDir $file)) -or ($hasSkinRes -and (Test-Path -LiteralPath (Join-Path $skinRes "html\sound\$file")))
    if ($found) { Pass "effect file $file" } else { Fail "effect file missing: $effectDir/$file" }
}

$dictionaries = @{}
foreach ($m in [regex]::Matches($lua, 'particleDictionary\s*=\s*"([^"]+)"\s*,\s*particleName\s*=\s*"([^"]+)"')) {
    $d = $m.Groups[1].Value
    if (-not $dictionaries.ContainsKey($d)) { $dictionaries[$d] = New-Object Collections.Generic.HashSet[string] }
    [void]$dictionaries[$d].Add($m.Groups[2].Value)
}
foreach ($d in $dictionaries.Keys) {
    $yptPath = $null
    foreach ($searchDir in @($weaponRes, $skinRes, $Root)) {
        if ($searchDir -and (Test-Path -LiteralPath $searchDir)) {
            $yptPath = [IO.Directory]::GetFiles($searchDir, "$d.ypt", [IO.SearchOption]::AllDirectories) | Select-Object -First 1
            if ($yptPath) { break }
        }
    }
    if (-not $yptPath) {
        if ($d -match '^(core|veh_|scr_|cut_|des_|proj_)') { Warn "dictionary $d is treated as base-game; confirm in game" } else { Fail "dictionary $d has no .ypt in resources" }
        continue
    }
    $raw = Inflate $yptPath
    if (-not $raw) { Warn "$d.ypt is not an RSC7 file, names not checked"; continue }
    $text = [Text.Encoding]::GetEncoding(28591).GetString($raw)
    foreach ($n in $dictionaries[$d]) { if ($text.Contains($n)) { Pass "particle $d/$n" } else { Fail "particle $n not found inside $d.ypt" } }
}

foreach ($m in [regex]::Matches($lua, '\bscale\s*=\s*([\d.]+)')) { if ([double]$m.Groups[1].Value -gt 4.0) { Warn "scale $($m.Groups[1].Value) exceeds particle_max_scale 4.0 and is clamped" } }
foreach ($m in [regex]::Matches($lua, '\bvolume\s*=\s*([\d.]+)')) { if ([double]$m.Groups[1].Value -gt 1.0) { Fail "volume $($m.Groups[1].Value) above 1.0" } }
foreach ($m in [regex]::Matches($lua, 'Screen\s*=\s*\{[^}]*?duration\s*=\s*(\d+)', 'Singleline')) { if ([int]$m.Groups[1].Value -gt 5000) { Warn "screen duration $($m.Groups[1].Value) is clamped to 5000 by the client" } }

Write-Output "RESULT fail=$script:fail warn=$script:warn"
if ($script:fail -gt 0) { exit 1 }
