# EXE Packaging

Two options are provided:

## Option A: Simple onefile build

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_exe.ps1
```

## Option B: Spec-based build (recommended for bundled data files)

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_exe_with_spec.ps1
```

The spec build includes:
- ui/
- src/
- data/
- result/
- 高频宏观数据指标库.xlsx

Run:
```powershell
powershell -ExecutionPolicy Bypass -File packaging\run_exe.ps1
```

The console will show the local Streamlit URL.
