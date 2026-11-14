<#
  Fill the small transparent windows that are ENCLOSED inside a cut-out character (the gap between a pigtail and the neck,
  the loop of an arm, the space under a raised hand). On a poster those windows show a patch of the bright background
  (a spotlight beam, a slab) in the middle of dark hair and look like a pink/grey blob stuck on the character.
  The script floods the transparent area from the image border; every transparent pixel the flood cannot reach is an
  enclosed window and is painted with a dark colour (default near-black, for black hair), so the gap reads as hair shadow.
    fill-holes.ps1 -In hero.png -Out hero_filled.png [-Color '#0c0809'] [-Alpha 255] [-Threshold 40] [-MinArea 150]
  Run it on the finished hero (after hero-prep.ps1); it does not touch anything connected to the outside.
  Use a Color close to the HAIR colour (a deep wine fill next to black hair showed up as a separate blob); a window bigger than
  ~15 percent of the figure is probably not a gap, check by eye. Tested on the Streamer girl: 2 windows, 69k px.
#>
param(
  [Parameter(Mandatory = $true)][string]$In,
  [Parameter(Mandatory = $true)][string]$Out,
  [string]$Color = '#0c0809',
  [int]$Alpha = 255,
  [int]$Threshold = 40,
  [int]$MinArea = 150
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System; using System.Drawing; using System.Drawing.Imaging; using System.Runtime.InteropServices; using System.Collections.Generic;
public static class PosterFillHoles {
  public static int Run(Bitmap src, string outPath, int r, int g, int b, int a, int thr, int minArea, out int regions) {
    int w = src.Width, h = src.Height;
    BitmapData d = src.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
    byte[] p = new byte[d.Stride * h]; Marshal.Copy(d.Scan0, p, 0, p.Length);
    int stride = d.Stride;
    byte[] label = new byte[w * h]; // 0 = unvisited, 1 = outside transparent, 2 = solid, 3 = enclosed (filled)
    for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) label[y * w + x] = (byte)(p[y * stride + x * 4 + 3] < thr ? 0 : 2);
    var q = new Stack<int>();
    Action<int, int> seed = (x, y) => { int i = y * w + x; if (label[i] == 0) { label[i] = 1; q.Push(i); } };
    for (int x = 0; x < w; x++) { seed(x, 0); seed(x, h - 1); }
    for (int y = 0; y < h; y++) { seed(0, y); seed(w - 1, y); }
    while (q.Count > 0) {
      int i = q.Pop(); int x = i % w, y = i / w;
      if (x > 0) seed(x - 1, y); if (x < w - 1) seed(x + 1, y); if (y > 0) seed(x, y - 1); if (y < h - 1) seed(x, y + 1);
    }
    // remaining label 0 = enclosed transparent windows; group them and fill those bigger than minArea
    int filled = 0; regions = 0;
    for (int s = 0; s < w * h; s++) {
      if (label[s] != 0) continue;
      var comp = new List<int>(); var st = new Stack<int>(); st.Push(s); label[s] = 3;
      while (st.Count > 0) {
        int i = st.Pop(); comp.Add(i); int x = i % w, y = i / w;
        if (x > 0 && label[i - 1] == 0) { label[i - 1] = 3; st.Push(i - 1); }
        if (x < w - 1 && label[i + 1] == 0) { label[i + 1] = 3; st.Push(i + 1); }
        if (y > 0 && label[i - w] == 0) { label[i - w] = 3; st.Push(i - w); }
        if (y < h - 1 && label[i + w] == 0) { label[i + w] = 3; st.Push(i + w); }
      }
      if (comp.Count < minArea) continue;
      regions++;
      foreach (int i in comp) { int x = i % w, y = i / w; int o = y * stride + x * 4; p[o] = (byte)b; p[o + 1] = (byte)g; p[o + 2] = (byte)r; p[o + 3] = (byte)a; filled++; }
    }
    Marshal.Copy(p, 0, d.Scan0, p.Length); src.UnlockBits(d);
    return filled;
  }
}
'@
$c = [Drawing.ColorTranslator]::FromHtml($Color)
$src = New-Object Drawing.Bitmap ((Resolve-Path -LiteralPath $In).ProviderPath)
try {
  $regions = 0
  $n = [PosterFillHoles]::Run($src, $Out, $c.R, $c.G, $c.B, $Alpha, $Threshold, $MinArea, [ref]$regions)
  $o = [IO.Path]::GetFullPath($Out); New-Item -ItemType Directory -Force -Path (Split-Path -Parent $o) | Out-Null
  $src.Save($o, [Drawing.Imaging.ImageFormat]::Png)
  Write-Output ("OK {0}: filled {1} enclosed windows ({2} px, {3:P1} of the picture)" -f $o, $regions, $n, ($n / ($src.Width * $src.Height)))
} finally { $src.Dispose() }
