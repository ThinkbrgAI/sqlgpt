@echo off
echo ========================================================
echo SQLGpt Installation Script
echo ========================================================
echo This script will install all required components:
echo  - MarkItDown for document conversion
echo  - PyMuPDF for enhanced table extraction
echo  - All other required dependencies
echo.
echo Installation may take a few minutes...
echo.

REM Check if Python is installed
echo Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.10 or higher from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

REM Check Python version
for /f "tokens=2" %%I in ('python --version 2^>^&1') do set PYTHON_VERSION=%%I
echo Found Python %PYTHON_VERSION%

REM Check if pip is installed
echo Checking pip installation...
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: pip is not installed or not in PATH.
    echo Please make sure pip is installed with your Python installation.
    pause
    exit /b 1
)

REM Install all required packages except MarkItDown
echo.
echo Installing base requirements...
pip install PyQt6>=6.4.0 aiosqlite>=0.19.0 pandas>=2.0.0 aiohttp>=3.8.0 openai>=1.0.0 anthropic>=0.7.0 python-dotenv>=1.0.0 tiktoken>=0.5.0 openpyxl>=3.1.0 PyPDF2>=3.0.0

if %errorlevel% neq 0 (
    echo ERROR: Failed to install base requirements.
    echo Please check your internet connection and try again.
    pause
    exit /b 1
)

REM Install MarkItDown
echo.
echo Installing MarkItDown...
pip install markitdown==0.0.1a4

if %errorlevel% neq 0 (
    echo ERROR: Failed to install MarkItDown.
    echo Please check your internet connection and try again.
    pause
    exit /b 1
)

REM Verify PyMuPDF installation
echo.
echo Installing PyMuPDF for enhanced table extraction...
pip install pymupdf>=1.22.0
    
if %errorlevel% neq 0 (
    echo ERROR: Failed to install PyMuPDF.
    echo Please check your internet connection and try again.
    pause
    exit /b 1
)

REM Run a quick test to verify everything is working
echo.
echo Running a quick test to verify installation...
python -c "from markitdown import MarkItDown; md = MarkItDown(); import fitz; print('All components are installed and working correctly!')" 2>nul

if %errorlevel% neq 0 (
    echo WARNING: Test failed. Some components may not be installed correctly.
    echo You can still try running the application, but you may encounter issues.
) else (
    echo.
    echo ========================================================
    echo Installation completed successfully!
    echo ========================================================
    echo.
    echo All required components have been installed:
    echo  - MarkItDown for document conversion
    echo  - PyMuPDF for enhanced table extraction
    echo  - All other required dependencies
    echo.
    echo To run the application, use the following command:
    echo    python run.py
    echo.
    echo Or simply double-click the run.bat file.
    echo.
    echo For enhanced table extraction from PDFs:
    echo  1. Open the application
    echo  2. Click "Convert Folder to MD" or "Convert Files to MD"
    echo  3. Select your PDF files
    echo  4. The application will automatically use PyMuPDF for table extraction
    echo.
)

pause 