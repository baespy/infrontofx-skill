Add-Type -AssemblyName System.IO.Compression

$M32 = [uint64]4294967295
$VBase = [uint64]1342177280
$PBase = [uint64]1610612736

function Joaat([string]$s) {
    [uint64]$h = 0
    foreach ($c in $s.ToLowerInvariant().ToCharArray()) {
        $h = ($h + [uint64][int]$c) -band $M32
        $h = ($h + (($h -shl 10) -band $M32)) -band $M32
        $h = $h -bxor ($h -shr 6)
    }
    $h = ($h + (($h -shl 3) -band $M32)) -band $M32
    $h = $h -bxor ($h -shr 11)
    $h = ($h + (($h -shl 15) -band $M32)) -band $M32
    [uint32]$h
}

$shaderByHash = @{}
$namesFile = Join-Path $PSScriptRoot '..\references\shader-names.txt'
if (Test-Path -LiteralPath $namesFile) {
    foreach ($n in [IO.File]::ReadAllLines($namesFile)) {
        $t = $n.Trim()
        if ($t) { $shaderByHash[[string](Joaat $t)] = $t }
    }
}

function Inflate([string]$p) {
    $b = [IO.File]::ReadAllBytes($p)
    if ($b.Length -lt 20 -or [Text.Encoding]::ASCII.GetString($b, 0, 4) -ne 'RSC7') { return $null }
    $ms = New-Object IO.MemoryStream(, $b)
    $ms.Position = 16
    $d = New-Object IO.Compression.DeflateStream($ms, [IO.Compression.CompressionMode]::Decompress)
    $o = New-Object IO.MemoryStream
    $d.CopyTo($o)
    $d.Dispose()
    return , $o.ToArray()
}

function VOff([uint64]$p) { if ($p -ge $VBase -and $p -lt $PBase) { [int64]($p - $VBase) } else { [int64]-1 } }
function U64($r, $o) { [BitConverter]::ToUInt64($r, [int]$o) }
function U32($r, $o) { [BitConverter]::ToUInt32($r, [int]$o) }
function U16($r, $o) { [BitConverter]::ToUInt16($r, [int]$o) }
function F32($r, $o) { [BitConverter]::ToSingle($r, [int]$o) }
function CStr($r, [int64]$o) {
    $e = $o
    while ($e -lt $r.Length -and $r[$e] -ne 0) { $e++ }
    [Text.Encoding]::ASCII.GetString($r, [int]$o, [int]($e - $o))
}

function FormatName([uint32]$f) {
    switch ($f) {
        827611204 { 'DXT1'; break }
        861165636 { 'DXT3'; break }
        894720068 { 'DXT5'; break }
        843666497 { 'ATI2'; break }
        826889281 { 'ATI1'; break }
        540492610 { 'BC7'; break }
        21 { 'A8R8G8B8'; break }
        32 { 'A8B8G8R8'; break }
        50 { 'L8'; break }
        28 { 'A8'; break }
        default { "fmt$f" }
    }
}

function ReadTextures($r, [int64]$dict) {
    $list = @()
    if ($dict -lt 0) { return , $list }
    $ptr = VOff (U64 $r ($dict + 0x30))
    $n = U16 $r ($dict + 0x38)
    if ($ptr -lt 0) { return , $list }
    for ($i = 0; $i -lt $n; $i++) {
        $t = VOff (U64 $r ($ptr + 8 * $i))
        if ($t -lt 0) { continue }
        $np = VOff (U64 $r ($t + 0x28))
        $list += [pscustomobject]@{
            name = if ($np -ge 0) { CStr $r $np } else { '?' }
            w = U16 $r ($t + 0x50)
            h = U16 $r ($t + 0x52)
            stride = U16 $r ($t + 0x56)
            fmt = FormatName (U32 $r ($t + 0x58))
            mips = [int]$r[$t + 0x5D]
        }
    }
    return , $list
}

function ReadDrawable($r) {
    $tris = 0; $verts = 0; $geoms = 0; $indices = 0
    $high = VOff (U64 $r 0x50)
    if ($high -ge 0) {
        $entries = VOff (U64 $r $high)
        $count = U16 $r ($high + 8)
        for ($i = 0; $i -lt $count; $i++) {
            $m = VOff (U64 $r ($entries + 8 * $i))
            if ($m -lt 0) { continue }
            $gl = VOff (U64 $r ($m + 8))
            $gc = U16 $r ($m + 0x10)
            for ($j = 0; $j -lt $gc; $j++) {
                $g = VOff (U64 $r ($gl + 8 * $j))
                if ($g -lt 0) { continue }
                $tris += U32 $r ($g + 0x5C)
                $verts += U16 $r ($g + 0x60)
                $indices += U32 $r ($g + 0x58)
                $geoms++
            }
        }
    }
    $shaders = @(); $textures = @()
    $sg = VOff (U64 $r 0x10)
    if ($sg -ge 0) {
        $textures = ReadTextures $r (VOff (U64 $r ($sg + 8)))
        $sp = VOff (U64 $r ($sg + 0x10))
        $sc = U16 $r ($sg + 0x18)
        for ($i = 0; $i -lt $sc; $i++) {
            $s = VOff (U64 $r ($sp + 8 * $i))
            if ($s -lt 0) { continue }
            $h = [string](U32 $r ($s + 8))
            $shaders += if ($shaderByHash.ContainsKey($h)) { $shaderByHash[$h] } else { '0x{0:x8}' -f [uint32]$h }
        }
    }
    $bones = @()
    $sk = VOff (U64 $r 0x18)
    if ($sk -ge 0) {
        $bp = VOff (U64 $r ($sk + 0x20))
        $bc = U16 $r ($sk + 0x5E)
        for ($i = 0; $i -lt $bc; $i++) {
            $np = VOff (U64 $r ($bp + 0x50 * $i + 0x38))
            $bones += if ($np -ge 0) { CStr $r $np } else { '?' }
        }
    }
    [pscustomobject]@{
        tris = [int]$tris
        verts = [int]$verts
        indices = [int]$indices
        geoms = $geoms
        shaders = @($shaders | Sort-Object -Unique)
        textures = @($textures)
        bones = @($bones)
        min = @((F32 $r 0x30), (F32 $r 0x34), (F32 $r 0x38) | ForEach-Object { [math]::Round($_, 3) })
        max = @((F32 $r 0x40), (F32 $r 0x44), (F32 $r 0x48) | ForEach-Object { [math]::Round($_, 3) })
    }
}
