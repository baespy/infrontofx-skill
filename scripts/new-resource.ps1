param(
    [Parameter(Mandatory = $true)]
    [string]$Name,
    [string]$Destination = (Get-Location).Path,
    [string]$Controller
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$template = Join-Path $root "templates\resource"

if (-not $Controller) {
    $core = $Name -replace "^infrontofx[_-]", ""
    $Controller = ($core -split "[_\-\s]+" | Where-Object { $_ } | ForEach-Object {
        $_.Substring(0, 1).ToUpper() + $_.Substring(1)
    }) -join ""
}

if ($Controller -notmatch "^[A-Z][A-Za-z0-9]*$") {
    throw "Controller name '$Controller' is not PascalCase. Pass -Controller explicitly."
}

$target = Join-Path $Destination $Name
if (Test-Path $target) {
    throw "Target already exists: $target"
}

Copy-Item -Path $template -Destination $target -Recurse

$utf8 = New-Object System.Text.UTF8Encoding $false
Get-ChildItem -Path $target -Recurse -File -Include *.lua, *.html, *.js, *.css, *.md, *.sql | ForEach-Object {
    $text = [System.IO.File]::ReadAllText($_.FullName)
    $new = $text -creplace "TemplateServer", "${Controller}Server"
    $new = $new -creplace "\bTemplate\b", $Controller
    $new = $new -creplace "infrontofx_template", $Name
    if ($new -ne $text) {
        [System.IO.File]::WriteAllText($_.FullName, $new, $utf8)
    }
}

Write-Host "Created $target" -ForegroundColor Green
Write-Host "  client controller: $Controller"
Write-Host "  server controller: ${Controller}Server"
Write-Host "Next: edit config/config.lua, then run: node `"$root\scripts\lint-resource.mjs`" `"$target`""

