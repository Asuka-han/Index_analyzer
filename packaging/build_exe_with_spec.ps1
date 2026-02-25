param(
    [string]$PythonExe = "C:\\Miniforge3\\envs\\py312\\python.exe",
    [string]$SpecFile = "packaging\\industry_app.spec"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $PythonExe)) {
    throw "Python not found: $PythonExe"
}

& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install pyinstaller streamlit matplotlib pandas numpy openpyxl akshare

& $PythonExe -m PyInstaller `
    --clean `
    --noconfirm `
    $SpecFile

Write-Host "EXE build complete. Output in dist\\industry_app.exe"
