param(
    [Parameter(Mandatory = $true)][Alias('Out', 'OutPath')][string]$OutFile,
    [ValidateSet('frost', 'bolt', 'drip', 'hearts', 'gothic', 'circuit', 'pixel', 'bubbles', 'nebula', 'tactical', 'oni', 'dragon', 'chains', 'shatter', 'cyber_hud', 'sakura_slash', 'holy_halo')]
    [string]$Preset = 'gothic',
    [string]$Primary = '#d91828',
    [string]$Secondary = '#0a0406',
    [string]$Glow = '#ff3848',
    [int]$Seed = 7,
    [int]$Width = 1920,
    [int]$Height = 1080
)

Add-Type -AssemblyName System.Drawing
$ErrorActionPreference = 'Stop'

if (-not ('ForgeScreenFX' -as [type])) {
    Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

public static class ForgeScreenFX {
    private static double Hash(int x, int y, int seed) {
        int n = x * 374761393 + y * 668265263 + seed * 1442695041;
        n = (n ^ (n >> 13)) * 1274126177;
        return ((n ^ (n >> 16)) & 0x7fffffff) / (double)0x7fffffff;
    }

    private static double ValueNoise(double x, double y, int seed) {
        int ix = (int)Math.Floor(x);
        int iy = (int)Math.Floor(y);
        double fx = x - ix;
        double fy = y - iy;
        double ux = fx * fx * (3.0 - 2.0 * fx);
        double uy = fy * fy * (3.0 - 2.0 * fy);
        double a = Hash(ix, iy, seed);
        double b = Hash(ix + 1, iy, seed);
        double c = Hash(ix, iy + 1, seed);
        double d = Hash(ix + 1, iy + 1, seed);
        return a + (b - a) * ux + (c - a) * uy + (a - b - c + d) * ux * uy;
    }

    private static double Fbm(double x, double y, int seed) {
        double v = 0.0;
        double amp = 0.52;
        double freq = 1.0;
        for (int i = 0; i < 4; i++) {
            v += amp * ValueNoise(x * freq, y * freq, seed + i * 101);
            freq *= 2.07;
            amp *= 0.5;
        }
        return v;
    }

    public static void RenderSmokeVignette(
        Bitmap bmp,
        Color baseCol,
        Color rimCol,
        Color glowCol,
        int maxAlpha,
        double innerClearRadius,
        int seed
    ) {
        int w = bmp.Width;
        int h = bmp.Height;
        BitmapData bd = bmp.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
        int bytes = Math.Abs(bd.Stride) * h;
        byte[] buf = new byte[bytes];
        Marshal.Copy(bd.Scan0, buf, 0, bytes);

        double cx = w * 0.5;
        double cy = h * 0.5;
        double rx = w * 0.5;
        double ry = h * 0.5;

        for (int y = 0; y < h; y++) {
            double dy = (y - cy) / ry;
            int row = y * bd.Stride;
            for (int x = 0; x < w; x++) {
                double dx = (x - cx) / rx;
                // Super-elliptical distance so corners and edges frame 16:9 cleanly
                double ell = Math.Sqrt(dx * dx + dy * dy);
                double box = Math.Max(Math.Abs(dx), Math.Abs(dy));
                double dist = ell * 0.65 + box * 0.35;

                // Keep inner gameplay area 100% transparent!
                if (dist <= innerClearRadius) {
                    continue;
                }

                double nx = x / (double)w * 6.5;
                double ny = y / (double)h * 6.5;
                double smoke = Fbm(nx, ny, seed);
                double detail = Fbm(nx * 2.4 + 3.1, ny * 2.4 - 1.7, seed + 59);

                // Perturb the inner boundary with organic smoke wisps
                double effInner = innerClearRadius + (smoke - 0.5) * 0.14;
                if (dist <= effInner) {
                    continue;
                }

                double t = (dist - effInner) / Math.Max(0.001, (1.12 - effInner));
                if (t > 1.0) t = 1.0;
                double smooth = t * t * (3.0 - 2.0 * t);

                // Billowing smoke alpha
                double smokeMod = 0.72 + 0.38 * smoke;
                int a = (int)Math.Min(255.0, maxAlpha * Math.Pow(smooth, 1.15) * smokeMod);
                if (a <= 0) continue;

                // Inner rim glows with rimCol/glowCol, outer edge deepens to baseCol
                double rimMix = Math.Sin(Math.Min(1.0, t) * Math.PI) * (0.45 + 0.55 * detail);
                double emberMix = Math.Pow(Math.Max(0.0, detail - 0.52) * 2.0, 2.0) * (1.0 - t * 0.5);

                double r = baseCol.R * (1.0 - rimMix) + rimCol.R * rimMix + glowCol.R * emberMix * 0.45;
                double g = baseCol.G * (1.0 - rimMix) + rimCol.G * rimMix + glowCol.G * emberMix * 0.25;
                double b = baseCol.B * (1.0 - rimMix) + rimCol.B * rimMix + glowCol.B * emberMix * 0.25;

                int idx = row + x * 4;
                buf[idx + 0] = (byte)Math.Max(0, Math.Min(255, (int)b));
                buf[idx + 1] = (byte)Math.Max(0, Math.Min(255, (int)g));
                buf[idx + 2] = (byte)Math.Max(0, Math.Min(255, (int)r));
                buf[idx + 3] = (byte)Math.Max((int)buf[idx + 3], a);
            }
        }

        Marshal.Copy(buf, 0, bd.Scan0, bytes);
        bmp.UnlockBits(bd);
    }

    public static void AddSoftGlow(Bitmap bmp, double cx, double cy, double radius, Color col, int peakAlpha) {
        if (radius < 2.0 || peakAlpha <= 0) return;
        int w = bmp.Width;
        int h = bmp.Height;
        int x0 = Math.Max(0, (int)(cx - radius));
        int x1 = Math.Min(w - 1, (int)(cx + radius));
        int y0 = Math.Max(0, (int)(cy - radius));
        int y1 = Math.Min(h - 1, (int)(cy + radius));
        if (x1 <= x0 || y1 <= y0) return;

        BitmapData bd = bmp.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
        int bytes = Math.Abs(bd.Stride) * h;
        byte[] buf = new byte[bytes];
        Marshal.Copy(bd.Scan0, buf, 0, bytes);

        double invR2 = 1.0 / (radius * radius);
        for (int y = y0; y <= y1; y++) {
            double dy2 = (y - cy) * (y - cy);
            int row = y * bd.Stride;
            for (int x = x0; x <= x1; x++) {
                double d2 = ((x - cx) * (x - cx) + dy2) * invR2;
                if (d2 >= 1.0) continue;
                double falloff = 1.0 - d2;
                falloff = falloff * falloff;
                double srcA = (peakAlpha * falloff) / 255.0;
                if (srcA <= 0.002) continue;

                int idx = row + x * 4;
                double dstB = buf[idx + 0];
                double dstG = buf[idx + 1];
                double dstR = buf[idx + 2];
                double dstA = buf[idx + 3] / 255.0;

                double outA = srcA + dstA * (1.0 - srcA);
                if (outA > 0.0) {
                    double outR = (col.R * srcA + dstR * dstA * (1.0 - srcA)) / outA;
                    double outG = (col.G * srcA + dstG * dstA * (1.0 - srcA)) / outA;
                    double outB = (col.B * srcA + dstB * dstA * (1.0 - srcA)) / outA;
                    buf[idx + 0] = (byte)Math.Min(255, (int)outB);
                    buf[idx + 1] = (byte)Math.Min(255, (int)outG);
                    buf[idx + 2] = (byte)Math.Min(255, (int)outR);
                    buf[idx + 3] = (byte)Math.Min(255, (int)(outA * 255.0));
                }
            }
        }

        Marshal.Copy(buf, 0, bd.Scan0, bytes);
        bmp.UnlockBits(bd);
    }
}
'@
}

