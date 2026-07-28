param(
    [switch]$Dev
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating Python virtual environment: .venv"

    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3 -m venv .venv
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv .venv
    }
    else {
        throw "Python was not found. Install Python 3.11 or 3.12 first."
    }
}
else {
    Write-Host "Virtual environment already exists: .venv"
}

& $VenvPython -m pip install --upgrade pip

if ($Dev) {
    Write-Host "Installing development dependencies..."
    & $VenvPython -m pip install -r requirements-dev.txt
}
else {
    Write-Host "Installing runtime dependencies..."
    & $VenvPython -m pip install -r requirements.txt
}

Write-Host ""
Write-Host "Environment setup complete."
Write-Host "Activate it with:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "Run the application with:"
Write-Host "  .\.venv\Scripts\python.exe .\app.py"
