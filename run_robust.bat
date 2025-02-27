@echo off
echo SQLGpt Robust Application Launcher
echo ================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.10 or higher
    pause
    exit /b 1
)

echo Starting SQLGpt with enhanced error handling...
echo.
echo If the application crashes, details will be shown in this window.
echo.

REM Run the robust version of the application
python run_robust.py

echo.
echo Application has exited.
echo.
pause 