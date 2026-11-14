<#
  One step from a Gemini green-screen character picture to a poster-ready hero:
  chroma-key cut -> crop sideways to the figure (full height kept, so the body reaches the poster's bottom edge) -> upscale + sharpen.
    hero-prep.ps1 -In work\ai2\family_outfit.png -Out work\hero_family.png [-Scale 1.85]
  Then put it in the spec as   "heroes":[{"src":"hero_family.png","x":0.36,"y":1.0,"h":0.96,"fade":{"bottom":0},...}]
  (this is what was done by hand with cutout.ps1 -Chroma -NoCrop + a bounding-box crop + upscale.ps1; the temporary files are deleted).
#>
param(
  [Parameter(Mandatory = $true)][string]$In,
  [Parameter(Mandatory = $true)][string]$Out,
  [double]$Scale = 1.85,
  [double]$Amount = 0.55,
  [double]$Radius = 1.2
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$tmp = Join-Path $env:TEMP ('hero-prep-' + [Guid]::NewGuid().ToString('N')); New-Item -ItemType Directory -Force -Path $tmp | Out-Null
try {
  $cut = Join-Path $tmp 'cut.png'
  & (Join-Path $here 'cutout.ps1') -In $In -Out $cut -Chroma -NoCrop | Out-Null
  $b = New-Object Drawing.Bitmap $cut
  $minx = $b.Width; $maxx = 0
  for ($y = 0; $y -lt $b.Height; $y += 3) { for ($x = 0; $x -lt $b.Width; $x += 2) { if ($b.GetPixel($x, $y).A -gt 40) { if ($x -lt $minx) { $minx = $x }; if ($x -gt $maxx) { $maxx = $x } } } }
  if ($maxx -le $minx) { throw 'Nothing left after the chroma cut: is the background really green?' }
  $minx = [Math]::Max(0, $minx - 4); $maxx = [Math]::Min($b.Width - 1, $maxx + 4)
  $crop = Join-Path $tmp 'crop.png'
  $cl = $b.Clone((New-Object Drawing.Rectangle $minx, 0, ($maxx - $minx + 1), $b.Height), [Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $cl.Save($crop); $cl.Dispose(); $b.Dispose()
  & (Join-Path $here 'upscale.ps1') -In $crop -Out $Out -Scale $Scale -Amount $Amount -Radius $Radius
  Write-Output ("CROP x {0}..{1} of the source" -f $minx, $maxx)
}
finally { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }
