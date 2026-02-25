# Packaging Guide

## 1. Single EXE (Windows)

From repo root:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_exe.ps1
```

Output:
- dist\industry_app.exe

Run:
```powershell
powershell -ExecutionPolicy Bypass -File packaging\run_exe.ps1
```

Notes:
- The EXE wraps Streamlit. It will start a local server; the console will show the URL.
- If you prefer another Python env, pass `-PythonExe`.

## 2. Docker

Build:
```bash
docker build -t industry-app .
```

Run:
```bash
docker run --rm -p 8501:8501 industry-app
```

Then open:
- http://localhost:8501

## 3. Requirements

Docker uses `requirements-ui.txt`.
EXE build installs Streamlit and analysis dependencies via the PowerShell script.
