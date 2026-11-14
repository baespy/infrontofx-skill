<#
  Enlarge a cut-out character (PNG with alpha) and sharpen it, so a ~1000 px AI render does not look soft when it is
  shown 1.5-2x larger on a 1920 poster. Not real super-resolution: it is bicubic + unsharp mask, enough to look crisp.
    upscale.ps1 -In hero.png -Out hero_x2.png [-Scale 1.6] [-Amount 0.7] [-Radius 1.3]
  Alpha is scaled with the picture and never sharpened (no halos on the edge).
#>
param(
  [Parameter(Mandatory = $true)][string]$In,
  [Parameter(Mandatory = $true)][string]$Out,
  [double]$Scale = 1.6,
  [double]$Amount = 0.7,
  [double]$Radius = 1.3
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System; using System.Drawing; using System.Drawing.Drawing2D; using System.Drawing.Imaging; using System.Runtime.InteropServices;
public static class PosterUpscale {
  static void BoxBlur(float[] src, float[] dst, int w, int h, int r) {
    float[] tmp = new float[w * h];
    for (int y = 0; y < h; y++) { float s = 0; int c = 0;
      for (int x = 0; x <= Math.Min(r, w - 1); x++) { s += src[y * w + x]; c++; }
      for (int x = 0; x < w; x++) { tmp[y * w + x] = s / c; int add = x + r + 1, rem = x - r; if (add < w) { s += src[y * w + add]; c++; } if (rem >= 0) { s -= src[y * w + rem]; c--; } } }
    for (int x = 0; x < w; x++) { float s = 0; int c = 0;
      for (int y = 0; y <= Math.Min(r, h - 1); y++) { s += tmp[y * w + x]; c++; }
      for (int y = 0; y < h; y++) { dst[y * w + x] = s / c; int add = y + r + 1, rem = y - r; if (add < h) { s += tmp[add * w + x]; c++; } if (rem >= 0) { s -= tmp[rem * w + x]; c--; } } }
  }
  public static Bitmap Run(Bitmap src, double scale, double amount, double radius) {
    int w = (int)Math.Round(src.Width * scale), h = (int)Math.Round(src.Height * scale);
    Bitmap big = new Bitmap(w, h, PixelFormat.Format32bppArgb);
    using (Graphics g = Graphics.FromImage(big)) { g.InterpolationMode = InterpolationMode.HighQualityBicubic; g.PixelOffsetMode = PixelOffsetMode.HighQuality; g.SmoothingMode = SmoothingMode.HighQuality; g.DrawImage(src, new Rectangle(0, 0, w, h), 0, 0, src.Width, src.Height, GraphicsUnit.Pixel); }
    BitmapData d = big.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
    byte[] p = new byte[d.Stride * h]; Marshal.Copy(d.Scan0, p, 0, p.Length);
    int r = Math.Max(1, (int)Math.Round(radius));
    for (int ch = 0; ch < 3; ch++) {
      float[] a = new float[w * h], b = new float[w * h], b2 = new float[w * h];
      for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) a[y * w + x] = p[y * d.Stride + x * 4 + ch];
      BoxBlur(a, b, w, h, r); BoxBlur(b, b2, w, h, r);
      for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
        int i = y * d.Stride + x * 4; if (p[i + 3] < 8) continue;
        float v = a[y * w + x] + (float)amount * (a[y * w + x] - b2[y * w + x]);
        p[i + ch] = (byte)Math.Max(0, Math.Min(255, v));
      }
    }
    Marshal.Copy(p, 0, d.Scan0, p.Length); big.UnlockBits(d);
    return big;
  }
}
'@
$src = New-Object Drawing.Bitmap ((Resolve-Path -LiteralPath $In).ProviderPath)
try {
  $res = [PosterUpscale]::Run($src, $Scale, $Amount, $Radius)
  $o = [IO.Path]::GetFullPath($Out); New-Item -ItemType Directory -Force -Path (Split-Path -Parent $o) | Out-Null
  $res.Save($o, [Drawing.Imaging.ImageFormat]::Png)
  Write-Output ("OK {0} ({1}x{2})" -f $o, $res.Width, $res.Height)
  $res.Dispose()
} finally { $src.Dispose() }
