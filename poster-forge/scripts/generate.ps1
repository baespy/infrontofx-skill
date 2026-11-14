<#
  Generate a character, prop or background image with a Gemini image model.
  Usage:
    generate.ps1 -PromptFile hero.prompt.txt -Out hero_raw.png -Ref me.jpg,mood.jpg -Aspect 1:1
    generate.ps1 -Prompt "..." -Out bg.png -Aspect 16:9 -Size 2K -Model fast -Count 2

  -Model   pro (Nano Banana Pro), fast (Nano Banana 2.1), or a full model id.
  -Ref     Up to 14 reference images, in the order the prompt refers to them.
  An existing -Out file is never overwritten: results are numbered instead.
  The API key comes from GEMINI_API_KEY and is never printed.
#>
param(
  [string]$Prompt,
  [string]$PromptFile,
  [Parameter(Mandatory = $true)][string]$Out,
  [string[]]$Ref = @(),
  [string]$Model = 'pro',
  [string]$Aspect = '1:1',
  [ValidateSet('1K', '2K', '4K')][string]$Size = '2K',
  [ValidateRange(1, 4)][int]$Count = 1,
  [string]$BaseUrl = 'https://generativelanguage.googleapis.com/v1beta/interactions',
  [int]$TimeoutSec = 300
)
$ErrorActionPreference = 'Stop'

$models = @{ 'pro' = 'gemini-3-pro-image'; 'fast' = 'gemini-nano-banana-2.1' }
$prices = @{
  'gemini-3-pro-image'     = @{ '1K' = 0.134; '2K' = 0.134; '4K' = 0.24 }
  'gemini-nano-banana-2.1' = @{ '1K' = 0.0336; '2K' = 0.0504; '4K' = 0.113 }
}
$modelId = if ($models.ContainsKey($Model)) { $models[$Model] } else { $Model }

function Get-ApiKey {
  # A key saved with setx is not in the environment of processes that were already running.
  foreach ($scope in 'Process', 'User', 'Machine') {
    $value = [Environment]::GetEnvironmentVariable('GEMINI_API_KEY', $scope)
    if ($value) { return $value }
  }
  throw 'GEMINI_API_KEY is not set. Ask the user to create a key at https://aistudio.google.com/apikey and save it with setx. Never ask for the key in chat.'
}

function Get-ImageType([byte[]]$b) {
  if ($b.Length -ge 4 -and $b[0] -eq 0x89 -and $b[1] -eq 0x50 -and $b[2] -eq 0x4E -and $b[3] -eq 0x47) { return @{ mime = 'image/png'; ext = '.png' } }
  if ($b.Length -ge 3 -and $b[0] -eq 0xFF -and $b[1] -eq 0xD8 -and $b[2] -eq 0xFF) { return @{ mime = 'image/jpeg'; ext = '.jpg' } }
  if ($b.Length -ge 12 -and $b[0] -eq 0x52 -and $b[1] -eq 0x49 -and $b[2] -eq 0x46 -and $b[3] -eq 0x46 -and $b[8] -eq 0x57 -and $b[9] -eq 0x45 -and $b[10] -eq 0x42 -and $b[11] -eq 0x50) { return @{ mime = 'image/webp'; ext = '.webp' } }
  return $null
}

function Find-Images($node) {
  # Walks the response so both the steps and outputs shapes work. Draft images from thinking are skipped.
  if ($null -eq $node -or $node -is [string] -or $node -is [ValueType]) { return }
  if ($node -is [Array]) { foreach ($entry in $node) { Find-Images $entry }; return }
  $names = @($node.PSObject.Properties | ForEach-Object { $_.Name })
  if ($names -contains 'thought' -and $node.thought -eq $true) { return }
  if ($names -contains 'type' -and $node.type -in 'thought', 'thinking') { return }
  if ($names -contains 'type' -and $node.type -eq 'image' -and $names -contains 'data' -and $node.data) { $node.data; return }
  foreach ($inline in 'inlineData', 'inline_data') {
    if ($names -contains $inline -and $node.$inline.data) { $node.$inline.data; return }
  }
  foreach ($name in $names) { Find-Images $node.$name }
}

