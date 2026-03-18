@echo off
setlocal

:: ---------------------------------------------------------------
:: generate_machine_id.bat
:: Run this on the CLIENT machine after installation.
:: Generates a machine_id.txt file in the installation folder.
:: Copy machine_id.txt to the server admin to generate a license.
:: ---------------------------------------------------------------

set INSTALL_DIR=C:\ScreenRecorderClient
set PYTHON=%INSTALL_DIR%\venv\Scripts\python.exe
set SHARED_DIR=%INSTALL_DIR%\shared
set OUTPUT_FILE=%INSTALL_DIR%\machine_id.txt

echo ================================================
echo   Screen Recorder - Machine ID Generator
echo ================================================
echo.

:: Verify installation directory exists
if not exist "%INSTALL_DIR%" (
    echo ERROR: Installation directory not found: %INSTALL_DIR%
    echo Please run install_client_service.bat first.
    pause
    exit /b 1
)

:: Verify Python venv exists
if not exist "%PYTHON%" (
    echo ERROR: Python virtual environment not found at:
    echo   %PYTHON%
    echo Please run install_client_service.bat first.
    pause
    exit /b 1
)

:: Verify shared module exists
if not exist "%SHARED_DIR%\license_manager.py" (
    echo ERROR: Shared module not found at:
    echo   %SHARED_DIR%\license_manager.py
    echo Please run install_client_service.bat first.
    pause
    exit /b 1
)

echo Generating Machine ID...
echo.

:: Run inline Python to get machine ID using the installed shared module
"%PYTHON%" -c ^
    "import sys; sys.path.insert(0, r'%SHARED_DIR%'); " ^
    "from license_manager import MachineIdentifier; " ^
    "mid = MachineIdentifier.get_machine_id(); " ^
    "print(mid); " ^
    "open(r'%OUTPUT_FILE%', 'w').write(mid)"

if %errorLevel% neq 0 (
    echo.
    echo ERROR: Failed to generate machine ID.
    echo Make sure the client installation is complete and the shared module is present.
    pause
    exit /b 1
)

echo.
echo ================================================
echo   Machine ID saved to:
echo   %OUTPUT_FILE%
echo ================================================
echo.
echo Next steps:
echo   1. Copy  %OUTPUT_FILE%  to the server administrator.
echo   2. On the server, open the admin dashboard.
echo   3. Go to "Generate License" and paste the Machine ID.
echo   4. Download the generated license.key.
echo   5. Place license.key in  %INSTALL_DIR%\license.key
echo   6. Restart the service:  sc stop ScreenRecSvc  then  sc start ScreenRecSvc
echo.

:: Also display the machine ID on screen for quick manual copy
echo Machine ID (also saved in file):
echo.
type "%OUTPUT_FILE%"
echo.

pause
endlocal
