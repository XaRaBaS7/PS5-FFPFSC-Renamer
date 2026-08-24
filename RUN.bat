@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo  PS5 FFPFSC Renamer - Development Launcher
echo ============================================================
echo.

where py >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python Launcher ^(py.exe^) was not found.
    echo Install Python 3.11 or newer from python.org and try again.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creating Python virtual environment...
    py -3.11 -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create a Python 3.11 virtual environment.
        echo Make sure Python 3.11 or newer is installed.
        pause
        exit /b 1
    )
) else (
    echo [1/4] Virtual environment already exists.
)

echo [2/4] Updating pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :install_error

echo [3/4] Installing PS5 FFPFSC Renamer and MkPFS 0.0.9...
".venv\Scripts\python.exe" -m pip install -e . "mkpfs==0.0.9"
if errorlevel 1 goto :install_error

echo [4/4] Starting GUI...
echo.
".venv\Scripts\python.exe" -m ps5_ffpfsc_renamer.gui
exit /b %errorlevel%

:install_error
echo.
echo [ERROR] Dependency installation failed.
echo Check the output above and your Internet connection.
pause
exit /b 1
