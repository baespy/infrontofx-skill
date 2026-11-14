param(
    [Parameter(Mandatory = $true)][string]$Spec,
    [Parameter(Mandatory = $true)][string]$OutRoot,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$s = Get-Content -LiteralPath $Spec -Raw -Encoding UTF8 | ConvertFrom-Json

if ($s.id -cnotmatch '^[a-z][a-z0-9_]{1,19}$') { throw "id must match ^[a-z][a-z0-9_]{1,19}$ : $($s.id)" }
if ($s.skinType -cnotmatch '^[A-Z][A-Za-z0-9]{1,23}$') { throw "skinType must be PascalCase: $($s.skinType)" }

$Slots = @{
    poolcue  = @{ Key = 'Poolcue'; Item = 'skin_p_'; Prefix = 'w_me'; Meta = 'weapons/weaponpoolcue.meta'; Bone = 'gun_root' }
    bottle   = @{ Key = 'Bottle'; Item = 'skin_b_'; Prefix = 'w_me'; Meta = 'weapons/weaponbottle.meta'; Bone = 'gun_root' }
    knuckle  = @{ Key = 'Knuckle'; Item = 'skin_k_'; Prefix = 'w_me'; Meta = 'weapons/weaponknuckle.meta'; Bone = 'gun_root' }
    machete  = @{ Key = 'Machete'; Item = 'skin_m_'; Prefix = 'w_me'; Meta = 'weapons/weaponmachete.meta'; Bone = 'gun_root' }
    revolver = @{ Key = 'Revolver'; Item = 'skin_r_'; Prefix = 'w_pi'; Meta = 'weapons/weaponrevolver.meta'; Bone = 'gun_root' }
    bat      = @{ Key = 'Bat'; Item = 'skin_bat_'; Prefix = 'w_me'; Meta = 'weapons/weapons.meta'; Bone = 'gun_root' }
    knife    = @{ Key = 'Knife'; Item = 'skin_knife_'; Prefix = 'w_me'; Meta = 'weapons/weapons.meta'; Bone = 'gun_root' }
}

$id = $s.id
$type = $s.skinType
$label = if ($s.label) { $s.label } else { $id.ToUpper() }
$res = Join-Path $OutRoot "weapon_$id"
if ((Test-Path -LiteralPath $res) -and -not $Force) { throw "$res exists; pass -Force to regenerate its patches and assets" }

$componentsMeta = Join-Path $OutRoot 'weapon_core\data\weaponcomponents.meta'
if ((Test-Path -LiteralPath $componentsMeta) -and -not $Force) {
    $taken = @([regex]::Matches([IO.File]::ReadAllText($componentsMeta), '<Name>COMPONENT_SKIN_[A-Z0-9]+_([A-Z0-9_]+)</Name>') | ForEach-Object { $_.Groups[1].Value })
    if ($taken -contains $id.ToUpper()) { throw "skin id '$id' is already used by COMPONENT_SKIN_*_$($id.ToUpper()); pick another id (see references/server-catalog.md)" }
}

$patches = Join-Path $res 'patches'
$effect = Join-Path $res 'assets\effect'
foreach ($d in @((Join-Path $res 'stream'), (Join-Path $res 'source'), $patches, $effect)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }

[IO.File]::WriteAllText((Join-Path $res 'fxmanifest.lua'), "fx_version `"cerulean`"`r`ngame `"gta5`"`r`n`r`nfiles {`r`n    `"stream/**`",`r`n}`r`n", (New-Object Text.UTF8Encoding $false))

function Num($v) { ([double]$v).ToString('0.0###', [Globalization.CultureInfo]::InvariantCulture) }
function Prop($o, $n, $d) { if ($null -ne $o.PSObject.Properties[$n] -and $null -ne $o.$n) { $o.$n } else { $d } }

function ParticleLua($p, [string]$phase, [string]$ind) {
    $defaults = switch ($phase) {
        'hold' { @{ attach = $true; bone = 57005; delay = 0; loop = 1000; isLoop = $true; duration = 1000; restart = $true } }
        'hit' { @{ attach = $true; bone = 31086; delay = 0; loop = 500; isLoop = $false; duration = 0; restart = $false } }
        default { @{ attach = $false; bone = 0; delay = 100; loop = 500; isLoop = $false; duration = 0; restart = $false } }
    }
    $L = New-Object Collections.Generic.List[string]
    $L.Add("$ind{")
    $L.Add("$ind    particleDictionary = `"$($p.dict)`",")
    $L.Add("$ind    particleName = `"$($p.name)`",")
    $L.Add("$ind    attach = $((Prop $p 'attach' $defaults.attach).ToString().ToLower()),")
    $L.Add("$ind    delay = $(Prop $p 'delay' $defaults.delay),")
    $L.Add("$ind    scale = $(Num (Prop $p 'scale' 1.0)),")
    $L.Add("$ind    offset = { x = $(Num (Prop $p 'x' 0)), y = $(Num (Prop $p 'y' 0)), z = $(Num (Prop $p 'z' 0)) },")
    $L.Add("$ind    rot = { x = $(Num (Prop $p 'rx' 0)), y = $(Num (Prop $p 'ry' 0)), z = $(Num (Prop $p 'rz' 0)) },")
    $L.Add("$ind    bone = $(Prop $p 'bone' $defaults.bone),")
    $L.Add("$ind    loop = $(Prop $p 'loop' $defaults.loop),")
    $L.Add("$ind    isLoop = $((Prop $p 'isLoop' $defaults.isLoop).ToString().ToLower()),")
    $dur = Prop $p 'duration' $defaults.duration
    if ($dur -gt 0) { $L.Add("$ind    duration = $dur,") }
    if ((Prop $p 'restart' $defaults.restart) -eq $true) { $L.Add("$ind    restart = true,") }
    if ($null -ne $p.PSObject.Properties['ground']) { $L.Add("$ind    ground = $($p.ground.ToString().ToLower()),") }
    if ($null -ne $p.PSObject.Properties['color']) { $L.Add("$ind    color = { r = $(Num $p.color.r), g = $(Num $p.color.g), b = $(Num $p.color.b) },") }
    if ($null -ne $p.PSObject.Properties['alpha']) { $L.Add("$ind    alpha = $(Num $p.alpha),") }
    if ($null -ne $p.PSObject.Properties['orbit_turns']) { $L.Add("$ind    orbit_turns = $(Num $p.orbit_turns),") }
    if ($null -ne $p.PSObject.Properties['growScale']) { $L.Add("$ind    growScale = $(Num $p.growScale),") }
    if ($null -ne $p.PSObject.Properties['growSteps']) { $L.Add("$ind    growSteps = $([int]$p.growSteps),") }
    if ($null -ne $p.PSObject.Properties['growStepTime']) { $L.Add("$ind    growStepTime = $([int]$p.growStepTime),") }
    $L.Add("$ind},")
    $L -join "`r`n"
}

function EffectBlock($list, [string]$phase) {
    $parts = @("        Effect = {")
    foreach ($p in $list) { $parts += ParticleLua $p $phase '            ' }
    $parts += "        },"
    $parts -join "`r`n"
}

$fx = $s.fx
$scr = Prop $fx 'screen' $null
$snd = Prop $fx 'sound' $null

# A theme also supplies the matching screen and sound presets and their colours, unless the spec names its own.
$themeName = Prop $fx 'theme' $null
if ($themeName) {
    $themes = Get-Content -LiteralPath (Join-Path $here 'ptfx\ptfx-themes.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $th = $themes.$themeName
    if (-not $th) { throw "unknown fx.theme '$themeName'; run scripts\ptfx\ptfx.ps1 themes for the list" }
    $pal = @{}
    foreach ($p in $th.palette.PSObject.Properties) { $pal[$p.Name] = $p.Value }
    foreach ($part in ([string](Prop $fx 'theme_colors' '')).Split(',', [StringSplitOptions]::RemoveEmptyEntries)) {
        $kv = $part.Split('=')
        if ($kv.Count -eq 2) { $pal[$kv[0].Trim()] = $kv[1].Trim() }
    }
    if (-not $scr) { $scr = [pscustomobject]@{} }
    if (-not $snd) { $snd = [pscustomobject]@{} }
    foreach ($pair in @(@('preset', $th.screen), @('kill_preset', $th.kill_screen), @('primary', $pal.primary), @('secondary', $pal.deep), @('glow', $pal.secondary))) {
        if ($pair[1] -and $null -eq $scr.PSObject.Properties[$pair[0]]) { $scr | Add-Member -NotePropertyName $pair[0] -NotePropertyValue $pair[1] }
    }
    foreach ($pair in @(@('preset', $th.sound), @('kill_preset', $th.kill_sound))) {
        if ($pair[1] -and $null -eq $snd.PSObject.Properties[$pair[0]]) { $snd | Add-Member -NotePropertyName $pair[0] -NotePropertyValue $pair[1] }
    }
}
if (-not $scr -or -not (Prop $scr 'preset' $null)) { throw 'fx.screen.preset is missing; set it, or set fx.theme to take the theme''s preset' }
if (-not $snd -or -not (Prop $snd 'preset' $null)) { throw 'fx.sound.preset is missing; set it, or set fx.theme to take the theme''s preset' }
$soundFile = "${id}_hit.wav"
$killSoundFile = "${id}_kill.wav"
$image = "$id.png"
$killImage = $image

& (Join-Path $here 'make-screen.ps1') -OutFile (Join-Path $effect $image) -Preset $scr.preset -Primary $scr.primary -Secondary $scr.secondary -Glow $scr.glow -Seed ([int](Prop $s 'seed' 7))
& (Join-Path $here 'make-sound.ps1') -OutFile (Join-Path $effect $soundFile) -Preset $snd.preset -Kind hit -Seed ([int](Prop $s 'seed' 7))
& (Join-Path $here 'make-sound.ps1') -OutFile (Join-Path $effect $killSoundFile) -Preset (Prop $snd 'kill_preset' $snd.preset) -Kind kill -Seed ([int](Prop $s 'seed' 7))
if ($null -ne $scr.PSObject.Properties['kill_preset'] -and $scr.kill_preset) {
    $killImage = "${id}_kill.png"
    & (Join-Path $here 'make-screen.ps1') -OutFile (Join-Path $effect $killImage) -Preset $scr.kill_preset -Primary (Prop $scr 'kill_primary' $scr.primary) -Secondary (Prop $scr 'kill_secondary' $scr.secondary) -Glow (Prop $scr 'kill_glow' $scr.glow) -Seed ([int](Prop $s 'seed' 7) + 1)
}

$ptfxReport = @()
if ($themeName -and -not (Prop $fx 'ptfx' $null)) {
    # A theme gives the set a complete Hold/Hit/Kill dictionary. The design is written once; later runs rebuild from
    # source\ptfx.design.json so hand edits to it survive -Force.
    $designPath = Join-Path $res 'source\ptfx.design.json'
    if (-not (Test-Path -LiteralPath $designPath)) {
        $newArgs = @{ Mode = 'new'; Theme = $themeName; Name = $id; Out = $designPath }
        $themeColors = Prop $fx 'theme_colors' $null
        if ($themeColors) { $newArgs.Colors = $themeColors }
        & (Join-Path $here 'ptfx\ptfx.ps1') @newArgs | Out-Null
    }
    $ptfxReport = @(& (Join-Path $here 'ptfx\ptfx.ps1') build -Spec $designPath -Out (Join-Path $res 'stream'))
    if (-not ($ptfxReport -match 'RESULT ok')) { $ptfxReport; throw 'particle dictionary build failed' }
    $auto = @{ hold = "${id}_hold"; hit = "${id}_hit"; kill = "${id}_kill" }
    foreach ($phase in 'hold', 'hit', 'kill') {
        if ($null -eq $fx.PSObject.Properties[$phase] -or @($fx.$phase).Count -eq 0) {
            $fx | Add-Member -NotePropertyName $phase -NotePropertyValue @([pscustomobject]@{ dict = "${id}_fx"; name = $auto[$phase] }) -Force
        }
    }
}
if ($null -ne $fx.PSObject.Properties['ptfx'] -and $fx.ptfx) {
    $designPath = Join-Path $res 'source\ptfx.design.json'
    if ($fx.ptfx -is [string]) {
        $src = $fx.ptfx
        if (-not [IO.Path]::IsPathRooted($src)) { $src = Join-Path (Split-Path -Parent (Resolve-Path -LiteralPath $Spec).ProviderPath) $src }
        if ((Resolve-Path -LiteralPath $src).ProviderPath -ne $designPath) { Copy-Item -LiteralPath $src -Destination $designPath -Force }
    } else {
        [IO.File]::WriteAllText($designPath, ($fx.ptfx | ConvertTo-Json -Depth 30), (New-Object Text.UTF8Encoding $false))
    }
    $ptfxReport = @(& (Join-Path $here 'ptfx\ptfx.ps1') build -Spec $designPath -Out (Join-Path $res 'stream'))
    if (-not ($ptfxReport -match 'RESULT ok')) { $ptfxReport; throw 'particle dictionary build failed' }
}

$duration = [int](Prop $scr 'duration' 2000)
$hitVol = Num (Prop $snd 'hit_volume' 0.35)
$killVol = Num (Prop $snd 'kill_volume' $hitVol)

$lua = New-Object Collections.Generic.List[string]
$lua.Add("Config.General.itemSkins[`"$type`"] = {")
foreach ($w in $s.weapons) { $lua.Add("    $($Slots[$w].Key) = `"$($Slots[$w].Item)$id`",") }
$lua.Add("}")
$lua.Add("")
$lua.Add("Config.General.skinLabels[`"$type`"] = `"$label`"")
$lua.Add("")
$lua.Add("Config.General.weaponEffects[`"$type`"] = {")
if ($fx.hold -and @($fx.hold).Count -gt 0) {
    $lua.Add("    Hold = {")
    $lua.Add((EffectBlock $fx.hold 'hold'))
    $lua.Add("    },")
}
$lua.Add("    Hit = {")
if ($fx.hit -and @($fx.hit).Count -gt 0) { $lua.Add((EffectBlock $fx.hit 'hit')) }
$lua.Add("        Screen = {")
$lua.Add("            image = `"$image`",")
$lua.Add("            sound = `"$soundFile`",")
$lua.Add("            duration = $duration,")
$lua.Add("            volume = $hitVol,")
$lua.Add("        },")
$lua.Add("    },")
$lua.Add("    Kill = {")
if ($fx.kill -and @($fx.kill).Count -gt 0) { $lua.Add((EffectBlock $fx.kill 'kill')) }
$lua.Add("        Screen = {")
$lua.Add("            image = `"$killImage`",")
$lua.Add("            sound = `"$killSoundFile`",")
$lua.Add("            duration = $duration,")
$lua.Add("            volume = $killVol,")
$lua.Add("        },")
$lua.Add("    },")
$lua.Add("}")
[IO.File]::WriteAllText((Join-Path $patches "$id.skin.lua"), (($lua -join "`r`n") + "`r`n"), (New-Object Text.UTF8Encoding $false))

$components = New-Object Collections.Generic.List[string]
$archetypes = New-Object Collections.Generic.List[string]
$sql = New-Object Collections.Generic.List[string]
$items = New-Object Collections.Generic.List[string]
$mapLines = New-Object Collections.Generic.List[string]
$attach = @{}

foreach ($w in $s.weapons) {
    $slot = $Slots[$w]
    $upper = $id.ToUpper()
    $comp = "COMPONENT_SKIN_$($slot.Key.ToUpper())_$upper"
    $model = "$($slot.Prefix)_${id}_$w"
    $item = "$($slot.Item)$id"
    $components.Add(@"
    <Item type="CWeaponComponentVariantModelInfo">
      <Name>$comp</Name>
      <Model>$model</Model>
      <LocName>WCT_INVALID</LocName>
      <LocDesc>WCD_INVALID</LocDesc>
      <AttachBone />
      <AccuracyModifier type="NULL" />
      <DamageModifier type="NULL" />
      <bShownOnWheel value="false" />
      <CreateObject value="false" />
      <HudDamage value="0" />
      <HudSpeed value="0" />
      <HudCapacity value="0" />
      <HudAccuracy value="0" />
      <HudRange value="0" />
      <TintIndexOverride value="0" />
    </Item>
"@)
    $archetypes.Add(@"
    <Item>
      <modelName>$model</modelName>
      <txdName>$model</txdName>
      <ptfxAssetName>NULL</ptfxAssetName>
      <lodDist value="50" />
    </Item>
"@)
    if (-not $attach.ContainsKey($slot.Meta)) { $attach[$slot.Meta] = New-Object Collections.Generic.List[string] }
    $attach[$slot.Meta].Add(@"
                <Item>
                  <Name>$comp</Name>
                  <Default value="false" />
                </Item>
"@)
    $mapLines.Add("-- config/weapons/$w.lua, inside weaponTextures[`"$($slot.Key)`"].skins")
    $mapLines.Add("[`"$type`"] = `"$comp`",")
    $itemLabel = "$($slot.Key.ToUpper()) $label"
    $sql.Add("    ('$item', '$itemLabel', -1, 1, 0, 1)")
    $items.Add(@"
    {
        "usable": false,
        "label": "$itemLabel",
        "limit": -1,
        "name": "$item",
        "canRemove": 1,
        "rare": 0,
        "weight": 1
    }
"@)
}

$utf8 = New-Object Text.UTF8Encoding $false
[IO.File]::WriteAllText((Join-Path $patches 'weaponcomponents.insert.xml'), ($components -join "`r`n"), $utf8)
[IO.File]::WriteAllText((Join-Path $patches 'weaponarchetypes.insert.xml'), ($archetypes -join "`r`n"), $utf8)
foreach ($k in $attach.Keys) {
    $name = ($k -replace '^weapons/', '' -replace '\.meta$', '') + '.attach.insert.xml'
    [IO.File]::WriteAllText((Join-Path $patches $name), ($attach[$k] -join "`r`n"), $utf8)
}
[IO.File]::WriteAllText((Join-Path $patches 'weapon_config.insert.lua'), ($mapLines -join "`r`n"), $utf8)
[IO.File]::WriteAllText((Join-Path $patches "$id.items.sql"), ("INSERT IGNORE INTO ``items`` (``name``, ``label``, ``limit``, ``weight``, ``rare``, ``can_remove``)`r`nVALUES`r`n" + ($sql -join ",`r`n") + ";`r`n"), $utf8)
[IO.File]::WriteAllText((Join-Path $patches 'es_extended.items.insert.json'), ($items -join ",`r`n"), $utf8)
[IO.File]::WriteAllText((Join-Path $patches 'inventory_use.insert.lua'), ((@($s.weapons | ForEach-Object { "            `"$($Slots[$_].Item)$id`"," }) -join "`r`n") + "`r`n"), $utf8)

"resource: $res"
if ($ptfxReport.Count) { $ptfxReport | Where-Object { $_ -match '^(callable effect|ERROR|WARN|NOTE|LINT|RESULT|sprite preview|wrote )' } }
"models expected in stream/: " + (($s.weapons | ForEach-Object { "$($Slots[$_].Prefix)_${id}_$_.ydr" }) -join ', ')
"patches: $patches"
"effect assets: $effect"
if ($s.weapons -contains 'bat') { "warning: Bat has no config/weapons/bat.lua in 1nfx_weaponskin; Bat skins stay inactive until that file exists" }