function ColorOf([string]$Hex, [int]$Alpha = 255) {
    $v = $Hex.TrimStart('#')
    [System.Drawing.Color]::FromArgb($Alpha, [Convert]::ToInt32($v.Substring(0, 2), 16), [Convert]::ToInt32($v.Substring(2, 2), 16), [Convert]::ToInt32($v.Substring(4, 2), 16))
}

function Brush([string]$Hex, [int]$Alpha = 255) {
    New-Object System.Drawing.SolidBrush (ColorOf $Hex $Alpha)
}

function Point([double]$X, [double]$Y) {
    New-Object System.Drawing.PointF ([single]$X), ([single]$Y)
}

$bmp = New-Object System.Drawing.Bitmap $Width, $Height, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
$g.Clear([System.Drawing.Color]::Transparent)
$rng = New-Object System.Random $Seed
$W = [double]$Width
$H = [double]$Height

function Rand([double]$A, [double]$B) { $A + $rng.NextDouble() * ($B - $A) }

function EdgePoint([double]$Band) {
    $side = $rng.Next(4)
    switch ($side) {
        0 { return , @((Rand ($W * 0.06) ($W * 0.94)), (Rand ($H * 0.05) ($H * $Band))) }
        1 { return , @((Rand ($W * 0.06) ($W * 0.94)), (Rand ($H * (1 - $Band)) ($H * 0.95))) }
        2 { return , @((Rand ($W * 0.05) ($W * $Band)), (Rand ($H * 0.06) ($H * 0.94))) }
        default { return , @((Rand ($W * (1 - $Band)) ($W * 0.95)), (Rand ($H * 0.06) ($H * 0.94))) }
    }
}

function Vignette([string]$Hex, [int]$Alpha, [double]$Inner) {
    $clearR = [Math]::Max(0.56, $Inner)
    [ForgeScreenFX]::RenderSmokeVignette($bmp, (ColorOf $Hex 255), (ColorOf $Primary 255), (ColorOf $Glow 255), $Alpha, $clearR, $Seed)
}

function Glow([double]$X, [double]$Y, [double]$R, [string]$Hex, [int]$Alpha) {
    [ForgeScreenFX]::AddSoftGlow($bmp, $X, $Y, $R, (ColorOf $Hex 255), $Alpha)
}

function Polygon([double[]]$Coords, [string]$Hex, [int]$Alpha) {
    $pts = for ($i = 0; $i -lt $Coords.Length; $i += 2) { Point $Coords[$i] $Coords[$i + 1] }
    $b = Brush $Hex $Alpha
    $g.FillPolygon($b, [System.Drawing.PointF[]]$pts)
    $b.Dispose()
}

function Sparkle([double]$X, [double]$Y, [double]$S, [string]$Hex, [int]$Alpha) {
    Glow $X $Y ($S * 1.6) $Hex ([int]($Alpha * 0.55))
    $k = $S * 0.14
    Polygon @($X, ($Y - $S), ($X + $k), ($Y - $k), ($X + $S), $Y, ($X + $k), ($Y + $k), $X, ($Y + $S), ($X - $k), ($Y + $k), ($X - $S), $Y, ($X - $k), ($Y - $k)) $Hex $Alpha
}

function Heart([double]$X, [double]$Y, [double]$S, [string]$Hex, [int]$Alpha) {
    $c = New-Object System.Collections.Generic.List[double]
    for ($i = 0; $i -lt 36; $i++) {
        $t = $i / 36 * 2 * [Math]::PI
        $c.Add($X + $S * 16 * [Math]::Pow([Math]::Sin($t), 3) / 17)
        $c.Add($Y - $S * (13 * [Math]::Cos($t) - 5 * [Math]::Cos(2 * $t) - 2 * [Math]::Cos(3 * $t) - [Math]::Cos(4 * $t)) / 17)
    }
    Polygon $c.ToArray() $Hex $Alpha
}

