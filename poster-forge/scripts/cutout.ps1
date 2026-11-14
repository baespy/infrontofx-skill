<#
  Remove a plain or green-screen background and crop to the subject.
  Usage:
    cutout.ps1 -In a.jpg -Out a.png                 flood-fill the background from the image border
    cutout.ps1 -In a.jpg -Out a.png -Tolerance 40   widen the match for gradients and vignettes
    cutout.ps1 -In a.jpg -Out a.png -Chroma         key out green at any position, with despill
  Busy backgrounds are out of scope: ask for a cut-out PNG, or use the "fade" hero option.
#>
param(
  [Parameter(Mandatory = $true)][string]$In,
  [Parameter(Mandatory = $true)][string]$Out,
  [int]$Tolerance = 26,
  [int]$Feather = 2,
  [int]$Erode = -1,
  [switch]$Chroma,
  [switch]$NoCrop
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System; using System.Collections.Generic; using System.Drawing; using System.Drawing.Imaging; using System.Runtime.InteropServices;
public static class PosterCutout {
  static int Dist(byte[] p, int i, int r, int g, int b) {
    int dr = p[i + 2] - r, dg = p[i + 1] - g, db = p[i] - b;
    return (int)Math.Sqrt(dr * dr + dg * dg + db * db);
  }
  public static Bitmap Run(Bitmap src, int tol, int feather, bool chroma, bool crop, int erode) {
    int w = src.Width, h = src.Height;
    Bitmap bmp = new Bitmap(w, h, PixelFormat.Format32bppArgb);
    using (Graphics g = Graphics.FromImage(bmp)) g.DrawImage(src, 0, 0, w, h);
    BitmapData d = bmp.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
    int stride = d.Stride; byte[] p = new byte[stride * h];
    Marshal.Copy(d.Scan0, p, 0, p.Length);
    float[] a = new float[w * h];
    for (int i = 0; i < a.Length; i++) a[i] = 1f;
    if (chroma) {
      for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
        int i = y * stride + x * 4; int b = p[i], gr = p[i + 1], r = p[i + 2];
        int excess = gr - Math.Max(r, b);
        a[y * w + x] = 1f - Math.Min(1f, Math.Max(0f, (excess - 30f) / 60f));
        if (excess > 0) p[i + 1] = (byte)Math.Max(r, b);
      }
    } else {
      bool[] seen = new bool[w * h];
      Stack<int> st = new Stack<int>();
      Action<int, int> seed = (x, y) => { if (!seen[y * w + x]) { seen[y * w + x] = true; st.Push(y * w + x); } };
      // Background colour = brightest of the four corners; only border pixels close to it are seeds,
      // so a dark sleeve or coat touching the frame edge is not erased.
      int[] cx = { 0, w - 1, 0, w - 1 }, cy = { 0, 0, h - 1, h - 1 }; int bgR = 0, bgG = 0, bgB = 0, best = -1;
      for (int c = 0; c < 4; c++) { int ci = cy[c] * stride + cx[c] * 4; int s = p[ci] + p[ci + 1] + p[ci + 2]; if (s > best) { best = s; bgR = p[ci + 2]; bgG = p[ci + 1]; bgB = p[ci]; } }
      Action<int, int> edge = (x, y) => { if (Dist(p, y * stride + x * 4, bgR, bgG, bgB) <= tol * 2) seed(x, y); };
      for (int x = 0; x < w; x++) { edge(x, 0); edge(x, h - 1); }
      for (int y = 0; y < h; y++) { edge(0, y); edge(w - 1, y); }
      int[] ref0 = new int[w * h];
      foreach (int k in st) ref0[k] = k;
      while (st.Count > 0) {
        int k = st.Pop(); int y = k / w, x = k % w; a[k] = 0f;
        int i0 = y * stride + x * 4; int r0 = p[i0 + 2], g0 = p[i0 + 1], b0 = p[i0];
        int[] nx = { x - 1, x + 1, x, x }, ny = { y, y, y - 1, y + 1 };
        for (int n = 0; n < 4; n++) {
          if (nx[n] < 0 || ny[n] < 0 || nx[n] >= w || ny[n] >= h) continue;
          int q = ny[n] * w + nx[n]; if (seen[q]) continue;
          if (Dist(p, ny[n] * stride + nx[n] * 4, r0, g0, b0) <= Math.Max(3, tol / 5)) {
            int ir = ref0[k]; int ri = (ir / w) * stride + (ir % w) * 4;
            if (Dist(p, ny[n] * stride + nx[n] * 4, p[ri + 2], p[ri + 1], p[ri]) <= tol) { seen[q] = true; ref0[q] = ir; st.Push(q); }
          }
        }
      }
    }
    for (int e = 0; e < erode; e++) {
      float[] t2 = new float[w * h];
      for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
        float m = a[y * w + x];
        for (int yy = Math.Max(0, y - 1); yy <= Math.Min(h - 1, y + 1); yy++)
          for (int xx = Math.Max(0, x - 1); xx <= Math.Min(w - 1, x + 1); xx++) m = Math.Min(m, a[yy * w + xx]);
        t2[y * w + x] = m;
      }
      Array.Copy(t2, a, a.Length);
    }
    if (feather > 0) {
      float[] t = new float[w * h];
      for (int pass = 0; pass < feather; pass++) {
        for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
          float s = 0; int c = 0;
          for (int yy = Math.Max(0, y - 1); yy <= Math.Min(h - 1, y + 1); yy++)
            for (int xx = Math.Max(0, x - 1); xx <= Math.Min(w - 1, x + 1); xx++) { s += a[yy * w + xx]; c++; }
          t[y * w + x] = s / c;
        }
        Array.Copy(t, a, a.Length);
      }
      for (int i = 0; i < a.Length; i++) a[i] = Math.Max(0f, Math.Min(1f, (a[i] - 0.5f) * 2f));
    }
    int minx = w, miny = h, maxx = -1, maxy = -1;
    for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
      byte v = (byte)(a[y * w + x] * 255f); p[y * stride + x * 4 + 3] = v;
      if (v > 12) { if (x < minx) minx = x; if (x > maxx) maxx = x; if (y < miny) miny = y; if (y > maxy) maxy = y; }
    }
    Marshal.Copy(p, 0, d.Scan0, p.Length); bmp.UnlockBits(d);
    if (maxx < 0) throw new Exception("Nothing left after removing the background: lower -Tolerance.");
    if (!crop) return bmp;
    Bitmap res = bmp.Clone(new Rectangle(minx, miny, maxx - minx + 1, maxy - miny + 1), PixelFormat.Format32bppArgb);
    bmp.Dispose(); return res;
  }
}
'@
$inPath = (Resolve-Path -LiteralPath $In).ProviderPath
$outPath = [IO.Path]::GetFullPath($Out)
$src = New-Object Drawing.Bitmap $inPath
try {
  $res = [PosterCutout]::Run($src, $Tolerance, $Feather, [bool]$Chroma, -not $NoCrop, $(if ($Erode -ge 0) { $Erode } elseif ($Chroma) { 1 } else { 0 }))
  $res.Save($outPath, [Drawing.Imaging.ImageFormat]::Png)
  $check = [IO.Path]::ChangeExtension($outPath, '.check.jpg')
  $prev = New-Object Drawing.Bitmap $res.Width, $res.Height
  $g = [Drawing.Graphics]::FromImage($prev); $g.Clear([Drawing.Color]::Magenta); $g.DrawImage($res, 0, 0, $res.Width, $res.Height); $g.Dispose()
  $prev.Save($check, [Drawing.Imaging.ImageFormat]::Jpeg); $prev.Dispose()
  Write-Output ("OK {0} ({1}x{2})" -f $outPath, $res.Width, $res.Height)
  Write-Output ("CHECK {0} (open it: magenta inside the subject means holes, so lower -Tolerance)" -f $check)
  $res.Dispose()
}
finally { $src.Dispose() }
