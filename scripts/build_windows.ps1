# build_windows.ps1
# PowerShell script to build the pdal_filter executable on Windows.

$ErrorActionPreference = "Stop"

Write-Host "--- Starting Windows Build for pdal_filter ---" -ForegroundColor Cyan

# 1. Check prerequisites
Write-Host "Checking prerequisites..."
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found. Please install Python and add it to your PATH."
}

# 2. Setup virtual environment (optional but recommended)
$venvDir = ".venv-build"
if (!(Test-Path $venvDir)) {
    Write-Host "Creating virtual environment for build..."
    python -m venv $venvDir
}

Write-Host "Activating virtual environment..."
& "$venvDir\Scripts\Activate.ps1"

# 3. Install dependencies
Write-Host "Installing dependencies..."
python -m pip install --upgrade pip
# Install pyinstaller and pdal. 
# We assume the current project's dependencies are also needed.
python -m pip install pyinstaller pdal
if (Test-Path "pyproject.toml") {
    # If using a project with dependencies, install them
    python -m pip install .
}

# 4. Run PyInstaller
Write-Host "Running PyInstaller..."
$specFile = "packaging/pdal_filter.spec"
if (!(Test-Path $specFile)) {
    Write-Error "Spec file not found at $specFile"
}

pyinstaller --clean $specFile

# 5. Sanity Check
Write-Host "Verifying build..."
$exeDir = "dist/pdal_filter"
$exePath = Join-Path $exeDir "pdal_filter.exe"
if (Test-Path $exePath) {
    Write-Host "Build successful! Executable found at $exePath" -ForegroundColor Green
    
    # Try to run --help
    Write-Host "Running sanity check (--help)..."
    & $exePath --help
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Sanity check passed." -ForegroundColor Green
    } else {
        Write-Warning "Sanity check failed with exit code $LASTEXITCODE. The EXE may have runtime issues (e.g. missing DLLs)."
    }
} else {
    Write-Error "Build failed. Executable not found at $exePath"
}

Write-Host "--- Build Process Finished ---"