function Cross([double]$X, [double]$Y, [double]$S, [string]$Hex, [int]$Alpha) {
    $n = @(-0.15, -0.43, -0.32, -1, 0, -0.86, 0.32, -1, 0.15, -0.43, 0.72, -0.6, 0.6, -0.28, 0.72, 0.04, 0.15, -0.13, 0.32, 1, 0, 0.86, -0.32, 1, -0.15, -0.13, -0.72, 0.04, -0.6, -0.28, -0.72, -0.6)
    $c = for ($i = 0; $i -lt $n.Length; $i += 2) { $X + $n[$i] * $S; $Y + $n[$i + 1] * $S }
    Polygon ([double[]]$c) $Hex $Alpha
}

function Bolt([double]$X0, [double]$Y0, [double]$X1, [double]$Y1, [string]$Hex, [double]$Thick) {
    $pts = New-Object System.Collections.Generic.List[System.Drawing.PointF]
    $steps = 11
    $dx = $X1 - $X0
    $dy = $Y1 - $Y0
    $len = [Math]::Sqrt($dx * $dx + $dy * $dy)
    $amp = $len * 0.05
    for ($i = 0; $i -le $steps; $i++) {
        $u = $i / $steps
        $j = if ($i -eq 0) { 0 } else { Rand (-1) 1 }
        $pts.Add((Point ($X0 + $dx * $u - $dy / $len * $j * $amp) ($Y0 + $dy * $u + $dx / $len * $j * $amp)))
    }
    foreach ($layer in @(@(($Thick * 9), 34), @(($Thick * 4), 90), @(($Thick * 1.6), 220))) {
        $pen = New-Object System.Drawing.Pen (ColorOf $Hex ([int]$layer[1])), ([single]$layer[0])
        $pen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
        $g.DrawLines($pen, $pts.ToArray())
        $pen.Dispose()
    }
    $core = New-Object System.Drawing.Pen ([System.Drawing.Color]::White), ([single]($Thick * 0.7))
    $g.DrawLines($core, $pts.ToArray())
    $core.Dispose()
}

function Petal([double]$X, [double]$Y, [double]$S, [double]$Rot, [string]$Hex, [int]$Alpha) {
    $shape = @(0, -1, 0.58, -0.52, 0.74, 0.12, 0.36, 0.84, 0, 0.54, -0.36, 0.84, -0.74, 0.12, -0.58, -0.52)
    $c = for ($i = 0; $i -lt $shape.Length; $i += 2) {
        $px = $shape[$i] * $S
        $py = $shape[$i + 1] * $S
        $X + $px * [Math]::Cos($Rot) - $py * [Math]::Sin($Rot)
        $Y + $px * [Math]::Sin($Rot) + $py * [Math]::Cos($Rot)
    }
    Polygon ([double[]]$c) '#220308' ([int]($Alpha * 0.65))
    $c2 = for ($i = 0; $i -lt $shape.Length; $i += 2) {
        $px = $shape[$i] * $S * 0.90
        $py = ($shape[$i + 1] - 0.05) * $S * 0.90
        $X + $px * [Math]::Cos($Rot) - $py * [Math]::Sin($Rot)
        $Y + $px * [Math]::Sin($Rot) + $py * [Math]::Cos($Rot)
    }
    Polygon ([double[]]$c2) $Hex $Alpha
    $c3 = for ($i = 0; $i -lt $shape.Length; $i += 2) {
        $px = $shape[$i] * $S * 0.48
        $py = ($shape[$i + 1] - 0.12) * $S * 0.48
        $X + $px * [Math]::Cos($Rot) - $py * [Math]::Sin($Rot)
        $Y + $px * [Math]::Sin($Rot) + $py * [Math]::Cos($Rot)
    }
    Polygon ([double[]]$c3) '#ffccd4' ([int]($Alpha * 0.55))
}

