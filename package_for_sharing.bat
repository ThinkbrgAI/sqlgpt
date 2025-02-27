@echo off
echo ========================================================
echo SQLGpt Packaging Script
echo ========================================================
echo This script will package the application for sharing.
echo.

REM Create a directory for the package
set PACKAGE_DIR=SQLGpt_Package
echo Creating package directory: %PACKAGE_DIR%
if exist %PACKAGE_DIR% (
    rmdir /s /q %PACKAGE_DIR%
)
mkdir %PACKAGE_DIR%

REM Copy essential files
echo Copying essential files...
xcopy /y README.md %PACKAGE_DIR%\
xcopy /y requirements.txt %PACKAGE_DIR%\
xcopy /y run.py %PACKAGE_DIR%\
xcopy /y run.bat %PACKAGE_DIR%\
xcopy /y install_all.bat %PACKAGE_DIR%\
xcopy /y ENHANCED_TABLE_EXTRACTION.md %PACKAGE_DIR%\
xcopy /y MARKITDOWN_README.md %PACKAGE_DIR%\
xcopy /y MARKITDOWN_USER_GUIDE.md %PACKAGE_DIR%\
xcopy /y test_markitdown.py %PACKAGE_DIR%\
xcopy /y test_enhanced_tables.py %PACKAGE_DIR%\
xcopy /y test_enhanced_tables.bat %PACKAGE_DIR%\

REM Copy source code
echo Copying source code...
xcopy /y /e /i src %PACKAGE_DIR%\src\

echo.
echo ========================================================
echo Package created successfully!
echo ========================================================
echo.
echo The package is ready in the %PACKAGE_DIR% directory.
echo.
echo To share the application:
echo  1. Zip the %PACKAGE_DIR% directory
echo  2. Share the zip file with your friend
echo  3. Tell them to:
echo     a. Extract the zip file
echo     b. Run install_all.bat to install all dependencies
echo     c. Run run.bat to start the application
echo.

pause 