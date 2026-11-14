<#
  Keep one person out of a cut-out that holds several (couple photos, group shots).
  Run cutout.ps1 -NoCrop first, then:
    isolate.ps1 -In g2.png -Out boy.png -Polygon "0.50,0.08 0.80,0.07 1,0.4 1,1 0.60,1 0.55,0.5 0.52,0.2" [-Clear "0.08,0.28,0.28,0.52"] [-Flip]
  -Polygon  normalized x,y points (0-1 of the image) around the person to keep; the edge is feathered.
            Run the cut along the other person's hair or clothing edge, never through a face.
  -Clear    "x0,y0,x1,y1;..." boxes where near-white leftovers (background pockets enclosed by an arm) are removed.
  -WhiteMin brightness (0-255) a pixel must exceed in every channel to be cleared inside -Clear boxes (default 238; pale skin is lower).
  -Feather  polygon edge softness in pixels (default 5).
  Output is cropped to the kept person. Open the .check.jpg (magenta = transparent) before using it.
#>
param(
  [Parameter(Mandatory = $true)][string]$In,
  [Parameter(Mandatory = $true)][string]$Out,
  [Parameter(Mandatory = $true)][string]$Polygon,
  [string]$Clear = '',
  [int]$Feather = 5,
  [int]$Max = 2400,
  [int]$WhiteMin = 238,
  [switch]$Flip
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System; using System.Drawing; using System.Drawing.Drawing2D; using System.Drawing.Imaging; using System.Runtime.InteropServices;
public static class PosterIsolate {
  public static Bitmap Run(Bitmap src, PointF[] poly, float[][] clear, int feather, bool flip, int max, int white) {
    int w = src.Width, h = src.Height;
    Bitmap mask = new Bitmap(w, h, PixelFormat.Format32bppArgb);
    using (Graphics g = Graphics.FromImage(mask)) {
      g.Clear(Color.Black); g.SmoothingMode = SmoothingMode.AntiAlias;
      PointF[] pts = new PointF[poly.Length];
      for (int i = 0; i < pts.Length; i++) pts[i] = new PointF(poly[i].X * w, poly[i].Y * h);
      g.FillPolygon(Brushes.White, pts);
    }
    BitmapData md = mask.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
    byte[] m = new byte[md.Stride * h]; Marshal.Copy(md.Scan0, m, 0, m.Length);
    float[] a = new float[w * h];
    for (int i = 0; i < a.Length; i++) a[i] = m[(i / w) * md.Stride + (i % w) * 4 + 2] / 255f;
    if (feather > 0) {
      float[] t = new float[w * h];
      for (int pass = 0; pass < 2; pass++) {
        for (int y = 0; y < h; y++) { float s = 0; int c = 0;
          for (int x = 0; x < Math.Min(w, feather); x++) { s += a[y * w + x]; c++; }
          for (int x = 0; x < w; x++) { int add = x + feather, rem = x - feather - 1;
            if (add < w) { s += a[y * w + add]; c++; } if (rem >= 0) { s -= a[y * w + rem]; c--; }
            t[y * w + x] = s / c; } }
        for (int x = 0; x < w; x++) { float s = 0; int c = 0;
          for (int y = 0; y < Math.Min(h, feather); y++) { s += t[y * w + x]; c++; }
          for (int y = 0; y < h; y++) { int add = y + feather, rem = y - feather - 1;
            if (add < h) { s += t[add * w + x]; c++; } if (rem >= 0) { s -= t[rem * w + x]; c--; }
            a[y * w + x] = s / c; } }
      }
    }
    mask.UnlockBits(md); mask.Dispose();
    Bitmap bmp = new Bitmap(w, h, PixelFormat.Format32bppArgb);
    using (Graphics g = Graphics.FromImage(bmp)) g.DrawImage(src, 0, 0, w, h);
    BitmapData d = bmp.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
    byte[] p = new byte[d.Stride * h]; Marshal.Copy(d.Scan0, p, 0, p.Length);
    foreach (float[] c in clear) {
      int x0 = (int)(c[0] * w), y0 = (int)(c[1] * h), x1 = (int)(c[2] * w), y1 = (int)(c[3] * h);
      for (int y = Math.Max(0, y0); y < Math.Min(h, y1); y++) for (int x = Math.Max(0, x0); x < Math.Min(w, x1); x++) {
        int i = y * d.Stride + x * 4; int mn = Math.Min(p[i], Math.Min(p[i + 1], p[i + 2]));
        if (mn > white) p[i + 3] = 0;
      }
    }
    int minx = w, miny = h, maxx = -1, maxy = -1;
    for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
      int i = y * d.Stride + x * 4; float v = p[i + 3] / 255f * a[y * w + x];
      byte b = (byte)(v * 255f); p[i + 3] = b;
      if (b > 12) { if (x < minx) minx = x; if (x > maxx) maxx = x; if (y < miny) miny = y; if (y > maxy) maxy = y; }
    }
    Marshal.Copy(p, 0, d.Scan0, p.Length); bmp.UnlockBits(d);
    if (maxx < 0) throw new Exception("Nothing left: check the -Polygon points.");
    Bitmap res = bmp.Clone(new Rectangle(minx, miny, maxx - minx + 1, maxy - miny + 1), PixelFormat.Format32bppArgb);
    bmp.Dispose();
    int big = Math.Max(res.Width, res.Height);
    if (big > max) {
      float k = (float)max / big; Bitmap sm = new Bitmap((int)(res.Width * k), (int)(res.Height * k), PixelFormat.Format32bppArgb);
      using (Graphics g = Graphics.FromImage(sm)) { g.InterpolationMode = InterpolationMode.HighQualityBicubic; g.DrawImage(res, 0, 0, sm.Width, sm.Height); }
      res.Dispose(); res = sm;
    }
    if (flip) res.RotateFlip(RotateFlipType.RotateNoneFlipX);
    return res;
  }
}
'@
$poly = @($Polygon -split '\s+' | Where-Object { $_ } | ForEach-Object { $v = $_ -split ','; New-Object Drawing.PointF ([single]$v[0]), ([single]$v[1]) })
if ($poly.Count -lt 3) { throw 'Polygon needs at least 3 points: "x,y x,y x,y".' }
$boxes = @()
if ($Clear) { foreach ($b in ($Clear -split ';' | Where-Object { $_ })) { $boxes += , ([single[]]($b -split ',')) } }
$src = New-Object Drawing.Bitmap ((Resolve-Path -LiteralPath $In).ProviderPath)
try {
  $res = [PosterIsolate]::Run($src, $poly, [single[][]]$boxes, $Feather, [bool]$Flip, $Max, $WhiteMin)
  $outPath = [IO.Path]::GetFullPath($Out)
  $res.Save($outPath, [Drawing.Imaging.ImageFormat]::Png)
  $check = [IO.Path]::ChangeExtension($outPath, '.check.jpg')
  $prev = New-Object Drawing.Bitmap $res.Width, $res.Height
  $g = [Drawing.Graphics]::FromImage($prev); $g.Clear([Drawing.Color]::Magenta); $g.DrawImage($res, 0, 0, $res.Width, $res.Height); $g.Dispose()
  $prev.Save($check, [Drawing.Imaging.ImageFormat]::Jpeg); $prev.Dispose()
  Write-Output ("OK {0} ({1}x{2})" -f $outPath, $res.Width, $res.Height)
  Write-Output ("CHECK {0}" -f $check)
  $res.Dispose()
}
finally { $src.Dispose() }
