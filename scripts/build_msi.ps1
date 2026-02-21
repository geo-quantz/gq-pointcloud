# build_msi.ps1
# PowerShell script to build the MSI installer for pdal_filter.
# Requires WiX Toolset v3 to be installed and in PATH.

$ErrorActionPreference = "Stop"

Write-Host "--- Starting MSI Build for pdal_filter ---" -ForegroundColor Cyan

# 1. Check for EXE
$exePath = "dist/pdal_filter.exe"
if (!(Test-Path $exePath)) {
    Write-Error "Executable not found at $exePath. Please run scripts/build_windows.ps1 first."
}

# 2. Check for WiX
if (!(Get-Command candle -ErrorAction SilentlyContinue) -or !(Get-Command light -ErrorAction SilentlyContinue)) {
    Write-Error "WiX Toolset (candle.exe, light.exe) not found. Please install WiX Toolset v3."
}

# 3. Compile and Link
Write-Host "Compiling WiX source..."
candle.exe packaging/pdal_filter.wxs -o packaging/pdal_filter.wixobj

Write-Host "Linking MSI..."
light.exe packaging/pdal_filter.wixobj -o dist/pdal_filter.msi

Write-Host "MSI build successful! File found at dist/pdal_filter.msi" -ForegroundColor Green
