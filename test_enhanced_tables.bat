@echo off
echo Running Enhanced Table Extraction Test Script...
echo.

python test_enhanced_tables.py

if %errorlevel% neq 0 (
    echo.
    echo Test script failed to run. Please make sure Python is installed and in your PATH.
    pause
    exit /b 1
)

exit /b 0 