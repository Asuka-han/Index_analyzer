param(
    [string]$PythonExe = "C:\\Miniforge3\\envs\\py312\\python.exe",
    [string]$Entry = "ui\\industry_app.py",
    [string]$Name = "industry_app"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $PythonExe)) {
    throw "Python not found: $PythonExe"
}

& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install pyinstaller streamlit matplotlib pandas numpy openpyxl akshare

& $PythonExe -m PyInstaller `
    --onefile `
    --name $Name `
    --clean `
    --noconfirm `
    $Entry

Write-Host "EXE build complete. Output in dist\\$Name.exe"
