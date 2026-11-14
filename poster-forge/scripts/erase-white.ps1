<#
  Remove a leftover white pocket (background trapped between an arm and a neck, a collar gap, a halo) from a cut-out PNG.
  Flood-fills outward from seed pixels that sit ON the white, only through near-white pixels, only inside the bounds.
    erase-white.ps1 -In boy.png -Out boy.png -Seeds "170,1092;1000,1070" -Bounds "40,980,430,1300;740,960,1180,1140" [-Min 232]
  Pixel coordinates are in the PNG itself. A seed must be on a white pixel, not on skin. Always keep -Bounds tight:
  pale skin is only a little darker than white and floods if the bounds reach the face or hands.
#>
param(
  [Parameter(Mandatory = $true)][string]$In,
  [Parameter(Mandatory = $true)][string]$Out,
  [Parameter(Mandatory = $true)][string]$Seeds,
  [Parameter(Mandatory = $true)][string]$Bounds,
  [int]$Min = 232
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System; using System.Collections.Generic; using System.Drawing; using System.Drawing.Imaging; using System.Runtime.InteropServices;
public static class PosterEraseWhite {
  public static void Run(string inp, string outp, int[][] seeds, int[][] bounds, int minv) {
    Bitmap src = new Bitmap(inp); int w = src.Width, h = src.Height; Bitmap b = new Bitmap(w, h, PixelFormat.Format32bppArgb);
    using (Graphics g = Graphics.FromImage(b)) g.DrawImage(src, 0, 0, w, h); src.Dispose();
    BitmapData d = b.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
    byte[] p = new byte[d.Stride * h]; Marshal.Copy(d.Scan0, p, 0, p.Length);
    Stack<int> st = new Stack<int>(); bool[] seen = new bool[w * h];
    foreach (int[] r in seeds) { int k = r[1] * w + r[0]; seen[k] = true; p[r[1] * d.Stride + r[0] * 4 + 3] = 0; st.Push(k); }
    while (st.Count > 0) {
      int k = st.Pop(); int x = k % w, y = k / w; int[] nx = { x - 1, x + 1, x, x }, ny = { y, y, y - 1, y + 1 };
      for (int n = 0; n < 4; n++) {
        int X = nx[n], Y = ny[n]; if (X < 0 || Y < 0 || X >= w || Y >= h) continue; int q = Y * w + X; if (seen[q]) continue;
        bool ok = false; foreach (int[] r in bounds) if (X >= r[0] && X < r[2] && Y >= r[1] && Y < r[3]) ok = true; if (!ok) continue;
        int i = Y * d.Stride + X * 4; int mn = Math.Min(p[i], Math.Min(p[i + 1], p[i + 2]));
        if (p[i + 3] == 0 || mn >= minv) { seen[q] = true; p[i + 3] = 0; st.Push(q); }
      }
    }
    Marshal.Copy(p, 0, d.Scan0, p.Length); b.UnlockBits(d); b.Save(outp, ImageFormat.Png); b.Dispose();
  }
}
'@
$s = @($Seeds -split ';' | Where-Object { $_ } | ForEach-Object { , [int[]]($_ -split ',') })
$bd = @($Bounds -split ';' | Where-Object { $_ } | ForEach-Object { , [int[]]($_ -split ',') })
$sa = New-Object 'int[][]' $s.Count; for ($i = 0; $i -lt $s.Count; $i++) { $sa[$i] = $s[$i] }
$ba = New-Object 'int[][]' $bd.Count; for ($i = 0; $i -lt $bd.Count; $i++) { $ba[$i] = $bd[$i] }
$inP = (Resolve-Path -LiteralPath $In).ProviderPath; $outP = [IO.Path]::GetFullPath($Out)
$tmp = $outP + '.tmp.png'
[PosterEraseWhite]::Run($inP, $tmp, $sa, $ba, $Min)
Move-Item -LiteralPath $tmp -Destination $outP -Force
Write-Output "OK $outP"
