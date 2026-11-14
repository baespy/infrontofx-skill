<#
  Generate or edit an image with the user's Antigravity CLI (Gemini image model on their subscription; no API key).
  One job:
    agy-gen.ps1 -Ref work\src\a.jpg -Prompt "<English prompt>" -Out work\ai\a_edit.png
  Several jobs in parallel (jobs.json = [{"ref":["a.jpg"],"out":"a.png","prompt":"..."}, ...]):
    agy-gen.ps1 -Batch jobs.json

  Why a wrapper: agy replies before the image exists, saves it under a name of its own in
  %USERPROFILE%\.gemini\antigravity-cli\brain\<id>\, and not at the path you ask for. This script snapshots that
  folder, runs agy, waits for the NEW image, and copies it to -Out. Results are ~900-1300 px JPEG/PNG: check by eye.
  If agy refuses or answers with text only, the job reports FAILED with what it said; do not work around a refusal.
#>
param(
  [string[]]$Ref,
  [string]$Prompt,
  [string]$PromptFile,
  [string]$Out,
  [string]$Batch,
  [int]$TimeoutSec = 420
)
$ErrorActionPreference = 'Stop'
$agy = Join-Path $env:USERPROFILE '.gemini\bin\agy.exe'
if (-not (Test-Path -LiteralPath $agy)) { throw 'agy.exe not found (Antigravity CLI).' }
$brain = Join-Path $env:USERPROFILE '.gemini\antigravity-cli\brain'

$jobs = @()
if ($Batch) {
  foreach ($j in (Get-Content -LiteralPath $Batch -Raw -Encoding UTF8 | ConvertFrom-Json)) { $jobs += [pscustomobject]@{ Ref = @($j.ref); Out = [string]$j.out; Prompt = [string]$j.prompt } }
} else {
  if (-not $Out) { throw '-Out is required.' }
  if ($PromptFile) { $Prompt = Get-Content -LiteralPath $PromptFile -Raw -Encoding UTF8 }
  if (-not $Prompt) { throw 'Give -Prompt, -PromptFile or -Batch.' }
  $jobs += [pscustomobject]@{ Ref = $Ref; Out = $Out; Prompt = $Prompt }
}

function Get-BrainImages {
  Get-ChildItem -LiteralPath $brain -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in '.jpg', '.jpeg', '.png' -and $_.FullName -notmatch '\\\.system_generated\\' } |
    Select-Object -ExpandProperty FullName
}

$before = @{}; foreach ($f in (Get-BrainImages)) { $before[$f] = $true }
$run = Join-Path $env:TEMP ('agy-gen-' + [Guid]::NewGuid().ToString('N')); New-Item -ItemType Directory -Force -Path $run | Out-Null
$procs = @(); $n = 0
foreach ($j in $jobs) {
  $n++
  if ($j.Prompt.Length -lt 200) { throw "Job $n prompt is only $($j.Prompt.Length) characters; build the full prompt string first." }
  # headless agy may only read inside its workspace: give every job its own folder (--add-dir) holding copies of the refs
  $jd = Join-Path $run "job$n"; New-Item -ItemType Directory -Force -Path $jd | Out-Null
  $refs = @(); foreach ($r in $j.Ref) { if ($r) { $src = (Resolve-Path -LiteralPath $r).ProviderPath; $dst = Join-Path $jd ([IO.Path]::GetFileName($src)); Copy-Item -LiteralPath $src -Destination $dst -Force; $refs += $dst } }
  $text = 'Use your image generation ability to create exactly ONE image, name the image file so its file name starts with job' + $n + '_, and do not edit any other file. '
  if ($refs.Count) { $text += 'Reference image file(s): ' + ($refs -join ' ; ') + '. Open them and use them as described. ' }
  $text += $j.Prompt
  $pf = Join-Path $run "job$n.txt"; [IO.File]::WriteAllText($pf, $text, (New-Object Text.UTF8Encoding($false)))
  # the prompt goes in as one argument; a file keeps quoting safe
  $arg = '--print "' + ($text -replace '"', "'") + '" --mode accept-edits --add-dir "' + $jd + '" --print-timeout ' + $TimeoutSec + 's'
  $procs += [pscustomobject]@{ N = $n; Out = $j.Out; Log = (Join-Path $run "job$n.log")
    Proc = (Start-Process -FilePath $agy -ArgumentList $arg -RedirectStandardOutput (Join-Path $run "job$n.log") -RedirectStandardError (Join-Path $run "job$n.err") -PassThru -WindowStyle Hidden) }
}
$deadline = (Get-Date).AddSeconds($TimeoutSec + 60)
foreach ($p in $procs) { $left = [int][Math]::Max(1, ($deadline - (Get-Date)).TotalSeconds); if (-not $p.Proc.WaitForExit($left * 1000)) { try { $p.Proc.Kill() } catch {} } }
Start-Sleep -Seconds 20   # agy often answers a little before the file lands

$new = @(Get-BrainImages | Where-Object { -not $before.ContainsKey($_) } | ForEach-Object { Get-Item -LiteralPath $_ } | Sort-Object LastWriteTime)
$failed = 0; $used = @{}
foreach ($p in $procs) {
  $pick = $null
  # take the oldest unused new image, in job order: parallel jobs finish in about the order they started, so verify by eye
  foreach ($f in $new) { if (-not $used.ContainsKey($f.FullName) -and $f.Name -match ('(?i)job' + $p.N + '(?!\d)')) { $pick = $f; break } }
  if (-not $pick) { foreach ($f in $new) { if (-not $used.ContainsKey($f.FullName) -and $f.Name -notmatch '(?i)job\d') { $pick = $f; break } } }
  if ($pick) {
    $used[$pick.FullName] = $true
    $o = [IO.Path]::GetFullPath($p.Out); New-Item -ItemType Directory -Force -Path (Split-Path -Parent $o) | Out-Null
    Copy-Item -LiteralPath $pick.FullName -Destination $o -Force
    Write-Output "OK job$($p.N) -> $o   (source $($pick.Name))"
  } else {
    $failed++
    $say = if (Test-Path -LiteralPath $p.Log) { (Get-Content -LiteralPath $p.Log -Encoding UTF8 | Select-Object -Last 4) -join ' | ' } else { '' }
    Write-Output "FAILED job$($p.N): no new image. agy said: $say"
  }
}
if ($failed) { Write-Output "LOGS kept in $run"; exit 1 } else { Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction SilentlyContinue }



