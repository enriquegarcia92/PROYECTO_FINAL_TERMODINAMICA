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
& .\.venv\Scripts\pyinstaller.exe --noconfirm --clean VLE_GammaPhi_onefile.spec

Write-Host "Ejecutable único creado en dist\VLE_GammaPhi.exe"
Write-Host "Distribuya esta variante únicamente después de validar el build onedir."