function CurvedSlash([double]$X0, [double]$Y0, [double]$X1, [double]$Y1, [double]$Curve, [double]$MaxWidth, [string]$ColOuter, [string]$ColMid, [string]$ColCore) {
    $dx = $X1 - $X0
    $dy = $Y1 - $Y0
    $len = [Math]::Sqrt($dx * $dx + $dy * $dy)
    if ($len -lt 10) { return }
    $nx = -$dy / $len
    $ny = $dx / $len
    $mx = ($X0 + $X1) * 0.5 + $nx * $Curve
    $my = ($Y0 + $Y1) * 0.5 + $ny * $Curve

    $steps = 28
    foreach ($layer in @(
        @($ColOuter, 2.25, 65, 0.0),
        @($ColMid,   1.35, 210, 0.0),
        @('#ff5260', 0.72, 245, 0.15),
        @($ColCore,  0.28, 250, 0.25)
    )) {
        $hex = $layer[0]
        $wScale = [double]$layer[1]
        $alpha = [int]$layer[2]
        $shift = [double]$layer[3] * $MaxWidth
        $leftPts = New-Object System.Collections.Generic.List[System.Drawing.PointF]
        $rightPts = New-Object System.Collections.Generic.List[System.Drawing.PointF]

        for ($i = 0; $i -le $steps; $i++) {
            $t = $i / [double]$steps
            $it = 1.0 - $t
            $bx = $it * $it * $X0 + 2 * $it * $t * $mx + $t * $t * $X1
            $by = $it * $it * $Y0 + 2 * $it * $t * $my + $t * $t * $Y1
            $tx = 2 * $it * ($mx - $X0) + 2 * $t * ($X1 - $mx)
            $ty = 2 * $it * ($my - $Y0) + 2 * $t * ($Y1 - $my)
            $tl = [Math]::Max(0.001, [Math]::Sqrt($tx * $tx + $ty * $ty))
            $px = -$ty / $tl
            $py = $tx / $tl

            $profile = [Math]::Sin($t * [Math]::PI) * [Math]::Pow(1.0 - $t * 0.22, 0.6)
            $hw = $MaxWidth * $wScale * $profile
            $leftPts.Add((Point ($bx + $px * ($hw + $shift)) ($by + $py * ($hw + $shift))))
            $rightPts.Add((Point ($bx - $px * ($hw * 0.68 - $shift)) ($by - $py * ($hw * 0.68 - $shift))))
        }
        $rightPts.Reverse()
        $leftPts.AddRange($rightPts)
        $b = Brush $hex $alpha
        $g.FillPolygon($b, $leftPts.ToArray())
        $b.Dispose()
    }

    # Blood droplets & golden sparks flung along the slash arc
    for ($d = 0; $d -lt 14; $d++) {
        $t = Rand 0.12 0.88
        $it = 1.0 - $t
        $bx = $it * $it * $X0 + 2 * $it * $t * $mx + $t * $t * $X1
        $by = $it * $it * $Y0 + 2 * $it * $t * $my + $t * $t * $Y1
        $offX = Rand (-$MaxWidth * 2.8) ($MaxWidth * 2.8)
        $offY = Rand (-$MaxWidth * 2.8) ($MaxWidth * 2.8)
        $r = Rand 2.2 6.8
        $col = if ($d % 4 -eq 0) { '#ffd26a' } else { $ColMid }
        $sb = Brush $col (Rand 165 245)
        $g.FillEllipse($sb, [single]($bx + $offX - $r * 0.5), [single]($by + $offY - $r * 0.5), [single]$r, [single]($r * (Rand 0.9 1.7)))
        $sb.Dispose()
    }
}

function Slash([double]$X0, [double]$Y0, [double]$Sx, [double]$Sy, [double]$Offset, [double]$Len, [double]$Width) {
    $bx = $X0 + $Sx * ($Offset + 45)
    $by = $Y0 + $Sy * 32
    $tx = $bx + $Sx * $Len * 0.66
    $ty = $by + $Sy * $Len * 0.74
    $curve = -$Sx * $Sy * ($Len * 0.16)
    CurvedSlash $bx $by $tx $ty $curve $Width '#48040a' $Primary '#fff4e4'
}

