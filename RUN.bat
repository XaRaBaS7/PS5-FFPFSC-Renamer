@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================================
echo  PS5 FFPFSC Renamer - Development Launcher
echo ============================================================
echo.

set "PY_CMD="
set "PY_LABEL="

rem ------------------------------------------------------------
rem Find a usable Python runtime. The application requires 3.11+.
rem Prefer the Windows Python Launcher when available, but do not
rem require exactly Python 3.11: 3.12, 3.13, 3.14, etc. are valid.
rem ------------------------------------------------------------
where py >nul 2>&1
if not errorlevel 1 (
    for %%V in (3.14 3.13 3.12 3.11) do (
        if not defined PY_CMD (
            py -%%V -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
            if not errorlevel 1 (
                set "PY_CMD=py -%%V"
                set "PY_LABEL=Python %%V via py.exe"
            )
        )
    )
)

rem Fall back to python.exe on PATH.
if not defined PY_CMD (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
        if not errorlevel 1 (
            set "PY_CMD=python"
            for /f "delims=" %%P in ('python --version 2^>^&1') do set "PY_LABEL=%%P via PATH"
        )
    )
)

if not defined PY_CMD goto :python_missing

echo [OK] Using !PY_LABEL!
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creating Python virtual environment...
    !PY_CMD! -m venv .venv
    if errorlevel 1 (
        echo.
        echo [ERROR] Could not create the virtual environment.
        echo Runtime selected: !PY_LABEL!
        pause
        exit /b 1
    )
) else (
    echo [1/4] Virtual environment already exists.
)

rem Validate an existing .venv too, in case it was created with an old Python.
".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] The existing .venv uses Python older than 3.11.
    echo Delete the .venv folder and run RUN.bat again.
    pause
    exit /b 1
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

:python_missing
echo [ERROR] No supported Python runtime was found.
echo.
echo PS5 FFPFSC Renamer requires Python 3.11 or newer.
echo.
echo Detected runtimes from the Windows Python Launcher:
where py >nul 2>&1
if errorlevel 1 (
    echo   py.exe not found
) else (
    py -0p 2>nul
)
echo.
echo Install a 64-bit Python 3.11 or newer, then run RUN.bat again.
echo Recommended: Python 3.13 x64 from python.org.
echo During installation enable "Add python.exe to PATH" if offered.
echo.
pause
exit /b 1

:install_error
echo.
echo [ERROR] Dependency installation failed.
echo Check the output above and your Internet connection.
pause
exit /b 1
