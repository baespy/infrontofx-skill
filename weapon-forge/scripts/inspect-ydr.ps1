param(
    [Parameter(Mandatory = $true)][string[]]$Path,
    [ValidateSet('', 'poolcue', 'bottle', 'knuckle', 'machete', 'revolver', 'bat', 'knife')][string]$Slot = '',
    [switch]$Summary
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lib-rsc.ps1')

$SlotLimits = @{
    poolcue = @{ zMin = -0.25; zMax = 1.10; tris = 40054; bones = 'Gun_Root', 'Gun_GripR', 'Gun_GripL' }
    bat = @{ zMin = -0.20; zMax = 0.85; tris = 30000; bones = 'Gun_Root', 'Gun_GripR' }
    bottle = @{ zMin = -0.20; zMax = 0.45; tris = 30000; bones = 'Gun_Root', 'Gun_GripR' }
    machete = @{ zMin = -0.15; zMax = 0.60; tris = 30000; bones = 'Gun_Root', 'Gun_GripR' }
    knife = @{ zMin = -0.15; zMax = 0.40; tris = 30000; bones = 'Gun_Root', 'Gun_GripR' }
    knuckle = @{ zMin = -0.12; zMax = 0.15; tris = 30000; bones = 'Gun_Root', 'Gun_GripR' }
    revolver = @{ zMin = -0.22; zMax = 0.20; tris = 30000; bones = 'Gun_Root', 'Gun_GripR', 'Gun_Muzzle' }
}

function ExpectedStride($t) {
    switch ($t.fmt) {
        'DXT1' { return [int]($t.w / 2) }
        'DXT5' { return [int]$t.w }
        'A8R8G8B8' { return [int]$t.w * 4 }
        default { return -1 }
    }
}

function PageFlags([uint32]$f) {
    [int64]$base = [int64]512 -shl ($f -band 15)
    $fields = @(@(4, 1, 8), @(5, 3, 7), @(7, 15, 6), @(11, 63, 5), @(17, 127, 4), @(24, 1, 3), @(25, 1, 2), @(26, 1, 1), @(27, 1, 0))
    [int64]$total = 0
    foreach ($x in $fields) { $total += [int64](($f -shr $x[0]) -band $x[1]) * ($base -shl $x[2]) }
    $total
}

function ReadBoneCountField($r) {
    $sk = VOff (U64 $r 0x18)
    if ($sk -lt 0) { return $null }
    $bonesOff = VOff (U64 $r ($sk + 0x20))
    $invOff = VOff (U64 $r ($sk + 0x28))
    $parOff = VOff (U64 $r ($sk + 0x38))
    $cparOff = VOff (U64 $r ($sk + 0x40))
    $gripQw = if ($bonesOff -ge 0) { [BitConverter]::ToSingle($r, $bonesOff + 0x50 + 0x0C) } else { 1.0 }
    $inv1W = if ($invOff -ge 0) { [BitConverter]::ToSingle($r, $invOff + 0x40 + 0x1C) } else { 0.0 }
    [pscustomobject]@{
        at5A = U16 $r ($sk + 0x5A)
        at5C = U16 $r ($sk + 0x5C)
        at5E = U16 $r ($sk + 0x5E)
        at60 = U16 $r ($sk + 0x60)
        parOff = $parOff
        cparOff = $cparOff
        gripQw = $gripQw
        inv1W = $inv1W
    }
}

$totalFail = 0
foreach ($p in $Path) {
    $file = Get-Item -LiteralPath $p
    $fail = 0
    $warn = 0
    $lines = New-Object Collections.Generic.List[string]
    $note = { param($level, $msg) if ($level -eq 'FAIL') { $script:fail++ } elseif ($level -eq 'WARN') { $script:warn++ }; $lines.Add("  $level  $msg") }

    $head = [IO.File]::ReadAllBytes($file.FullName)
    if ($head.Length -lt 16 -or [Text.Encoding]::ASCII.GetString($head, 0, 4) -ne 'RSC7') {
        Write-Output "$($file.Name): not an RSC7 resource (encrypted or wrong format), skipped"
        continue
    }
    $version = [BitConverter]::ToUInt32($head, 4)
    $sysFlags = [BitConverter]::ToUInt32($head, 8)
    $gfxFlags = [BitConverter]::ToUInt32($head, 12)
    $raw = Inflate $file.FullName
    $d = ReadDrawable $raw

    $lines.Add(("{0}  {1:N0} KB  rsc v{2}  sys 0x{3:x8}  gfx 0x{4:x8}" -f $file.Name, ($file.Length / 1KB), $version, $sysFlags, $gfxFlags))
    $lines.Add(("  tris {0}  verts {1}  geoms {2}  bones {3}  shaders [{4}]" -f $d.tris, $d.verts, $d.geoms, $d.bones.Count, ($d.shaders -join ', ')))
    $lines.Add(("  bbox min ({0}) max ({1})" -f ($d.min -join ', '), ($d.max -join ', ')))

    if ($version -ne 165) { & $note 'FAIL' "resource version $version, drawables must be 165" }
    $expected = (PageFlags $sysFlags) + (PageFlags $gfxFlags)
    if ($raw.Length -ne $expected) { & $note 'FAIL' "inflated size $($raw.Length) does not match page flags $expected" }
    if ($d.tris -le 0) { & $note 'FAIL' 'no triangles in the high LOD' }
    if ($d.indices -ne ($d.tris * 3)) { & $note 'FAIL' "indices $($d.indices) is not tris x 3" }
    if ($d.shaders.Count -eq 0) { & $note 'FAIL' 'no shaders' }
    foreach ($s in $d.shaders) { if ($s -like '0x*') { & $note 'WARN' "unknown shader hash $s" } }
    $bc = ReadBoneCountField $raw
    if ($null -eq $bc) {
        & $note 'FAIL' 'no skeleton, weapon bones are required'
    } else {
        if ($bc.at5E -eq 0) {
            & $note 'FAIL' "skeleton has 0 bones at +0x5E (u16 at +0x5A is $($bc.at5A)); the bone count field is misplaced if that value looks like the bone count"
        }
        if ([Math]::Abs($bc.gripQw - 1.0) -lt 0.01) {
            & $note 'FAIL' "Gun_GripR has identity rotation (qw=$($bc.gripQw)); weapon will twist ~78 deg wrong in hand"
        }
        if ([Math]::Abs($bc.inv1W) -gt 0.01) {
            & $note 'FAIL' "TransformationsInverted[1] has non-zero w=$($bc.inv1W); inverse bind matrix is corrupt"
        }
        if ($bc.cparOff -lt 0) {
            & $note 'FAIL' 'ChildParentIndices pointer at skel+0x40 is NULL'
        } elseif ($bc.at5E -gt 1) {
            if ($bc.at60 -eq 0 -or ($bc.at60 % 8) -ne 0) {
                & $note 'FAIL' "ChildParentIndicesCount at skel+0x60 ($($bc.at60)) must be a non-zero multiple of 8 uint16s (4 SIMD pairs)"
            } else {
                $pairCount = [int]($bc.at60 / 2)
                $seenChild = @{}
                for ($pi = 0; $pi -lt $pairCount; $pi++) {
                    $ch = [BitConverter]::ToInt16($raw, [int]($bc.cparOff + $pi * 4))
                    $pr = [BitConverter]::ToInt16($raw, [int]($bc.cparOff + $pi * 4 + 2))
                    if ($ch -lt 0 -or $ch -ge $bc.at5E -or $pr -lt 0 -or $pr -ge $bc.at5E) {
                        & $note 'FAIL' "ChildParentIndices[$pi]=($ch,$pr) out of bone range 0..$($bc.at5E - 1) (buffer over-read -> crSkeleton::Update crash!)"
                        break
                    }
                    $seenChild[[int]$ch] = $true
                    if ($bc.parOff -ge 0) {
                        $wantPar = [BitConverter]::ToInt16($raw, [int]($bc.parOff + $ch * 2))
                        if ($wantPar -ne $pr) {
                            & $note 'FAIL' "ChildParentIndices[$pi]=($ch,$pr) mismatches ParentIndices[$ch]=$wantPar"
                            break
                        }
                    }
                }
                for ($bi = 1; $bi -lt $bc.at5E; $bi++) {
                    if (-not $seenChild.ContainsKey($bi)) {
                        & $note 'FAIL' "bone[$bi] ($($d.bones[$bi])) missing from ChildParentIndices; bone matrix will never update"
                    }
                }
            }
        }
    }

    $bndOff = VOff (U64 $raw 0xC8)
    if ($bndOff -ge 0 -and $raw[$bndOff + 0x10] -eq 10) {
        $chPtrs = VOff (U64 $raw ($bndOff + 0x70))
        $chCnt = U16 $raw ($bndOff + 0xA0)
        for ($ci = 0; $ci -lt $chCnt; $ci++) {
            $chOff = VOff (U64 $raw ($chPtrs + 8 * $ci))
            if ($chOff -ge 0) {
                $matRaw = U32 $raw ($chOff + 0x4C)
                if (($matRaw -band 0xFF000000) -ge 0x3F000000 -and ($matRaw -band 0x0000FFFF) -eq 0) {
                    & $note 'FAIL' ("phBound child[$ci] MaterialId at +0x4C (0x{0:x8}) looks like float instead of integer material id" -f $matRaw)
                }
            }
        }
    }

    $ytdPath = [IO.Path]::ChangeExtension($file.FullName, '.ytd')
    if (-not $file.Name.EndsWith('_hi.ydr') -and (Test-Path -LiteralPath $ytdPath)) {
        $ytdRaw = Inflate $ytdPath
        $ytdCount = U16 $ytdRaw 0x28
        if ($ytdCount -lt 1) {
            & $note 'FAIL' "companion $([IO.Path]::GetFileName($ytdPath)) has 0 textures (empty .ytd breaks texture lookup)"
        }
    }

    foreach ($t in $d.textures) {
        $want = ExpectedStride $t
        $lines.Add(("  texture {0}  {1}x{2} {3} stride {4} mips {5}" -f $t.name, $t.w, $t.h, $t.fmt, $t.stride, $t.mips))
        if ($want -gt 0 -and $t.stride -ne $want) { & $note 'FAIL' "texture $($t.name) stride $($t.stride), expected $want for $($t.fmt)" }
        if ($t.mips -lt 1) { & $note 'FAIL' "texture $($t.name) has no mip levels" }
    }
    if ($d.textures.Count -eq 0) { & $note 'WARN' 'no embedded textures, a same-named .ytd must supply them' }

    if ($Slot) {
        $lim = $SlotLimits[$Slot]
        if ($d.tris -gt $lim.tris) { & $note 'WARN' "tris $($d.tris) above the $Slot budget $($lim.tris)" }
        if ($d.min[2] -lt $lim.zMin -or $d.max[2] -gt $lim.zMax) { & $note 'WARN' "Z range $($d.min[2])..$($d.max[2]) outside $Slot range $($lim.zMin)..$($lim.zMax)" }
        foreach ($b in $lim.bones) { if ($d.bones -notcontains $b) { & $note 'FAIL' "bone $b is missing" } }
    }

    if ($Summary) {
        Write-Output ("{0}: fail={1} warn={2} tris={3} tex={4}" -f $file.Name, $fail, $warn, $d.tris, (($d.textures | ForEach-Object { "$($_.w)x$($_.h) $($_.fmt) s$($_.stride)" }) -join ';'))
    } else {
        $lines | Write-Output
        Write-Output "  RESULT fail=$fail warn=$warn"
    }
    $totalFail += $fail
}
if ($totalFail -gt 0) { exit 1 }
