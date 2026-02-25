param(
    [string]$ExePath = "dist\\industry_app.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ExePath)) {
    throw "EXE not found: $ExePath"
}

& $ExePath
