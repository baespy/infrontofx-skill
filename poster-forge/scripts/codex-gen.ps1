<#
  Generate character images with the user's Codex CLI (built-in image generator), one or many in parallel.

  Single job:
    codex-gen.ps1 -Ref src\a.jpg,src\a_face.jpg -Prompt "<text>" -Out work\ai\gang.png
  Batch (jobs.json = [{"ref":["a.jpg","a_face.jpg"],"out":"gang.png","prompt":"..."} , ...]):
    codex-gen.ps1 -Batch jobs.json

  What it does for you (all learned the hard way):
    - finds codex.exe in the newest openai.chatgpt VS Code extension (it is not on PATH)
    - passes the prompt on stdin ("-"), because -i swallows a positional prompt
    - gives every job its own working folder, so parallel jobs never mix their outputs
    - takes the result from the "generated_images" path in Codex's log (the file name Codex saves under varies)
    - refuses to run if the prompt file is suspiciously short (a PowerShell `+` inside @( ) once cut the prompt to its first part)
  Output is whatever Codex made (usually ~1000-1250 px, 1:1). Check it by eye; if Codex refuses or asks a question, the job reports it and nothing is written.
#>
param(
  [string[]]$Ref,
  [string]$Prompt,
  [string]$PromptFile,
  [string]$Out,
  [string]$Batch,
  [int]$TimeoutSec = 560
)
$ErrorActionPreference = 'Stop'
$ext = Get-ChildItem "$env:USERPROFILE\.vscode\extensions" -Directory -Filter 'openai.chatgpt-*' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$codex = $null
if ($ext) { $codex = Get-ChildItem $ext.FullName -Recurse -Filter 'codex.exe' -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName }
if (-not $codex) { throw 'codex.exe not found (install the OpenAI ChatGPT/Codex VS Code extension).' }

$jobs = @()
if ($Batch) {
  $list = Get-Content -LiteralPath $Batch -Raw -Encoding UTF8 | ConvertFrom-Json
  foreach ($j in $list) { $jobs += [pscustomobject]@{ Ref = @($j.ref); Out = [string]$j.out; Prompt = [string]$j.prompt } }
} else {
  if (-not $Out) { throw '-Out is required.' }
  if ($PromptFile) { $Prompt = Get-Content -LiteralPath $PromptFile -Raw -Encoding UTF8 }
  if (-not $Prompt) { throw 'Give -Prompt, -PromptFile or -Batch.' }
  $jobs += [pscustomobject]@{ Ref = $Ref; Out = $Out; Prompt = $Prompt }
}

$run = Join-Path $env:TEMP ('codex-gen-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $run | Out-Null
$procs = @()
$n = 0
foreach ($j in $jobs) {
  $n++
  if ($j.Prompt.Length -lt 200) { throw "Job $n prompt is only $($j.Prompt.Length) characters; build the full prompt string first." }
  $dir = Join-Path $run "job$n"; New-Item -ItemType Directory -Force -Path $dir | Out-Null
  $imgs = @()
  foreach ($r in $j.Ref) { if ($r) { $p = (Resolve-Path -LiteralPath $r).ProviderPath; $dst = Join-Path $dir ([IO.Path]::GetFileName($p)); Copy-Item -LiteralPath $p -Destination $dst -Force; $imgs += [IO.Path]::GetFileName($p) } }
  $pf = Join-Path $dir 'prompt.txt'
  [IO.File]::WriteAllText($pf, ($j.Prompt + "`nSave the final image as result.png in the current directory."), (New-Object Text.UTF8Encoding($false)))
  $argList = @('exec', '-s', 'workspace-write', '--skip-git-repo-check')
  foreach ($i in $imgs) { $argList += @('-i', ('"' + $i + '"')) }
  $argList += '-'
  $procs += [pscustomobject]@{ N = $n; Dir = $dir; Out = $j.Out; Start = Get-Date
    Proc = (Start-Process -FilePath $codex -ArgumentList ($argList -join ' ') -RedirectStandardInput $pf -RedirectStandardOutput (Join-Path $dir 'out.log') -RedirectStandardError (Join-Path $dir 'err.log') -PassThru -WindowStyle Hidden -WorkingDirectory $dir) }
}
$deadline = (Get-Date).AddSeconds($TimeoutSec)
foreach ($p in $procs) { $left = [int][Math]::Max(1, ($deadline - (Get-Date)).TotalSeconds); if (-not $p.Proc.WaitForExit($left * 1000)) { try { $p.Proc.Kill() } catch {} } }

$failed = 0
foreach ($p in $procs) {
  $found = $null
  $errLog = Join-Path $p.Dir 'err.log'
  if (Test-Path -LiteralPath $errLog) {
    $m = [regex]::Matches((Get-Content -LiteralPath $errLog -Raw -Encoding UTF8), '[A-Za-z]:\\\\?[^\r\n''"]*?generated_images\\\\?[^\r\n''"]*?\.png')
    if ($m.Count -gt 0) { $cand = ($m[$m.Count - 1].Value -replace '\\\\', '\'); if (Test-Path -LiteralPath $cand) { $found = $cand } }
  }
  if (-not $found) {
    $own = Get-ChildItem $p.Dir -File -Filter '*.png' -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch '^(IMG|ref)' } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($own) { $found = $own.FullName }
  }
  if ($found) {
    $o = [IO.Path]::GetFullPath($p.Out); New-Item -ItemType Directory -Force -Path (Split-Path -Parent $o) | Out-Null
    Copy-Item -LiteralPath $found -Destination $o -Force
    Write-Output "OK job$($p.N) -> $o"
  } else {
    $failed++
    $say = if (Test-Path -LiteralPath (Join-Path $p.Dir 'out.log')) { (Get-Content -LiteralPath (Join-Path $p.Dir 'out.log') -Encoding UTF8 | Select-Object -Last 3) -join ' | ' } else { '' }
    Write-Output "FAILED job$($p.N): no image. Codex said: $say"
  }
}
Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction SilentlyContinue
if ($failed) { exit 1 }
