param(
    [Parameter(Mandatory = $true)][string]$Image,
    [int]$Colors = 8,
    [double]$CropLeft = 0.0,
    [double]$CropTop = 0.0,
    [double]$CropRight = 1.0,
    [double]$CropBottom = 1.0
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;

public static class PaletteKMeans {
    public static string[] Run(Bitmap bmp, int k, Rectangle area) {
        var samples = new List<double[]>();
        int step = Math.Max(1, Math.Min(area.Width, area.Height) / 220);
        for (int y = area.Top; y < area.Bottom; y += step)
            for (int x = area.Left; x < area.Right; x += step) {
                var c = bmp.GetPixel(x, y);
                if (c.A >= 200) samples.Add(new double[] { c.R, c.G, c.B });
            }
        var rng = new Random(11);
        var centers = samples.OrderBy(_ => rng.Next()).Take(k).Select(s => (double[])s.Clone()).ToArray();
        var counts = new int[k];
        for (int iter = 0; iter < 24; iter++) {
            var sum = new double[k, 3];
            Array.Clear(counts, 0, k);
            foreach (var s in samples) {
                int best = 0; double bestD = double.MaxValue;
                for (int i = 0; i < k; i++) {
                    double d = 0;
                    for (int a = 0; a < 3; a++) d += (s[a] - centers[i][a]) * (s[a] - centers[i][a]);
                    if (d < bestD) { bestD = d; best = i; }
                }
                counts[best]++;
                for (int a = 0; a < 3; a++) sum[best, a] += s[a];
            }
            for (int i = 0; i < k; i++)
                if (counts[i] > 0)
                    for (int a = 0; a < 3; a++) centers[i][a] = sum[i, a] / counts[i];
        }
        return Enumerable.Range(0, k).OrderByDescending(i => counts[i]).Select(i => string.Format("#{0:x2}{1:x2}{2:x2}  {3,5:0.0}%", (int)centers[i][0], (int)centers[i][1], (int)centers[i][2], 100.0 * counts[i] / samples.Count)).ToArray();
    }
}
'@

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("palette_" + [Guid]::NewGuid().ToString('N') + ".img")
Copy-Item -LiteralPath $Image -Destination $tmp
try {
    $img = [System.Drawing.Image]::FromFile($tmp)
    $bmp = New-Object System.Drawing.Bitmap $img
    $area = [System.Drawing.Rectangle]::FromLTRB([int]($bmp.Width * $CropLeft), [int]($bmp.Height * $CropTop), [int]($bmp.Width * $CropRight), [int]($bmp.Height * $CropBottom))
    [PaletteKMeans]::Run($bmp, $Colors, $area)
    $bmp.Dispose()
    $img.Dispose()
}
finally {
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
}
