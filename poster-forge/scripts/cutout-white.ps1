<#
  Cut a character out of its ORIGINAL picture when the picture has a plain white background and the
  character may wear white clothes (so a plain "remove white" would eat the clothes). Pixels stay the
  user's own: nothing is regenerated.

  Usage (all coordinates are PIXELS of the input picture; read them off a grid overlay, see SKILL.md):
    cutout-white.ps1 -In IMG.jpg -Out hero.png -Keep "x,y x,y x,y ..." `
        (every polygon option takes several polygons separated by ";", e.g. -Free "x,y x,y x,y;x,y x,y x,y") `
        [-Free "x,y ..."]  [-Drop "x,y ..."]  [-Crop "x0,y0,x1,y1"]  [-Thresh 250] [-Band 20] [-Feather 1.4]

  -Keep    outline of the character (everything outside it is removed). Draw it slightly OUTSIDE white
           clothing edges (<= 15 px), and loosely around hair. Up to 3 outlines: -Keep, -Keep2, -Keep3.
  -Free    areas (hair, gaps between arm and body) where near-white pixels that connect to the outside are
           removed to any depth. Never draw it over white clothes.
  -Drop    areas removed no matter what (stickers, watermark tags, the other person of a couple).
  -Thresh  a pixel counts as "white background" when its darkest channel is >= this (default 250).
  -FreeThresh  the same threshold but only inside -Free areas (default = -Thresh). Lower it (e.g. 236) to also clear the grey
           watermark swashes and halo around hair; keep -Free away from white clothes and pale skin when you do.
  -Band    outside -Free areas, white is removed only this many px deep from the outline (default 20), so a
           white shirt next to the outline is cut at its grey edge line instead of being eaten.
  -Crop    keep only this box (the bottom of a bust is normally hidden behind the cards).
  -Pocket  white pockets enclosed by hair strands inside -Free areas are removed when smaller than this many px (default 6000).
  -Halo    inside -Free areas, pale pixels (darkest channel >= this, default 238) touching removed ones are peeled 3 px deep
           (JPEG halo around hair). Set 0 to turn off.
  -Feather edge softness in px (default 1.4). The edge is also pulled in by 1 px and hair-edge pixels are
           un-mixed from white so no white fringe shows on a dark poster.
  Writes <Out> and <Out>.check.jpg (magenta = transparent): open it and look at the shoulders and hair.
