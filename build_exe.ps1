$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    & (Join-Path $ProjectRoot "setup_env.ps1") -Dev
}
else {
    & $VenvPython -m pip install -r requirements-dev.txt
}

& $VenvPython -m PyInstaller --noconfirm --clean --windowed --name "GFileStudio" `
  --add-data "resources;resources" `
  --add-data "config;config" `
  app.py

Write-Host "Build complete: dist\GFileStudio\GFileStudio.exe"
