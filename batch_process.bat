@echo off
echo SQLGpt Batch Processing Tool
echo ===========================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.10 or higher
    pause
    exit /b 1
)

REM Get the input directory from command line or prompt user
set INPUT_DIR=%1
if "%INPUT_DIR%"=="" (
    set /p INPUT_DIR="Enter the directory containing files to process: "
)

REM Check if the directory exists
if not exist "%INPUT_DIR%" (
    echo Error: Directory "%INPUT_DIR%" does not exist
    pause
    exit /b 1
)

REM Get the output directory (optional)
set OUTPUT_DIR=%2
if "%OUTPUT_DIR%"=="" (
    echo Output will be saved in the same directory as input files
    set OUTPUT_PARAM=
) else (
    echo Output will be saved in: %OUTPUT_DIR%
    set OUTPUT_PARAM=--output-dir "%OUTPUT_DIR%"
)

echo.
echo Starting batch processing...
echo.

REM Run the batch processing script
python batch_process.py "%INPUT_DIR%" %OUTPUT_PARAM% --recursive

echo.
echo Batch processing completed
echo.
pause 