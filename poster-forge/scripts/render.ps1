<#
  Render a poster spec (JSON) to PNG with headless Chrome.
  Usage: render.ps1 -Spec path\poster.json [-Out path\poster.png]
  Asset paths in the spec may be relative to the spec file or absolute.
#>
param(
  [Parameter(Mandatory = $true)][string]$Spec,
  [string]$Out,
  [int]$WaitMs = 20000
)
$ErrorActionPreference = 'Stop'

$chromeCandidates = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
)
$chrome = $chromeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $chrome) { throw 'Chrome or Edge not found.' }

$specPath = (Resolve-Path -LiteralPath $Spec).ProviderPath
$specDir = Split-Path -Parent $specPath
if (-not $Out) { $Out = [IO.Path]::ChangeExtension($specPath, '.png') }
$outPath = [IO.Path]::GetFullPath($Out)

$utf8 = New-Object Text.UTF8Encoding($false)
$json = [IO.File]::ReadAllText($specPath, [Text.Encoding]::UTF8)
$data = $json | ConvertFrom-Json

$sizes = @{
  '16:9' = 1920, 1080; '1:1' = 1920, 1920; '6:5' = 2592, 2160; '2:1' = 2000, 1000
  '3:2' = 2048, 1365; '4:5' = 1536, 1920; '9:16' = 1080, 1920; 'cover' = 2000, 761
}
if ($data.size -is [array]) { $w = [int]$data.size[0]; $h = [int]$data.size[1] }
elseif ($data.size) {
  if (-not $sizes.ContainsKey([string]$data.size)) { throw "Unknown size '$($data.size)'. Use one of: $($sizes.Keys -join ', ') or [w,h]." }
  $w = $sizes[[string]$data.size][0]; $h = $sizes[[string]$data.size][1]
}
else { $w = 1920; $h = 1080 }

$engine = Join-Path (Split-Path -Parent $PSScriptRoot) 'engine'
$buildRoot = Join-Path $env:TEMP ('poster-forge-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null
try {
  $base = ([Uri]($specDir.TrimEnd('\') + '\')).AbsoluteUri
  $specJs = "window.SPEC=$json;`nwindow.RENDER={w:$w,h:$h,base:$(ConvertTo-Json $base)};"
  $specFile = Join-Path $buildRoot 'spec.js'
  [IO.File]::WriteAllText($specFile, $specJs, $utf8)

  $pageUri = ([Uri](Join-Path $engine 'poster.html')).AbsoluteUri + '?spec=' + [Uri]::EscapeDataString(([Uri]$specFile).AbsoluteUri)
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outPath) | Out-Null
  if (Test-Path -LiteralPath $outPath) { Remove-Item -LiteralPath $outPath -Force }

  $chromeProfile = Join-Path $buildRoot 'profile'
  $chromeArgs = @(
    '--headless=new', '--use-gl=angle', '--use-angle=d3d11', '--ignore-gpu-blocklist',
    '--enable-gpu-rasterization', '--disable-software-rasterizer', '--hide-scrollbars', '--no-first-run',
    '--allow-file-access-from-files', '--force-device-scale-factor=1',
    '--run-all-compositor-stages-before-draw', "--virtual-time-budget=$WaitMs",
    "--user-data-dir=$chromeProfile", "--window-size=$w,$h", "--screenshot=$outPath",
    '--enable-logging=stderr', '--v=0', $pageUri
  )
  $errLog = Join-Path $buildRoot 'chrome.log'
  $p = Start-Process -FilePath $chrome -ArgumentList $chromeArgs -PassThru -WindowStyle Hidden -RedirectStandardError $errLog
  if (-not $p.WaitForExit(180000)) { try { $p.Kill() } catch {}; throw 'Chrome timed out.' }
  Start-Sleep -Milliseconds 300

  $messages = @()
  if (Test-Path -LiteralPath $errLog) {
    $messages = @(Get-Content -LiteralPath $errLog -Encoding UTF8 | Where-Object { $_ -match 'POSTER-(GPU|WARN|ERROR)' } | ForEach-Object {
      if ($_ -match '"(POSTER-[^"]*)') { $Matches[1] } else { $_ }
    })
  }
  $gpuLine = $messages | Where-Object { $_ -like '*POSTER-GPU *' } | Select-Object -First 1
  $errors = @($messages | Where-Object { $_ -like '*POSTER-ERROR*' })

  # GPU-only: a page that did not confirm a hardware renderer never produces a deliverable.
  if ($errors.Count -gt 0 -or -not $gpuLine) {
    if (Test-Path -LiteralPath $outPath) { Remove-Item -LiteralPath $outPath -Force }
    if ($errors.Count -gt 0) { throw ('Render failed: ' + ($errors -join '; ')) }
    throw 'Render failed: the page did not confirm a hardware GPU.'
  }
  if (-not (Test-Path -LiteralPath $outPath)) { throw 'Chrome did not write the screenshot.' }
  $messages | Where-Object { $_ -like '*POSTER-WARN*' } | ForEach-Object { Write-Output $_ }
  Write-Output ($gpuLine -replace '^.*POSTER-GPU ', 'GPU ')
  Add-Type -AssemblyName System.Drawing
  $img = [Drawing.Image]::FromFile($outPath)
  Write-Output ("OK {0} ({1}x{2})" -f $outPath, $img.Width, $img.Height)
  $img.Dispose()
}
finally {
  Remove-Item -LiteralPath $buildRoot -Recurse -Force -ErrorAction SilentlyContinue
}