function Get-FreePath([string]$path) {
  if (-not (Test-Path -LiteralPath $path)) { return $path }
  $dir = Split-Path -Parent $path
  $stem = [IO.Path]::GetFileNameWithoutExtension($path)
  $ext = [IO.Path]::GetExtension($path)
  for ($n = 2; ; $n++) {
    $candidate = Join-Path $dir ("{0}-{1}{2}" -f $stem, $n, $ext)
    if (-not (Test-Path -LiteralPath $candidate)) { return $candidate }
  }
}

if ($PromptFile) { $Prompt = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $PromptFile).ProviderPath, [Text.Encoding]::UTF8) }
if ([string]::IsNullOrWhiteSpace($Prompt)) { throw 'Provide -Prompt or -PromptFile.' }
if ($Ref.Count -gt 14) { throw 'Gemini accepts at most 14 reference images.' }

$input_parts = New-Object Collections.ArrayList
[void]$input_parts.Add(@{ type = 'text'; text = $Prompt })
$totalBytes = 0
foreach ($file in $Ref) {
  $bytes = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $file).ProviderPath)
  $kind = Get-ImageType $bytes
  if (-not $kind) { throw "Reference is not a PNG, JPEG or WebP image: $file" }
  $totalBytes += $bytes.Length
  [void]$input_parts.Add(@{ type = 'image'; mime_type = $kind.mime; data = [Convert]::ToBase64String($bytes) })
}
if ($totalBytes -gt 18MB) { throw 'References exceed 18 MB in total. Use fewer or smaller images.' }

$key = Get-ApiKey
# the fast model only returns JPEG; the pro model returns PNG
$outMime = if ($Model -eq 'fast') { 'image/jpeg' } else { 'image/png' }
$body = @{
  model           = $modelId
  input           = $input_parts
  response_format = @{ type = 'image'; mime_type = $outMime; aspect_ratio = $Aspect; image_size = $Size }
} | ConvertTo-Json -Depth 8 -Compress

Add-Type -AssemblyName System.Net.Http
$client = New-Object Net.Http.HttpClient
$client.Timeout = [TimeSpan]::FromSeconds($TimeoutSec)
$outPath = [IO.Path]::GetFullPath($Out)
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outPath) | Out-Null
$saved = 0
try {
  for ($run = 1; $run -le $Count; $run++) {
    $request = New-Object Net.Http.HttpRequestMessage ([Net.Http.HttpMethod]::Post), ([Uri]$BaseUrl)
    [void]$request.Headers.TryAddWithoutValidation('x-goog-api-key', $key)
    [void]$request.Headers.TryAddWithoutValidation('Api-Revision', '2026-05-20')
    $request.Content = New-Object Net.Http.StringContent $body, ([Text.Encoding]::UTF8), 'application/json'
    $response = $client.SendAsync($request).GetAwaiter().GetResult()
    $text = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()

    if (-not $response.IsSuccessStatusCode) {
      $detail = $text
      try { $detail = ($text | ConvertFrom-Json).error.message } catch {}
      throw ("API error {0}: {1}" -f [int]$response.StatusCode, $detail)
    }

    $images = @(Find-Images ($text | ConvertFrom-Json))
    if ($images.Count -eq 0) {
      $preview = $text.Substring(0, [Math]::Min(800, $text.Length))
      throw "The API returned no image (often a safety block). Response: $preview"
    }
    foreach ($b64 in $images) {
      $bytes = [Convert]::FromBase64String($b64)
      $kind = Get-ImageType $bytes
      $target = $outPath
      if ($kind -and [IO.Path]::GetExtension($target) -ne $kind.ext) { $target = [IO.Path]::ChangeExtension($target, $kind.ext) }
      $target = Get-FreePath $target
      [IO.File]::WriteAllBytes($target, $bytes)
      $saved++
      Write-Output ("OK {0} ({1:N0} KB)" -f $target, ($bytes.Length / 1KB))
    }
  }
}
finally { $client.Dispose() }

if ($prices.ContainsKey($modelId)) {
  Write-Output ("MODEL {0} {1}, about USD {2:N3} for this run" -f $modelId, $Size, ($prices[$modelId][$Size] * $saved))
}
else { Write-Output "MODEL $modelId $Size" }
