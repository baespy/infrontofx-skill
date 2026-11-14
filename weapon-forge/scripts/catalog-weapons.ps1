param(
    [Parameter(Mandatory = $true)][string]$WeaponRoot,
    [string]$OutMd,
    [string]$OutJson
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lib-rsc.ps1')

function ResourceOf([string]$path) {
    $rel = $path.Substring($WeaponRoot.TrimEnd('\').Length + 1)
    $rel.Split('\')[0]
}

$WeaponRoot = (Resolve-Path -LiteralPath $WeaponRoot).ProviderPath
$coreData = Join-Path $WeaponRoot 'weapon_core\data'
$all = Get-ChildItem -LiteralPath $WeaponRoot -Recurse -File -Force

$locked = @{}
foreach ($d in Get-ChildItem -LiteralPath $WeaponRoot -Directory -Force) {
    $locked[$d.Name] = [bool](Get-ChildItem -LiteralPath $d.FullName -Recurse -File -Force -Filter '*.fxap' | Select-Object -First 1)
}

$ydrIndex = @{}
foreach ($f in $all | Where-Object { $_.Extension -ieq '.ydr' }) {
    if (-not $ydrIndex.ContainsKey($f.BaseName)) { $ydrIndex[$f.BaseName] = New-Object Collections.Generic.List[object] }
    $ydrIndex[$f.BaseName].Add($f)
}
$ytdIndex = @{}
foreach ($f in $all | Where-Object { $_.Extension -ieq '.ytd' }) {
    if (-not $ytdIndex.ContainsKey($f.BaseName)) { $ytdIndex[$f.BaseName] = New-Object Collections.Generic.List[object] }
    $ytdIndex[$f.BaseName].Add($f)
}

$componentsText = [IO.File]::ReadAllText((Join-Path $coreData 'weaponcomponents.meta'))
$archetypesText = [IO.File]::ReadAllText((Join-Path $coreData 'weaponarchetypes.meta'))
$attachFiles = Get-ChildItem -LiteralPath (Join-Path $coreData 'weapons') -File -Filter '*.meta'
$attachText = ($attachFiles | ForEach-Object { [IO.File]::ReadAllText($_.FullName) }) -join "`n"

$stats = @{}
function StatsFor([string]$model) {
    if ($stats.ContainsKey($model)) { return $stats[$model] }
    $result = $null
    if ($ydrIndex.ContainsKey($model)) {
        $file = $ydrIndex[$model][0]
        $res = ResourceOf $file.FullName
        if (-not $locked[$res]) {
            try {
                $raw = Inflate $file.FullName
                if ($raw) {
                    $result = ReadDrawable $raw
                    $ext = @()
                    if ($ytdIndex.ContainsKey($model)) {
                        $td = Inflate $ytdIndex[$model][0].FullName
                        if ($td) { $ext = ReadTextures $td 0 }
                    }
                    $result | Add-Member -NotePropertyName externalTextures -NotePropertyValue @($ext)
                }
            } catch { $result = $null }
        }
    }
    $stats[$model] = $result
    return $result
}

$components = New-Object Collections.Generic.List[object]
$seen = New-Object 'Collections.Generic.HashSet[string]'
foreach ($m in [regex]::Matches($componentsText, '<Name>(COMPONENT_SKIN_([A-Z0-9]+)_([A-Z0-9_]+))</Name>\s*<Model>([^<]+)</Model>')) {
    $comp = $m.Groups[1].Value
    if (-not $seen.Add($comp)) { continue }
    $model = $m.Groups[4].Value
    $file = if ($ydrIndex.ContainsKey($model)) { $ydrIndex[$model][0] } else { $null }
    $res = if ($file) { ResourceOf $file.FullName } else { $null }
    $s = StatsFor $model
    $components.Add([pscustomobject]@{
        component = $comp
        slot = $m.Groups[2].Value
        skin = $m.Groups[3].Value
        model = $model
        resource = $res
        locked = if ($res) { [bool]$locked[$res] } else { $false }
        ydrKB = if ($file) { [math]::Round($file.Length / 1KB) } else { $null }
        hasYtd = $ytdIndex.ContainsKey($model)
        attached = $attachText.Contains("<Name>$comp</Name>")
        archetype = $archetypesText.Contains("<modelName>$model</modelName>")
        tris = if ($s) { $s.tris } else { $null }
        shaders = if ($s) { $s.shaders } else { @() }
        textures = if ($s) { @($s.textures) + @($s.externalTextures) | Where-Object { $_ } } else { @() }
        bones = if ($s) { $s.bones } else { @() }
        min = if ($s) { $s.min } else { $null }
        max = if ($s) { $s.max } else { $null }
    })
}

$resources = foreach ($d in Get-ChildItem -LiteralPath $WeaponRoot -Directory -Force | Sort-Object Name) {
    $files = @($all | Where-Object { $_.FullName.StartsWith($d.FullName + '\') })
    $compsHere = @($components | Where-Object { $_.resource -eq $d.Name })
    [pscustomobject]@{
        resource = $d.Name
        locked = [bool]$locked[$d.Name]
        ydr = @($files | Where-Object { $_.Extension -ieq '.ydr' }).Count
        ytd = @($files | Where-Object { $_.Extension -ieq '.ytd' }).Count
        ypt = @($files | Where-Object { $_.Extension -ieq '.ypt' } | ForEach-Object { $_.BaseName })
        ycd = @($files | Where-Object { $_.Extension -ieq '.ycd' }).Count
        MB = [math]::Round((($files | Measure-Object Length -Sum).Sum) / 1MB, 1)
        components = $compsHere.Count
        slots = @($compsHere | ForEach-Object { $_.slot } | Sort-Object -Unique)
        skins = @($compsHere | ForEach-Object { $_.skin } | Sort-Object -Unique)
    }
}

$referenced = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
foreach ($c in $components) { [void]$referenced.Add($c.model) }
foreach ($m in [regex]::Matches($componentsText, '<Model>([^<]+)</Model>')) { [void]$referenced.Add($m.Groups[1].Value) }
foreach ($m in [regex]::Matches($archetypesText, '<modelName>([^<]+)</modelName>')) { [void]$referenced.Add($m.Groups[1].Value) }

$missingModel = @($components | Where-Object { -not $_.resource })
$notAttached = @($components | Where-Object { -not $_.attached })
$noArchetype = @($components | Where-Object { -not $_.archetype })
$orphans = @($ydrIndex.Keys | Where-Object { -not $referenced.Contains($_) -and -not $referenced.Contains(($_ -replace '_hi$', '')) } | Sort-Object | ForEach-Object { [pscustomobject]@{ model = $_; resource = ResourceOf $ydrIndex[$_][0].FullName } })
$dupStream = New-Object Collections.Generic.List[object]
foreach ($g in $all | Where-Object { $_.Extension -in '.ydr', '.ytd', '.ypt' } | Group-Object Name | Where-Object { $_.Count -gt 1 }) {
    $dupStream.Add([pscustomobject]@{ file = $g.Name; resources = @($g.Group | ForEach-Object { ResourceOf $_.FullName } | Sort-Object -Unique) })
}

function Median($v) { $s = @($v | Sort-Object); if ($s.Count -eq 0) { return $null }; $s[[int][math]::Floor($s.Count / 2)] }

$slotStats = foreach ($g in $components | Group-Object slot | Sort-Object Name) {
    $measured = @($g.Group | Where-Object { $null -ne $_.tris -and $_.tris -gt 0 })
    $real = @($measured | Where-Object { $_.tris -ge 2000 })
    [pscustomobject]@{
        slot = $g.Name
        total = $g.Count
        open = @($g.Group | Where-Object { $_.resource -and -not $_.locked }).Count
        locked = @($g.Group | Where-Object { $_.locked }).Count
        missing = @($g.Group | Where-Object { -not $_.resource }).Count
        measured = $measured.Count
        customMeshes = $real.Count
        trisMin = if ($real) { ($real | Measure-Object tris -Minimum).Minimum } else { $null }
        trisMedian = Median ($real | ForEach-Object { $_.tris })
        trisMax = if ($real) { ($real | Measure-Object tris -Maximum).Maximum } else { $null }
    }
}

$shaderUse = @{}
$texUse = @{}
foreach ($c in $components) {
    foreach ($s in $c.shaders) { $shaderUse[$s] = 1 + [int]$shaderUse[$s] }
    foreach ($t in $c.textures) { $k = "$($t.w)x$($t.h) $($t.fmt)"; $texUse[$k] = 1 + [int]$texUse[$k] }
}

$summary = [pscustomobject]@{
    resources = @($resources).Count
    lockedResources = @($resources | Where-Object { $_.locked }).Count
    openResources = @($resources | Where-Object { -not $_.locked }).Count
    components = $components.Count
    measuredComponents = @($components | Where-Object { $null -ne $_.tris }).Count
    skins = @($components | ForEach-Object { $_.skin } | Sort-Object -Unique).Count
    files = @($all).Count
    MB = [math]::Round((($all | Measure-Object Length -Sum).Sum) / 1MB, 1)
}

if ($OutJson) {
    $problems = [pscustomobject]@{
        missingModel = @($missingModel | ForEach-Object { $_.component + ' -> ' + $_.model })
        notAttached = @($notAttached | ForEach-Object { $_.component })
        noArchetype = @($noArchetype | ForEach-Object { $_.model })
        orphans = @($orphans)
        duplicateStream = @($dupStream | ForEach-Object { $_ })
    }
    $payload = [pscustomobject]@{
        summary = $summary
        slots = @($slotStats)
        resources = @($resources)
        components = @($components | ForEach-Object { $_ })
        problems = $problems
    }
    [IO.File]::WriteAllText($OutJson, ($payload | ConvertTo-Json -Depth 6 -Compress), (New-Object Text.UTF8Encoding $false))
}

$L = New-Object Collections.Generic.List[string]
$L.Add('# Server Catalog')
$L.Add('')
$L.Add('สร้างจาก `scripts/catalog-weapons.ps1` อย่าแก้มือ รันใหม่เมื่อเพิ่มหรือลบสกิน รายละเอียดทุก component อยู่ใน `server-catalog.json`')
$L.Add('')
$L.Add("Resource $($summary.resources) ตัว (เปิดได้ $($summary.openResources), ล็อก .fxap $($summary.lockedResources)) | Component สกิน $($summary.components) | ชื่อสกินไม่ซ้ำ $($summary.skins) | ไฟล์ $($summary.files) ไฟล์ $($summary.MB) MB")
$L.Add('')
$L.Add('ตัวเลข tris, shader และ texture อ่านจากไฟล์ใน resource ที่ไม่ล็อกเท่านั้น ส่วนที่ล็อกดูแค่ชื่อและขนาดไฟล์')
$L.Add('')
$L.Add('## แยกตามช่อง')
$L.Add('')
$L.Add('| ช่อง | ทั้งหมด | เปิดได้ | ล็อก | ไม่พบไฟล์ | โมเดลปั้นเอง (>=2k tris) | tris ต่ำสุด | ค่ากลาง | สูงสุด |')
$L.Add('| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |')
foreach ($s in $slotStats) { $L.Add("| $($s.slot) | $($s.total) | $($s.open) | $($s.locked) | $($s.missing) | $($s.customMeshes) | $($s.trisMin) | $($s.trisMedian) | $($s.trisMax) |") }
$L.Add('')
$L.Add('## Shader ที่ใช้จริง')
$L.Add('')
$L.Add('| shader | จำนวนโมเดล |')
$L.Add('| --- | ---: |')
foreach ($k in $shaderUse.Keys | Sort-Object { -$shaderUse[$_] }) { $L.Add("| ``$k`` | $($shaderUse[$k]) |") }
$L.Add('')
$L.Add('## Texture ที่ใช้จริง')
$L.Add('')
$L.Add('| ขนาดและฟอร์แมต | จำนวน |')
$L.Add('| --- | ---: |')
foreach ($k in $texUse.Keys | Sort-Object { -$texUse[$_] } | Select-Object -First 15) { $L.Add("| $k | $($texUse[$k]) |") }
$L.Add('')
$L.Add('## Resource ทั้งหมด')
$L.Add('')
$L.Add('| resource | สถานะ | ydr | ytd | ycd | MB | component | ช่อง | particle dictionary |')
$L.Add('| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |')
foreach ($r in $resources) {
    $st = if ($r.locked) { 'ล็อก' } else { 'เปิดได้' }
    $L.Add("| ``$($r.resource)`` | $st | $($r.ydr) | $($r.ytd) | $($r.ycd) | $($r.MB) | $($r.components) | $($r.slots -join ' ') | $($r.ypt -join ' ') |")
}
$L.Add('')
$L.Add('## ชื่อที่ใช้แล้ว')
$L.Add('')
$L.Add('ห้ามตั้ง `id` หรือ `skinType` ซ้ำกับรายการนี้')
$L.Add('')
$L.Add((@($components | ForEach-Object { $_.skin } | Sort-Object -Unique) -join ', '))
$L.Add('')
$L.Add('## จุดที่ควรตรวจ')
$L.Add('')
$L.Add("- Component ที่หา ``.ydr`` ไม่เจอใน ``[weapon]``: $($missingModel.Count)")
foreach ($c in $missingModel | Select-Object -First 25) { $L.Add("  - ``$($c.component)`` -> ``$($c.model)``") }
if ($missingModel.Count -gt 25) { $L.Add("  - และอีก $($missingModel.Count - 25) รายการใน JSON") }
$L.Add("- Component ที่ไม่มี attach point ใน meta อาวุธ: $($notAttached.Count)")
foreach ($c in $notAttached | Select-Object -First 25) { $L.Add("  - ``$($c.component)``") }
if ($notAttached.Count -gt 25) { $L.Add("  - และอีก $($notAttached.Count - 25) รายการใน JSON") }
$L.Add("- Model ที่ไม่มีใน ``weaponarchetypes.meta``: $($noArchetype.Count) (เกมใช้ค่า lodDist สำรอง ไม่ใช่ข้อผิดพลาดเสมอไป)")
$L.Add("- ``.ydr`` ที่ไม่มี component หรือ archetype อ้างถึง: $($orphans.Count)")
foreach ($o in $orphans | Select-Object -First 30) { $L.Add("  - ``$($o.model)`` ใน ``$($o.resource)``") }
if ($orphans.Count -gt 30) { $L.Add("  - และอีก $($orphans.Count - 30) รายการใน JSON") }
$L.Add("- ไฟล์ stream ชื่อซ้ำข้าม resource: $($dupStream.Count)")
foreach ($d in $dupStream | Select-Object -First 25) { $L.Add("  - ``$($d.file)`` ใน $($d.resources -join ', ')") }
$md = ($L -join "`r`n") + "`r`n"
if ($OutMd) { [IO.File]::WriteAllText($OutMd, $md, (New-Object Text.UTF8Encoding $false)) }

Write-Output ("resources={0} locked={1} components={2} measured={3} missingModel={4} notAttached={5} noArchetype={6} orphans={7} duplicateStream={8}" -f $summary.resources, $summary.lockedResources, $summary.components, $summary.measuredComponents, $missingModel.Count, $notAttached.Count, $noArchetype.Count, $orphans.Count, $dupStream.Count)
