@echo off
setlocal enabledelayedexpansion

echo --- gq-pointcloud Windows Setup ---

:: 1. Python Check
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+.
    pause
    exit /b 1
)

:: 2. Create Virtual Environment
set VENV_DIR=.venv
if not exist %VENV_DIR% (
    echo Creating virtual environment...
    python -m venv %VENV_DIR%
)

:: 3. Install Dependencies
echo Installing dependencies...
%VENV_DIR%\Scripts\python -m pip install --upgrade pip
%VENV_DIR%\Scripts\python -m pip install .

:: 4. PDAL DLL Discovery (Optional but helpful)
echo Searching for PDAL DLLs...
set PDAL_BIN_PATH=
:: Try to find PDAL in Conda environments
for /f "tokens=*" %%i in ('where pdal 2^>nul') do (
    set "PDAL_EXE_PATH=%%i"
    set "PDAL_BIN_PATH=!PDAL_EXE_PATH:\pdal.exe=!"
)

if "!PDAL_BIN_PATH!"=="" (
    :: Check common Conda paths if 'where' failed
    if exist "%USERPROFILE%\miniconda3\envs\gq-pdal\Library\bin" (
        set "PDAL_BIN_PATH=%USERPROFILE%\miniconda3\envs\gq-pdal\Library\bin"
    )
)

if not "!PDAL_BIN_PATH!"=="" (
    echo [INFO] Found PDAL DLLs at: !PDAL_BIN_PATH!
    echo [INFO] Setting PDAL_LIBRARY_PATH in virtual environment...
    
    :: Append environment variable to activate.bat
    findstr /C:"set PDAL_LIBRARY_PATH=" %VENV_DIR%\Scripts\activate.bat >nul
    if %errorlevel% neq 0 (
        echo set "PDAL_LIBRARY_PATH=!PDAL_BIN_PATH!" >> %VENV_DIR%\Scripts\activate.bat
    )
    
    :: For PowerShell
    findstr /C:"$env:PDAL_LIBRARY_PATH =" %VENV_DIR%\Scripts\Activate.ps1 >nul
    if %errorlevel% neq 0 (
        echo $env:PDAL_LIBRARY_PATH = "!PDAL_BIN_PATH!" >> %VENV_DIR%\Scripts\Activate.ps1
    )
) else (
    echo [WARNING] PDAL DLLs not found automatically.
    echo [WARNING] Please set PDAL_LIBRARY_PATH manually if you encounter DLL load errors.
)

echo.
echo --- Setup Complete ---
echo To activate the environment, run: .venv\Scripts\activate
pause
