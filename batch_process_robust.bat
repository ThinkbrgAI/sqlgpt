@echo off
echo SQLGpt Robust Batch Processing Tool
echo =================================
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

REM Ask if user wants to resume from previous run
set /p RESUME_OPTION="Resume from previous run? (y/n): "
if /i "%RESUME_OPTION%"=="y" (
    set RESUME_PARAM=--resume
    echo Will resume from previous run
) else (
    set RESUME_PARAM=
    echo Starting fresh run
)

REM Ask if user wants to process recursively
set /p RECURSIVE_OPTION="Process subdirectories recursively? (y/n): "
if /i "%RECURSIVE_OPTION%"=="y" (
    set RECURSIVE_PARAM=--recursive
    echo Will process subdirectories recursively
) else (
    set RECURSIVE_PARAM=
    echo Will only process files in the top directory
)

REM Ask for advanced options
set /p ADVANCED_OPTION="Configure advanced options? (y/n): "
if /i "%ADVANCED_OPTION%"=="y" (
    REM Get max retries
    set /p MAX_RETRIES="Maximum retry attempts (default: 3): "
    if "%MAX_RETRIES%"=="" (
        set MAX_RETRIES=3
    )
    set MAX_RETRIES_PARAM=--max-retries %MAX_RETRIES%
    
    REM Get delay between files
    set /p DELAY="Delay between files in seconds (default: 1.0): "
    if "%DELAY%"=="" (
        set DELAY=1.0
    )
    set DELAY_PARAM=--delay %DELAY%
    
    REM Get garbage collection interval
    set /p GC_INTERVAL="Garbage collection interval (default: 5): "
    if "%GC_INTERVAL%"=="" (
        set GC_INTERVAL=5
    )
    set GC_INTERVAL_PARAM=--gc-interval %GC_INTERVAL%
    
    echo Using advanced options:
    echo - Max retries: %MAX_RETRIES%
    echo - Delay between files: %DELAY% seconds
    echo - Garbage collection interval: Every %GC_INTERVAL% files
) else (
    set MAX_RETRIES_PARAM=
    set DELAY_PARAM=
    set GC_INTERVAL_PARAM=
    echo Using default advanced options
)

echo.
echo Starting batch processing with enhanced error handling...
echo If the script crashes, you can restart it with the same parameters and use the resume option.
echo.

REM Run the batch processing script
python batch_process.py "%INPUT_DIR%" %OUTPUT_PARAM% %RESUME_PARAM% %RECURSIVE_PARAM% %MAX_RETRIES_PARAM% %DELAY_PARAM% %GC_INTERVAL_PARAM%

echo.
if %ERRORLEVEL% NEQ 0 (
    echo Batch processing encountered errors
    echo You can resume from where it left off by running this script again and selecting "y" for resume
) else (
    echo Batch processing completed successfully
)
echo.
pause 