function DrawOniMaskCrest([double]$Cx, [double]$Cy, [double]$Scale) {
    Glow $Cx $Cy (210 * $Scale) '#a80c18' 125
    Glow $Cx ($Cy - 18 * $Scale) (120 * $Scale) '#ff2c3c' 95

    # Ornate dark crimson & obsidian Oni Mask forehead shield
    Polygon @(
        ($Cx - 118 * $Scale), ($Cy - 20 * $Scale),
        ($Cx - 85 * $Scale),  ($Cy - 52 * $Scale),
        ($Cx - 32 * $Scale),  ($Cy - 44 * $Scale),
        $Cx,                  ($Cy - 58 * $Scale),
        ($Cx + 32 * $Scale),  ($Cy - 44 * $Scale),
        ($Cx + 85 * $Scale),  ($Cy - 52 * $Scale),
        ($Cx + 118 * $Scale), ($Cy - 20 * $Scale),
        ($Cx + 96 * $Scale),  ($Cy + 28 * $Scale),
        ($Cx + 42 * $Scale),  ($Cy + 42 * $Scale),
        $Cx,                  ($Cy + 28 * $Scale),
        ($Cx - 42 * $Scale),  ($Cy + 42 * $Scale),
        ($Cx - 96 * $Scale),  ($Cy + 28 * $Scale)
    ) '#140609' 240

    Polygon @(
        ($Cx - 108 * $Scale), ($Cy - 18 * $Scale),
        ($Cx - 78 * $Scale),  ($Cy - 45 * $Scale),
        $Cx,                  ($Cy - 50 * $Scale),
        ($Cx + 78 * $Scale),  ($Cy - 45 * $Scale),
        ($Cx + 108 * $Scale), ($Cy - 18 * $Scale),
        ($Cx + 86 * $Scale),  ($Cy + 22 * $Scale),
        ($Cx + 38 * $Scale),  ($Cy + 34 * $Scale),
        $Cx,                  ($Cy + 20 * $Scale),
        ($Cx - 38 * $Scale),  ($Cy + 34 * $Scale),
        ($Cx - 86 * $Scale),  ($Cy + 22 * $Scale)
    ) '#5c0c14' 235

    # Sculpted Curved Golden Oni Horns (Left & Right)
    foreach ($side in @(-1.0, 1.0)) {
        # Outer dark bronze shadow horn
        Polygon @(
            ($Cx + $side * 58 * $Scale),  ($Cy - 24 * $Scale),
            ($Cx + $side * 98 * $Scale),  ($Cy - 44 * $Scale),
            ($Cx + $side * 145 * $Scale), ($Cy - 72 * $Scale),
            ($Cx + $side * 172 * $Scale), ($Cy - 98 * $Scale),
            ($Cx + $side * 148 * $Scale), ($Cy - 54 * $Scale),
            ($Cx + $side * 116 * $Scale), ($Cy - 20 * $Scale),
            ($Cx + $side * 76 * $Scale),  ($Cy - 6 * $Scale)
        ) '#5a360c' 245

        # Main antique gold horn body
        Polygon @(
            ($Cx + $side * 62 * $Scale),  ($Cy - 24 * $Scale),
            ($Cx + $side * 98 * $Scale),  ($Cy - 42 * $Scale),
            ($Cx + $side * 142 * $Scale), ($Cy - 69 * $Scale),
            ($Cx + $side * 168 * $Scale), ($Cy - 95 * $Scale),
            ($Cx + $side * 142 * $Scale), ($Cy - 56 * $Scale),
            ($Cx + $side * 108 * $Scale), ($Cy - 24 * $Scale),
            ($Cx + $side * 74 * $Scale),  ($Cy - 10 * $Scale)
        ) '#d99b32' 245

        # Specular gold highlight ridge along horn
        Polygon @(
            ($Cx + $side * 68 * $Scale),  ($Cy - 26 * $Scale),
            ($Cx + $side * 104 * $Scale), ($Cy - 44 * $Scale),
            ($Cx + $side * 164 * $Scale), ($Cy - 92 * $Scale),
            ($Cx + $side * 134 * $Scale), ($Cy - 58 * $Scale),
            ($Cx + $side * 92 * $Scale),  ($Cy - 30 * $Scale)
        ) '#ffe394' 220

        # Fierce scowling golden brow ridge
        Polygon @(
            ($Cx + $side * 10 * $Scale), ($Cy - 4 * $Scale),
            ($Cx + $side * 44 * $Scale), ($Cy - 24 * $Scale),
            ($Cx + $side * 86 * $Scale), ($Cy - 18 * $Scale),
            ($Cx + $side * 64 * $Scale), ($Cy - 6 * $Scale),
            ($Cx + $side * 22 * $Scale), ($Cy + 2 * $Scale)
        ) '#e0a43c' 240

        # Glowing Demon Eye Socket + Crimson Flame Trail
        $ex = $Cx + $side * 46 * $Scale
        $ey = $Cy + 6 * $Scale
        Glow $ex $ey (46 * $Scale) '#ff1828' 185

        # Flame trail sweeping outward from eye
        Polygon @(
            ($ex + $side * 12 * $Scale), ($ey - 4 * $Scale),
            ($ex + $side * 58 * $Scale), ($ey - 22 * $Scale),
            ($ex + $side * 96 * $Scale), ($ey - 38 * $Scale),
            ($ex + $side * 62 * $Scale), ($ey - 8 * $Scale),
            ($ex + $side * 24 * $Scale), ($ey + 6 * $Scale)
        ) '#ff2e3e' 195

        # Eye sclera (blood scarlet) & white-gold slit core
        Polygon @(
            ($Cx + $side * 20 * $Scale), ($Cy + 8 * $Scale),
            ($Cx + $side * 42 * $Scale), ($Cy - 4 * $Scale),
            ($Cx + $side * 74 * $Scale), ($Cy + 2 * $Scale),
            ($Cx + $side * 52 * $Scale), ($Cy + 16 * $Scale)
        ) '#ff1e2e' 250

        Polygon @(
            ($Cx + $side * 30 * $Scale), ($Cy + 7 * $Scale),
            ($Cx + $side * 45 * $Scale), ($Cy + 0 * $Scale),
            ($Cx + $side * 64 * $Scale), ($Cy + 4 * $Scale),
            ($Cx + $side * 48 * $Scale), ($Cy + 12 * $Scale)
        ) '#fff2c8' 250
    }

    # Center Forehead Blood Ruby Diamond & Gold Frame
    Polygon @(
        $Cx,                  ($Cy - 42 * $Scale),
        ($Cx + 14 * $Scale),  ($Cy - 22 * $Scale),
        $Cx,                  ($Cy - 2 * $Scale),
        ($Cx - 14 * $Scale),  ($Cy - 22 * $Scale)
    ) '#e5a83b' 245
    Polygon @(
        $Cx,                  ($Cy - 36 * $Scale),
        ($Cx + 9 * $Scale),   ($Cy - 22 * $Scale),
        $Cx,                  ($Cy - 8 * $Scale),
        ($Cx - 9 * $Scale),   ($Cy - 22 * $Scale)
    ) '#ff1c2d' 250
}

