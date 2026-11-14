$ErrorActionPreference = 'Stop'

function Import-PtfxLib {
    if ('WeaponForge.YptFile' -as [type]) { return }
    $src = @(Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.cs' | Sort-Object Name)
    if (-not $src) { throw "no .cs sources next to ptfx-lib.ps1" }
    $stamp = ($src | ForEach-Object { '{0}:{1}:{2}' -f $_.Name, $_.Length, $_.LastWriteTimeUtc.Ticks }) -join '|'
    $md5 = [Security.Cryptography.MD5]::Create()
    $key = ([BitConverter]::ToString($md5.ComputeHash([Text.Encoding]::UTF8.GetBytes($stamp))) -replace '-', '').Substring(0, 16)
    $cacheDir = Join-Path $env:TEMP 'weapon-forge-ptfx'
    if (-not (Test-Path -LiteralPath $cacheDir)) { New-Item -ItemType Directory -Force $cacheDir | Out-Null }
    $dll = Join-Path $cacheDir "ptfx-$key.dll"
    $refs = @('System.dll', 'System.Core.dll', 'System.Drawing.dll', 'System.Web.Extensions.dll', 'System.IO.Compression.dll')
    if (Test-Path -LiteralPath $dll) {
        try { Add-Type -Path $dll; return } catch { Remove-Item -LiteralPath $dll -Force -ErrorAction SilentlyContinue }
    }
    try {
        Add-Type -Path $src.FullName -ReferencedAssemblies $refs -OutputAssembly $dll -OutputType Library
        Add-Type -Path $dll
    } catch {
        Add-Type -Path $src.FullName -ReferencedAssemblies $refs
    }
}

function Test-Escrowed([string]$file) {
    $dir = Split-Path -Parent $file
    for ($i = 0; $i -lt 4 -and $dir; $i++) {
        if (Test-Path -LiteralPath (Join-Path $dir '.fxap')) { return $true }
        if (Test-Path -LiteralPath (Join-Path $dir 'fxmanifest.lua')) { return $false }
        $dir = Split-Path -Parent $dir
    }
    return $false
}