#>
param(
  [Parameter(Mandatory = $true)][string]$In,
  [Parameter(Mandatory = $true)][string]$Out,
  [Parameter(Mandatory = $true)][string]$Keep,
  [string]$Keep2 = '', [string]$Keep3 = '',
  [string]$Free = '', [string]$Free2 = '', [string]$Free3 = '',
  [string]$Drop = '', [string]$Drop2 = '',
  [string]$Crop = '',
  [int]$Thresh = 250,
  [int]$Band = 20,
  [double]$Feather = 1.4,
  [int]$Erode = 1,
  [int]$FreeThresh = 0,
  [int]$Pocket = 6000,
  [int]$Halo = 238,
  [int]$Max = 2400
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System; using System.Collections.Generic; using System.Drawing; using System.Drawing.Drawing2D; using System.Drawing.Imaging; using System.Runtime.InteropServices;
public static class PosterCutWhite {
  static bool[] Raster(int w, int h, List<PointF[]> polys) {
    bool[] r = new bool[w * h]; if (polys.Count == 0) return r;
    using (Bitmap m = new Bitmap(w, h, PixelFormat.Format32bppArgb)) {
      using (Graphics g = Graphics.FromImage(m)) { g.Clear(Color.Black); g.SmoothingMode = SmoothingMode.None; foreach (PointF[] p in polys) g.FillPolygon(Brushes.White, p); }
      BitmapData d = m.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
      byte[] b = new byte[d.Stride * h]; Marshal.Copy(d.Scan0, b, 0, b.Length); m.UnlockBits(d);
      for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) r[y * w + x] = b[y * d.Stride + x * 4 + 2] > 127;
    }
    return r;
  }
  public static Bitmap Run(Bitmap src, List<PointF[]> keep, List<PointF[]> free, List<PointF[]> drop, int[] crop, int thresh, int band, double feather, int erode, int max, int pocket, int halo, int freeThresh) {
    int w = src.Width, h = src.Height;
    Bitmap bmp = new Bitmap(w, h, PixelFormat.Format32bppArgb);
    using (Graphics g = Graphics.FromImage(bmp)) g.DrawImage(src, 0, 0, w, h);
    BitmapData d = bmp.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
    int stride = d.Stride; byte[] p = new byte[stride * h]; Marshal.Copy(d.Scan0, p, 0, p.Length);
    bool[] K = Raster(w, h, keep), F = Raster(w, h, free), D = Raster(w, h, drop);
    bool[] gone = new bool[w * h]; int[] depth = new int[w * h];
    Queue<int> q = new Queue<int>();
    for (int i = 0; i < w * h; i++) { if (!K[i] || D[i]) { gone[i] = true; q.Enqueue(i); } }
    int[] dx = { -1, 1, 0, 0 }, dy = { 0, 0, -1, 1 };
    while (q.Count > 0) {
      int k = q.Dequeue(); int y = k / w, x = k % w;
      for (int n = 0; n < 4; n++) {
        int nx = x + dx[n], ny = y + dy[n]; if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
        int j = ny * w + nx; if (gone[j]) continue;
        int i = ny * stride + nx * 4; int mn = Math.Min(p[i], Math.Min(p[i + 1], p[i + 2]));
        if (mn < (F[j] ? freeThresh : thresh)) continue;
        int dep = depth[k] + 1;
        if (!F[j] && dep > band) continue;
        gone[j] = true; depth[j] = dep; q.Enqueue(j);
      }
    }
    // white pockets enclosed by hair strands inside -Free areas (flood cannot reach them): remove small ones
    if (pocket > 0) {
      bool[] seen = new bool[w * h];
      for (int s0 = 0; s0 < w * h; s0++) {
        if (seen[s0] || gone[s0] || !F[s0]) continue;
        int si = (s0 / w) * stride + (s0 % w) * 4; if (Math.Min(p[si], Math.Min(p[si + 1], p[si + 2])) < thresh) continue;
        List<int> comp = new List<int>(); Queue<int> cq = new Queue<int>(); cq.Enqueue(s0); seen[s0] = true; bool allF = true;
        while (cq.Count > 0) {
          int k = cq.Dequeue(); comp.Add(k); if (!F[k]) allF = false; int y = k / w, x = k % w;
          for (int n = 0; n < 4; n++) {
            int nx = x + dx[n], ny = y + dy[n]; if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
            int j = ny * w + nx; if (seen[j] || gone[j]) continue;
            int i = ny * stride + nx * 4; if (Math.Min(p[i], Math.Min(p[i + 1], p[i + 2])) < thresh) continue;
            seen[j] = true; cq.Enqueue(j);
          }
          if (comp.Count > pocket) break;
        }
        if (comp.Count <= pocket && allF) foreach (int k in comp) gone[k] = true;
      }
    }
    // light halo left on hair edges (JPEG ringing): peel pale pixels that touch removed ones, only inside -Free areas
    for (int it = 0; it < 3 && halo > 0; it++) {
      List<int> peel = new List<int>();
      for (int y = 1; y < h - 1; y++) for (int x = 1; x < w - 1; x++) {
        int k = y * w + x; if (gone[k] || !F[k]) continue;
        if (!(gone[k - 1] || gone[k + 1] || gone[k - w] || gone[k + w])) continue;
        int i = y * stride + x * 4; if (Math.Min(p[i], Math.Min(p[i + 1], p[i + 2])) >= halo) peel.Add(k);
      }
      foreach (int k in peel) gone[k] = true;
    }
    float[] a = new float[w * h];
    for (int i = 0; i < a.Length; i++) a[i] = gone[i] ? 0f : 1f;
    // un-mix hair edge pixels from white (only next to removed pixels, only where the pixel is light and neutral-ish)
    for (int y = 1; y < h - 1; y++) for (int x = 1; x < w - 1; x++) {
      int k = y * w + x; if (gone[k]) continue;
      bool near = false;
      for (int yy = y - 2; yy <= y + 2 && !near; yy++) for (int xx = x - 2; xx <= x + 2; xx++) { if (yy < 0 || xx < 0 || yy >= h || xx >= w) continue; if (gone[yy * w + xx]) { near = true; break; } }
      if (!near) continue;
      int i = y * stride + x * 4; int b0 = p[i], g0 = p[i + 1], r0 = p[i + 2];
      int mn = Math.Min(b0, Math.Min(g0, r0)), mx = Math.Max(b0, Math.Max(g0, r0));
      if (!F[k] || mn < 70) continue;
      if (mx - mn > 60) continue;
      float al = Math.Max(0.12f, Math.Min(1f, (255f - mn - 6f) / 150f));
      a[k] = al;
      p[i] = (byte)Math.Max(0, Math.Min(255, (b0 - 255f * (1f - al)) / al));
      p[i + 1] = (byte)Math.Max(0, Math.Min(255, (g0 - 255f * (1f - al)) / al));
      p[i + 2] = (byte)Math.Max(0, Math.Min(255, (r0 - 255f * (1f - al)) / al));
    }
    for (int e = 0; e < erode; e++) {
      float[] t2 = new float[w * h];
      for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
        float m = a[y * w + x]; if (m == 0f) continue;
        for (int yy = Math.Max(0, y - 1); yy <= Math.Min(h - 1, y + 1); yy++) for (int xx = Math.Max(0, x - 1); xx <= Math.Min(w - 1, x + 1); xx++) { float v = a[yy * w + xx]; if (v < m) m = v; }
        t2[y * w + x] = m;
      }
      Array.Copy(t2, a, a.Length);
    }
    int passes = (int)Math.Round(feather); if (feather > 0 && passes < 1) passes = 1;
    if (passes > 0) {
      float[] t = new float[w * h];
      for (int pass = 0; pass < passes; pass++) {
        for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
          float s = 0; int c = 0;
          for (int yy = Math.Max(0, y - 1); yy <= Math.Min(h - 1, y + 1); yy++) for (int xx = Math.Max(0, x - 1); xx <= Math.Min(w - 1, x + 1); xx++) { s += a[yy * w + xx]; c++; }
          t[y * w + x] = s / c;
        }
        Array.Copy(t, a, a.Length);
      }
      for (int i = 0; i < a.Length; i++) a[i] = Math.Max(0f, Math.Min(1f, (a[i] - 0.25f) * 1.6f));
    }
    int x0 = 0, y0 = 0, x1 = w - 1, y1 = h - 1;
    if (crop != null) { x0 = Math.Max(0, crop[0]); y0 = Math.Max(0, crop[1]); x1 = Math.Min(w - 1, crop[2]); y1 = Math.Min(h - 1, crop[3]); }
    int minx = w, miny = h, maxx = -1, maxy = -1;
    for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
      bool inside = x >= x0 && x <= x1 && y >= y0 && y <= y1;
      byte v = inside ? (byte)(a[y * w + x] * 255f) : (byte)0; p[y * stride + x * 4 + 3] = v;
      if (v > 12) { if (x < minx) minx = x; if (x > maxx) maxx = x; if (y < miny) miny = y; if (y > maxy) maxy = y; }
    }
    Marshal.Copy(p, 0, d.Scan0, p.Length); bmp.UnlockBits(d);
    if (maxx < 0) throw new Exception("Nothing left: check -Keep.");
    Bitmap res = bmp.Clone(new Rectangle(minx, miny, maxx - minx + 1, maxy - miny + 1), PixelFormat.Format32bppArgb);
    bmp.Dispose();
    int big = Math.Max(res.Width, res.Height);
    if (big > max) { float k = (float)max / big; Bitmap sm = new Bitmap((int)(res.Width * k), (int)(res.Height * k), PixelFormat.Format32bppArgb); using (Graphics g = Graphics.FromImage(sm)) { g.InterpolationMode = InterpolationMode.HighQualityBicubic; g.DrawImage(res, 0, 0, sm.Width, sm.Height); } res.Dispose(); res = sm; }
    return res;
  }
}
'@
function ParsePoly([string]$s) {
  if (-not $s) { return $null }
  $pts = @($s -split '\s+' | Where-Object { $_ } | ForEach-Object { $v = $_ -split ','; New-Object Drawing.PointF ([single]$v[0]), ([single]$v[1]) })
  if ($pts.Count -lt 3) { throw "A polygon needs at least 3 points: '$s'" }
  return , ([Drawing.PointF[]]$pts)
}
function PolyList($strs) {
  $l = New-Object 'System.Collections.Generic.List[System.Drawing.PointF[]]'
  foreach ($s in $strs) { foreach ($one in ($s -split ';')) { $p = ParsePoly $one.Trim(); if ($p) { $l.Add($p) } } }
  return , $l
}
$src = New-Object Drawing.Bitmap ((Resolve-Path -LiteralPath $In).ProviderPath)
try {
  $keepL = PolyList @($Keep, $Keep2, $Keep3)
  $freeL = PolyList @($Free, $Free2, $Free3)
  $dropL = PolyList @($Drop, $Drop2)
  $cropA = $null; if ($Crop) { $cropA = [int[]]($Crop -split ',') }
  $res = [PosterCutWhite]::Run($src, $keepL, $freeL, $dropL, $cropA, $Thresh, $Band, $Feather, $Erode, $Max, $Pocket, $Halo, $(if ($FreeThresh -gt 0) { $FreeThresh } else { $Thresh }))
  $outPath = [IO.Path]::GetFullPath($Out)
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outPath) | Out-Null
  $res.Save($outPath, [Drawing.Imaging.ImageFormat]::Png)
  $check = [IO.Path]::ChangeExtension($outPath, '.check.jpg')
  $prev = New-Object Drawing.Bitmap $res.Width, $res.Height
  $g = [Drawing.Graphics]::FromImage($prev); $g.Clear([Drawing.Color]::FromArgb(255, 0, 255)); $g.DrawImage($res, 0, 0, $res.Width, $res.Height); $g.Dispose()
  $prev.Save($check, [Drawing.Imaging.ImageFormat]::Jpeg); $prev.Dispose()
  Write-Output ("OK {0} ({1}x{2})" -f $outPath, $res.Width, $res.Height)
  Write-Output ("CHECK {0}" -f $check)
  $res.Dispose()
}
finally { $src.Dispose() }