function DrawOniBottomSeal([double]$Cx, [double]$Cy, [double]$Scale) {
    Glow $Cx $Cy (240 * $Scale) '#960a16' 135

    # Horizontal Blood Katana Slash behind the seal
    CurvedSlash ($Cx - 380 * $Scale) ($Cy + 8 * $Scale) ($Cx + 380 * $Scale) ($Cy - 6 * $Scale) (-12 * $Scale) (14 * $Scale) '#3c0408' '#d91828' '#fff0dc'

    # Left & Right Golden Oni Lower Fangs / Tusks framing the kanji
    foreach ($side in @(-1.0, 1.0)) {
        Polygon @(
            ($Cx + $side * 110 * $Scale), ($Cy + 26 * $Scale),
            ($Cx + $side * 148 * $Scale), ($Cy - 38 * $Scale),
            ($Cx + $side * 165 * $Scale), ($Cy + 8 * $Scale),
            ($Cx + $side * 136 * $Scale), ($Cy + 38 * $Scale)
        ) '#d99b32' 235
        Polygon @(
            ($Cx + $side * 116 * $Scale), ($Cy + 22 * $Scale),
            ($Cx + $side * 146 * $Scale), ($Cy - 32 * $Scale),
            ($Cx + $side * 152 * $Scale), ($Cy + 4 * $Scale)
        ) '#ffe394' 210
    }

    $fontName = 'Yu Gothic'
    if (-not ([System.Drawing.FontFamily]::Families | Where-Object { $_.Name -eq $fontName })) { $fontName = 'MS Gothic' }
    $font = New-Object System.Drawing.Font($fontName, [single](118 * $Scale), [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAlias
    $kanji = [string][char]0x9B3C + [string][char]0x5F71
    $sf = New-Object System.Drawing.StringFormat
    $sf.Alignment = [System.Drawing.StringAlignment]::Center
    $sf.LineAlignment = [System.Drawing.StringAlignment]::Center

    foreach ($off in @(@(-4, 4), @(4, 4), @(-4, -4), @(4, -4), @(0, 6))) {
        $sb = Brush '#090305' 220
        $g.DrawString($kanji, $font, $sb, (Point ($Cx + $off[0]) ($Cy + $off[1])), $sf)
        $sb.Dispose()
    }
    $gb = Brush '#d99b32' 215
    $g.DrawString($kanji, $font, $gb, (Point ($Cx + 2) ($Cy + 2)), $sf)
    $gb.Dispose()

    $kb = Brush '#ff2e3e' 240
    $g.DrawString($kanji, $font, $kb, (Point $Cx $Cy), $sf)
    $kb.Dispose()

    $sf.Dispose()
    $font.Dispose()
}

function Scatter([int]$Count, [double]$Band, [scriptblock]$Draw) {
    for ($i = 0; $i -lt $Count; $i++) {
        $p = EdgePoint $Band
        & $Draw $p[0] $p[1]
    }
}

switch ($Preset) {
    'gothic' {
        Vignette $Secondary 235 0.60
        Scatter 26 0.16 { param($x, $y) Sparkle $x $y (Rand 10 42) $Primary 235 }
        foreach ($c in @(@(150, 170), @(($W - 150), 170), @(150, ($H - 170)), @(($W - 150), ($H - 170)))) {
            Glow $c[0] $c[1] 170 $Glow 90
            Cross $c[0] $c[1] 110 $Primary 240
        }
    }
    'bolt' {
        Vignette $Secondary 225 0.58
        for ($i = 0; $i -lt 10; $i++) {
            $a = EdgePoint 0.04
            $bx = $a[0] + ($W / 2 - $a[0]) * (Rand 0.25 0.42)
            $by = $a[1] + ($H / 2 - $a[1]) * (Rand 0.25 0.42)
            Bolt $a[0] $a[1] $bx $by $Glow (Rand 2.6 5.5)
        }
    }
    'drip' {
        Vignette $Secondary 185 0.58
        $b = Brush $Primary 245
        $x = -20.0
        while ($x -lt $W) {
            $dripW = Rand 46 130
            $len = Rand 50 220
            $g.FillRectangle($b, [single]$x, [single]-10, [single]$dripW, [single]($len + 10))
            $g.FillEllipse($b, [single]$x, [single]($len - $dripW * 0.6), [single]$dripW, [single]($dripW * 1.2))
            $x += $dripW * 0.86
        }
        $b.Dispose()
        Scatter 90 0.20 { param($px, $py) $s = Rand 3 22; $sb = Brush $Primary 230; $g.FillEllipse($sb, [single]$px, [single]$py, [single]$s, [single]$s); $sb.Dispose() }
    }
    'hearts' {
        Vignette $Primary 185 0.58
        Scatter 44 0.18 { param($x, $y) Heart $x $y (Rand 26 92) $Glow (Rand 150 245) }
        Scatter 24 0.20 { param($x, $y) Sparkle $x $y (Rand 10 30) '#ffffff' 235 }
    }
    'frost' {
        Vignette $Primary 185 0.58
        Scatter 40 0.18 { param($x, $y)
            $s = Rand 22 72
            $pen = New-Object System.Drawing.Pen (ColorOf $Glow 225), ([single](Rand 2 4))
            for ($k = 0; $k -lt 3; $k++) {
                $a = $k * [Math]::PI / 3
                $g.DrawLine($pen, [single]($x - [Math]::Cos($a) * $s), [single]($y - [Math]::Sin($a) * $s), [single]($x + [Math]::Cos($a) * $s), [single]($y + [Math]::Sin($a) * $s))
            }
            $pen.Dispose()
        }
    }
    'circuit' {
        Vignette $Secondary 220 0.58
        $m = 44.0
        $pen = New-Object System.Drawing.Pen (ColorOf $Glow 235), ([single]3)
        $g.DrawLines($pen, [System.Drawing.PointF[]]@((Point $m ($H * 0.3)), (Point $m $m), (Point ($W * 0.22) $m)))
        $g.DrawLines($pen, [System.Drawing.PointF[]]@((Point ($W - $m) ($H * 0.7)), (Point ($W - $m) ($H - $m)), (Point ($W * 0.78) ($H - $m))))
        $g.DrawLines($pen, [System.Drawing.PointF[]]@((Point ($W * 0.78) $m), (Point ($W - $m) $m), (Point ($W - $m) ($H * 0.3))))
        $g.DrawLines($pen, [System.Drawing.PointF[]]@((Point $m ($H * 0.7)), (Point $m ($H - $m)), (Point ($W * 0.22) ($H - $m))))
        $pen.Dispose()
        Scatter 60 0.12 { param($x, $y) $s = Rand 6 28; $b = Brush $Glow (Rand 90 230); $g.FillRectangle($b, [single]$x, [single]$y, [single]$s, [single]($s * 0.4)); $b.Dispose() }
    }
    'pixel' {
        Vignette $Secondary 180 0.58
        $cell = 40
        for ($x = 0; $x -lt $Width; $x += $cell) {
            for ($y = 0; $y -lt $Height; $y += $cell) {
                $edge = [Math]::Min([Math]::Min($x, $Width - $x) / $W, [Math]::Min($y, $Height - $y) / $H)
                if ($rng.NextDouble() -lt (0.85 - $edge * 7.5)) {
                    $hex = if ($rng.Next(3) -eq 0) { $Glow } else { $Primary }
                    $b = Brush $hex (Rand 150 245)
                    $g.FillRectangle($b, $x, $y, $cell - 3, $cell - 3)
                    $b.Dispose()
                }
            }
        }
    }
    'bubbles' {
        Vignette $Secondary 175 0.58
        Scatter 44 0.20 { param($x, $y)
            $s = Rand 18 92
            Glow $x $y ($s * 1.2) $Glow 46
            $pen = New-Object System.Drawing.Pen (ColorOf $Primary 215), ([single]3)
            $g.DrawEllipse($pen, [single]($x - $s / 2), [single]($y - $s / 2), [single]$s, [single]$s)
            $pen.Dispose()
            $b = Brush '#ffffff' 225
            $g.FillEllipse($b, [single]($x - $s * 0.26), [single]($y - $s * 0.3), [single]($s * 0.18), [single]($s * 0.12))
            $b.Dispose()
        }
    }
    'nebula' {
        Vignette $Secondary 235 0.58
        Scatter 26 0.14 { param($x, $y) Glow $x $y (Rand 120 260) $Glow (Rand 40 96) }
        Scatter 110 0.20 { param($x, $y) Sparkle $x $y (Rand 3 16) '#ffffff' 235 }
        Scatter 18 0.18 { param($x, $y) Sparkle $x $y (Rand 20 46) $Primary 240 }
    }
    'oni' {
        # 1. Volumetric Blood-Smoke & Obsidian Vignette (Center 58% is 100% transparent!)
        Vignette $Secondary 248 0.58

        # 2. Corner Curved Katana Blood-Crescent Slashes (3 sweeping arcs per corner)
        foreach ($c in @(@(0, 0, 1, 1), @($W, 0, -1, 1), @(0, $H, 1, -1), @($W, $H, -1, -1))) {
            for ($k = 0; $k -lt 3; $k++) {
                Slash $c[0] $c[1] $c[2] $c[3] (42 + $k * 64) (465 - $k * 75) (19 - $k * 3.5)
            }
        }

        # 3. Drifting 3D Blood Sakura Petals & Golden Fire Embers along the border
        Scatter 54 0.18 { param($x, $y) Petal $x $y (Rand 13 30) (Rand 0 6.28) $Glow (Rand 175 245) }
        Scatter 32 0.20 { param($x, $y) Petal $x $y (Rand 9 20) (Rand 0 6.28) $Primary (Rand 165 235) }
        Scatter 115 0.15 {
            param($x, $y)
            $s = Rand 2.5 6.5
            Glow $x $y ($s * 3.2) '#ff6a28' 115
            $b = Brush '#ffd878' 245
            $g.FillEllipse($b, [single]($x - $s / 2), [single]($y - $s / 2), [single]$s, [single]$s)
            $b.Dispose()
        }

        # 4. Top-Center Sculpted Oni Hannya Demon Mask Crest (Safe zone Y = 11%, rendered in foreground)
        DrawOniMaskCrest ($W * 0.5) ($H * 0.112) 1.08

        # 5. Bottom-Center Oni Tusks & 鬼影 Seal (Safe zone Y = 87.5%, rendered in foreground)
        DrawOniBottomSeal ($W * 0.5) ($H * 0.875) 0.96
    }
    'tactical' {
        Vignette $Secondary 200 0.58
        $m = 56.0
        $L = 180.0
        $pen = New-Object System.Drawing.Pen (ColorOf $Primary 235), ([single]7)
        foreach ($c in @(@($m, $m, 1, 1), @(($W - $m), $m, -1, 1), @($m, ($H - $m), 1, -1), @(($W - $m), ($H - $m), -1, -1))) {
            $g.DrawLines($pen, [System.Drawing.PointF[]]@((Point ($c[0] + $L * $c[2]) $c[1]), (Point $c[0] $c[1]), (Point $c[0] ($c[1] + $L * $c[3]))))
        }
        $pen.Dispose()
        for ($i = 0; $i -lt 16; $i++) {
            Polygon @((60 + $i * 44), ($H - 30), (86 + $i * 44), ($H - 30), (108 + $i * 44), ($H - 12), (82 + $i * 44), ($H - 12)) $Glow 220
        }
    }
    'dragon' {
        Vignette $Secondary 245 0.58
        foreach ($c in @(@(0, 0, 1, 1), @($W, 0, -1, 1), @(0, $H, 1, -1), @($W, $H, -1, -1))) {
            for ($k = 0; $k -lt 4; $k++) {
                Slash $c[0] $c[1] $c[2] $c[3] (52 + $k * 58) (490 - $k * 78) (22 - $k * 4)
            }
        }
        Scatter 55 0.16 { param($x, $y)
            $r = Rand 18 44
            $pen = New-Object System.Drawing.Pen (ColorOf $Primary (Rand 140 230)), ([single]2.5)
            $g.DrawArc($pen, [single]($x - $r), [single]($y - $r), [single]($r * 2), [single]($r * 1.4), 20, 140)
            $pen.Dispose()
        }
        Scatter 90 0.14 { param($x, $y) $s = Rand 2 7; Glow $x $y ($s * 3.2) $Glow 95; $b = Brush $Primary 235; $g.FillEllipse($b, [single]($x - $s / 2), [single]($y - $s / 2), [single]$s, [single]$s); $b.Dispose() }
    }
    'chains' {
        Vignette $Secondary 240 0.58
        foreach ($c in @(@(0, ($H * 0.28), ($W * 0.32), 0), @(($W * 0.68), 0, $W, ($H * 0.28)), @(0, ($H * 0.72), ($W * 0.32), $H), @(($W * 0.68), $H, $W, ($H * 0.72)))) {
            $dx = $c[2] - $c[0]; $dy = $c[3] - $c[1]
            $dist = [Math]::Sqrt($dx * $dx + $dy * $dy)
            $ang = [Math]::Atan2($dy, $dx) * 180.0 / [Math]::PI
            $links = [int]($dist / 36)
            for ($i = 0; $i -le $links; $i++) {
                $u = $i / [double]$links
                $lx = $c[0] + $dx * $u
                $ly = $c[1] + $dy * $u
                $state = $g.Save()
                $g.TranslateTransform([single]$lx, [single]$ly)
                $g.RotateTransform([single]$ang)
                $penG = New-Object System.Drawing.Pen (ColorOf $Glow 75), ([single]11)
                $penM = New-Object System.Drawing.Pen (ColorOf $Primary 235), ([single]5)
                if ($i % 2 -eq 0) {
                    $g.DrawEllipse($penG, -22, -10, 44, 20)
                    $g.DrawEllipse($penM, -22, -10, 44, 20)
                } else {
                    $g.DrawLine($penG, -18, 0, 18, 0)
                    $g.DrawLine($penM, -18, 0, 18, 0)
                }
                $penG.Dispose(); $penM.Dispose()
                $g.Restore($state)
            }
        }
        Scatter 32 0.16 { param($x, $y) Sparkle $x $y (Rand 8 28) $Glow 220 }
    }
    'shatter' {
        Vignette $Secondary 230 0.58
        for ($i = 0; $i -lt 18; $i++) {
            $p = EdgePoint 0.04
            $tx = $p[0] + ($W / 2 - $p[0]) * (Rand 0.22 0.38)
            $ty = $p[1] + ($H / 2 - $p[1]) * (Rand 0.22 0.38)
            Bolt $p[0] $p[1] $tx $ty $Glow (Rand 1.8 3.6)
            $mx = ($p[0] + $tx) * 0.5
            $my = ($p[1] + $ty) * 0.5
            Bolt $mx $my ($mx + (Rand -110 110)) ($my + (Rand -110 110)) $Primary 1.6
        }
        Scatter 48 0.16 { param($x, $y)
            $r = Rand 10 38
            $a1 = Rand 0 2.0; $a2 = $a1 + (Rand 1.5 2.4); $a3 = $a2 + (Rand 1.5 2.4)
            Polygon @(($x + $r * [Math]::Cos($a1)), ($y + $r * [Math]::Sin($a1)), ($x + $r * [Math]::Cos($a2)), ($y + $r * [Math]::Sin($a2)), ($x + $r * [Math]::Cos($a3)), ($y + $r * [Math]::Sin($a3))) $Primary (Rand 90 195)
        }
    }
    'cyber_hud' {
        Vignette $Secondary 215 0.58
        $m = 48.0
        $pen = New-Object System.Drawing.Pen (ColorOf $Glow 235), ([single]4)
        $penThin = New-Object System.Drawing.Pen (ColorOf $Primary 165), ([single]1.5)
        foreach ($c in @(@($m, $m, 1, 1), @(($W - $m), $m, -1, 1), @($m, ($H - $m), 1, -1), @(($W - $m), ($H - $m), -1, -1))) {
            $g.DrawLines($pen, [System.Drawing.PointF[]]@((Point ($c[0] + 240 * $c[2]) $c[1]), (Point ($c[0] + 28 * $c[2]) $c[1]), (Point $c[0] ($c[1] + 28 * $c[3])), (Point $c[0] ($c[1] + 180 * $c[3]))))
            for ($k = 0; $k -lt 8; $k++) {
                $bx = $c[0] + (50 + $k * 22) * $c[2]
                $by = $c[1] + 10 * $c[3]
                $b = Brush $Glow (220 - $k * 20)
                $g.FillRectangle($b, [single]([Math]::Min($bx, $bx + 14 * $c[2])), [single]([Math]::Min($by, $by + 6 * $c[3])), 14, 6)
                $b.Dispose()
            }
        }
        for ($y = 0; $y -lt $Height; $y += 16) {
            if ($y -lt 140 -or $y -gt ($Height - 140)) {
                $g.DrawLine($penThin, 0, $y, $Width, $y)
            }
        }
        $pen.Dispose(); $penThin.Dispose()
    }
    'sakura_slash' {
        Vignette $Secondary 230 0.58
        foreach ($c in @(@(0, 0, 1, 1), @($W, 0, -1, 1), @(0, $H, 1, -1), @($W, $H, -1, -1))) {
            for ($k = 0; $k -lt 2; $k++) {
                Slash $c[0] $c[1] $c[2] $c[3] (64 + $k * 72) (460 - $k * 90) (18 - $k * 4)
            }
        }
        Scatter 75 0.18 { param($x, $y) Petal $x $y (Rand 12 36) (Rand 0 6.28) $Glow (Rand 165 245) }
        Scatter 45 0.20 { param($x, $y) Petal $x $y (Rand 8 22) (Rand 0 6.28) $Primary (Rand 160 235) }
        Scatter 30 0.16 { param($x, $y) Sparkle $x $y (Rand 8 22) '#ffffff' 220 }
    }
    'holy_halo' {
        Vignette $Primary 185 0.58
        foreach ($c in @(@(0, 0), @($W, 0), @(0, $H), @($W, $H))) {
            Glow $c[0] $c[1] 340 $Glow 95
            $pen = New-Object System.Drawing.Pen (ColorOf $Glow 210), ([single]3)
            $g.DrawEllipse($pen, [single]($c[0] - 220), [single]($c[1] - 220), 440, 440)
            $g.DrawEllipse($pen, [single]($c[0] - 260), [single]($c[1] - 260), 520, 520)
            $pen.Dispose()
        }
        Scatter 42 0.18 { param($x, $y) Sparkle $x $y (Rand 14 48) $Glow 240 }
        Scatter 28 0.16 { param($x, $y) Cross $x $y (Rand 28 64) '#ffffff' 215 }
    }
}

$g.Dispose()
$dir = Split-Path -Parent $OutFile
if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
$bmp.Save($OutFile, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
$len = (Get-Item -LiteralPath $OutFile).Length
"screen: $OutFile ($([int]($len / 1KB)) KB, $Preset)"
