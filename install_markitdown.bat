@echo off
echo Installing MarkItDown for local document conversion...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not in PATH. Please install Python 3.10 or higher.
    pause
    exit /b 1
)

REM Check if pip is installed
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo pip is not installed or not in PATH. Please install pip.
    pause
    exit /b 1
)

REM Install MarkItDown
echo Installing MarkItDown and its dependencies...
pip install markitdown>=0.0.2

if %errorlevel% neq 0 (
    echo Failed to install MarkItDown. Please check your internet connection and try again.
    pause
    exit /b 1
)

echo.
echo MarkItDown has been successfully installed!
echo You can now use the local document conversion feature in the application.
echo.
pause 