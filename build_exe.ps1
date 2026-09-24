param(
    [switch]$PackageOnly
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$IconPath = Join-Path $ProjectRoot "resources\icons\app.ico"
$DistAppDir = Join-Path $ProjectRoot "dist\GFileStudio"
$DistExe = Join-Path $DistAppDir "GFileStudio.exe"

function Assert-GFileStudioNotRunning {
    $running = Get-Process -Name "GFileStudio" -ErrorAction SilentlyContinue
    if ($running) {
        $pids = ($running | ForEach-Object { $_.Id }) -join ", "
        throw "GFileStudio.exe is still running (PID: $pids). Close the running application first, then run this script again. If the EXE is already built, use: .\build_exe.ps1 -PackageOnly"
    }
}

function Wait-DirectoryFilesUnlocked {
    param(
        [Parameter(Mandatory = $true)][string]$Directory,
        [int]$RetryCount = 10,
        [int]$DelayMilliseconds = 500
    )

    for ($attempt = 1; $attempt -le $RetryCount; $attempt++) {
        $locked = New-Object System.Collections.Generic.List[string]
        foreach ($file in Get-ChildItem -LiteralPath $Directory -Recurse -File) {
            $stream = $null
            try {
                $stream = [System.IO.File]::Open(
                    $file.FullName,
                    [System.IO.FileMode]::Open,
                    [System.IO.FileAccess]::Read,
                    [System.IO.FileShare]::None
                )
            }
            catch {
                $locked.Add($file.FullName)
            }
            finally {
                if ($null -ne $stream) {
                    $stream.Dispose()
                }
            }
        }

        if ($locked.Count -eq 0) {
            return
        }

        if ($attempt -lt $RetryCount) {
            Write-Host "Waiting for build files to be released ($attempt/$RetryCount)..."
            Start-Sleep -Milliseconds $DelayMilliseconds
            continue
        }

        $preview = ($locked | Select-Object -First 8) -join [Environment]::NewLine
        throw "Cannot package because build files are still in use:`n$preview`nClose GFileStudio.exe or any process using the dist folder, then retry with: .\build_exe.ps1 -PackageOnly"
    }
}

function Test-ZipArchive {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }
    if ((Get-Item -LiteralPath $Path).Length -le 0) {
        return $false
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = $null
    try {
        $archive = [System.IO.Compression.ZipFile]::OpenRead($Path)
        return $archive.Entries.Count -gt 0
    }
    catch {
        return $false
    }
    finally {
        if ($null -ne $archive) {
            $archive.Dispose()
        }
    }
}

Assert-GFileStudioNotRunning

if (-not $PackageOnly) {
    if (-not (Test-Path $VenvPython)) {
        & (Join-Path $ProjectRoot "setup_env.ps1") -Dev
    }
    else {
        & $VenvPython -m pip install -r requirements-dev.txt
    }

    if (-not (Test-Path $IconPath)) {
        throw "Cannot find application icon: $IconPath"
    }

    $PySideCodecvtPath = Join-Path $VenvPython "..\..\Lib\site-packages\PySide6\msvcp140_codecvt_ids.dll"
    if (-not (Test-Path $PySideCodecvtPath)) {
        throw "Cannot find PySide6 runtime library: $PySideCodecvtPath"
    }

    & $VenvPython -m PyInstaller --noconfirm --clean --windowed --name "GFileStudio" `
      --icon "$IconPath" `
      --add-data "resources;resources" `
      --add-data "config;config" `
      --add-binary "$PySideCodecvtPath;PySide6" `
      --collect-all "paramiko" `
      --collect-all "cryptography" `
      app.py

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path -LiteralPath $DistExe -PathType Leaf)) {
    if ($PackageOnly) {
        throw "Cannot find built executable: $DistExe. Run .\build_exe.ps1 once without -PackageOnly first."
    }
    throw "Build finished without producing the expected executable: $DistExe"
}

if (-not (Test-Path $VenvPython)) {
    throw "Cannot read application version because virtual environment Python was not found: $VenvPython"
}

$Version = (& $VenvPython -c "import g_file_studio; print(g_file_studio.__version__)" | Select-Object -Last 1).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($Version)) {
    throw "Cannot read G File Studio version."
}

$ReleaseDir = Join-Path $ProjectRoot "release"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
$ZipName = "GFileStudio_v" + $Version + "_Windows_x64.zip"
$ZipPath = Join-Path $ReleaseDir $ZipName

Assert-GFileStudioNotRunning
Wait-DirectoryFilesUnlocked -Directory $DistAppDir

if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

try {
    Compress-Archive `
        -Path $DistAppDir `
        -DestinationPath $ZipPath `
        -CompressionLevel Optimal `
        -ErrorAction Stop

    if (-not (Test-ZipArchive -Path $ZipPath)) {
        throw "ZIP verification failed: $ZipPath"
    }
}
catch {
    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force -ErrorAction SilentlyContinue
    }
    throw "Packaging failed. No valid share package was produced. $($_.Exception.Message)"
}

Write-Host "Build complete: dist\GFileStudio\GFileStudio.exe"
Write-Host "Share package verified: $ZipPath"
