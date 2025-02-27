@echo off
echo Installing PyMuPDF for enhanced table extraction...
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

REM Install PyMuPDF
echo Installing PyMuPDF and its dependencies...
pip install pymupdf>=1.22.0

if %errorlevel% neq 0 (
    echo Failed to install PyMuPDF. Please check your internet connection and try again.
    pause
    exit /b 1
)

echo.
echo PyMuPDF has been successfully installed!
echo You can now use the enhanced table extraction feature in the application.
echo.
pause 