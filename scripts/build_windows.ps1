$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYINSTALLER_CONFIG_DIR = Join-Path $Root ".pyinstaller"
$env:MPLCONFIGDIR = Join-Path $Root ".mplconfig"

if (-not (Test-Path ".venv")) {
    py -3.14 -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pytest
& .\.venv\Scripts\pyinstaller.exe --noconfirm --clean VLE_GammaPhi.spec

Write-Host "Build onedir creado en dist\VLE_GammaPhi\VLE_GammaPhi.exe"
Write-Host "Valide esta versión antes de preparar la distribución onefile."
