@echo off
echo Installing test dependencies...
pip install -r requirements.txt
pip install -r requirements-test.txt

echo Creating test directories...
if not exist tests\test_data mkdir tests\test_data
if not exist tests\test_data\subfolder mkdir tests\test_data\subfolder

echo Running tests...
python run_tests.py

echo Cleaning up...
if exist test.db del test.db
if exist export.xlsx del export.xlsx

echo Done! 