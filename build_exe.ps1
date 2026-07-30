$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$IconPath = Join-Path $ProjectRoot "resources\icons\app.ico"

if (-not (Test-Path $VenvPython)) {
    & (Join-Path $ProjectRoot "setup_env.ps1") -Dev
}
else {
    & $VenvPython -m pip install -r requirements-dev.txt
}

if (-not (Test-Path $IconPath)) {
    throw "找不到程序图标：$IconPath"
}

& $VenvPython -m PyInstaller --noconfirm --clean --windowed --name "GFileStudio" `
  --icon "$IconPath" `
  --add-data "resources;resources" `
  --add-data "config;config" `
  app.py

$ReleaseDir = Join-Path $ProjectRoot "release"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
$ZipPath = Join-Path $ReleaseDir "GFileStudio_v2.8.0_Windows_x64.zip"
if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}
Compress-Archive -Path (Join-Path $ProjectRoot "dist\GFileStudio") -DestinationPath $ZipPath

Write-Host "Build complete: dist\GFileStudio\GFileStudio.exe"
Write-Host "Share package: $ZipPath"
