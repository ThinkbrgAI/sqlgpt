@echo off
echo Setting up environment...

REM Check if virtual environment exists
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies if needed
if not exist venv\Lib\site-packages\PyQt6 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

echo Starting application...
python run.py

REM Deactivate virtual environment on exit
deactivate 