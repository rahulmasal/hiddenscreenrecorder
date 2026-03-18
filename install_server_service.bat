@echo off
echo ================================================
echo   Screen Recorder Server - Windows Service Installer
echo ================================================
echo.

:: Check for admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo This script requires administrator privileges.
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

:: Set paths
set INSTALL_DIR=C:\ScreenRecorderServer
set SCRIPT_DIR=%~dp0
set SERVER_DIR=%SCRIPT_DIR%server
set SHARED_DIR=%SCRIPT_DIR%shared

echo Step 1: Creating installation directory...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"
echo Done.
pause

echo Step 1b: Copying nssm.exe to installation directory...
if exist "%NSSM%" (
    copy /Y "%NSSM%" "%INSTALL_DIR%\nssm.exe"
    echo nssm.exe copied to %INSTALL_DIR%
) else (
    echo ERROR: nssm.exe not found at %SCRIPT_DIR%nssm.exe
    echo Please place nssm.exe in the same folder as this installer and re-run.
    pause
    exit /b 1
)
set NSSM=%INSTALL_DIR%\nssm.exe
echo NSSM will run from: %NSSM%
pause

echo Step 2: Copying server files...
xcopy /E /I /Y "%SERVER_DIR%\*" "%INSTALL_DIR%\"
echo Step 2b: Copying shared files...
xcopy /E /I /Y "%SHARED_DIR%\*" "%INSTALL_DIR%\shared\"
echo Done.
pause

echo Step 3: Creating virtual environment...
if not exist "%INSTALL_DIR%\venv" (
    python -m venv "%INSTALL_DIR%\venv"
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)
pause

echo Step 4: Installing dependencies...
call "%INSTALL_DIR%\venv\Scripts\activate.bat"
pip install -r "%INSTALL_DIR%\requirements.txt"
echo Done.
pause

echo Step 5: Creating .env file...
if not exist "%INSTALL_DIR%\.env" (
    copy "%INSTALL_DIR%\.env.example" "%INSTALL_DIR%\.env"
    echo .env file created.
    echo IMPORTANT: Edit %INSTALL_DIR%\.env to set your SECRET_KEY and ADMIN_PASSWORD
) else (
    echo .env file already exists.
)
pause

echo Step 6: Downloading NSSM...
if not exist "%NSSM%" (
    echo Downloading NSSM from https://nssm.cc/release/nssm-2.24.zip...
    curl -L -o "%SCRIPT_DIR%nssm.zip" https://nssm.cc/release/nssm-2.24.zip
    if not exist "%SCRIPT_DIR%nssm.zip" (
        echo ERROR: Failed to download NSSM.
        echo.
        echo Please download NSSM manually:
        echo 1. Go to https://nssm.cc/download
        echo 2. Download nssm-2.24.zip
        echo 3. Extract nssm.exe from the win64 folder
        echo 4. Place nssm.exe in: %SCRIPT_DIR%
        echo 5. Run this script again
        pause
        exit /b 1
    )
    echo Extracting NSSM...
    cd /d "%SCRIPT_DIR%"
    tar -xf nssm.zip
    if not exist "%SCRIPT_DIR%nssm-2.24\win64\nssm.exe" (
        echo ERROR: Failed to extract NSSM properly.
        echo.
        echo Please download NSSM manually:
        echo 1. Go to https://nssm.cc/download
        echo 2. Download nssm-2.24.zip
        echo 3. Extract nssm.exe from the win64 folder
        echo 4. Place nssm.exe in: %SCRIPT_DIR%
        echo 5. Run this script again
        pause
        exit /b 1
    )
    copy "%SCRIPT_DIR%nssm-2.24\win64\nssm.exe" "%NSSM%"
    rmdir /s /q "%SCRIPT_DIR%nssm-2.24"
    del "%SCRIPT_DIR%nssm.zip"
    echo NSSM downloaded successfully.
) else (
    echo NSSM already exists.
)
pause

echo Step 7: Installing Windows service...
"%NSSM%" install ScreenRecorderServer "%INSTALL_DIR%\venv\Scripts\python.exe" "%INSTALL_DIR%\app.py"
"%NSSM%" set ScreenRecorderServer AppDirectory "%INSTALL_DIR%"
"%NSSM%" set ScreenRecorderServer DisplayName "Screen Recorder Server"
"%NSSM%" set ScreenRecorderServer Description "Screen Recorder Server Application"
"%NSSM%" set ScreenRecorderServer Start SERVICE_AUTO_START
"%NSSM%" set ScreenRecorderServer AppStdout "%INSTALL_DIR%\logs\service.log"
"%NSSM%" set ScreenRecorderServer AppStderr "%INSTALL_DIR%\logs\service_error.log"
"%NSSM%" set ScreenRecorderServer AppRotateFiles 1
"%NSSM%" set ScreenRecorderServer AppRotateOnline 1
"%NSSM%" set ScreenRecorderServer AppRotateSeconds 86400
"%NSSM%" set ScreenRecorderServer AppRotateBytes 1048576
echo Service installed.
pause

echo Step 8: Starting service...
"%NSSM%" start ScreenRecorderServer
if %errorLevel% neq 0 (
    echo ERROR: Failed to start service. Error code: %errorLevel%
    echo Check the service logs at: %INSTALL_DIR%\logs\
    pause
    exit /b 1
)
echo Service started.
pause

echo.
echo ================================================
echo   Installation Complete!
echo ================================================
echo.
echo Service Name: ScreenRecorderServer
echo Installation Directory: %INSTALL_DIR%
echo Logs Directory: %INSTALL_DIR%\logs
echo.
echo The server will start automatically on system boot.
echo.
echo Admin Dashboard: http://localhost:5000/admin
echo.
echo To manage the service:
echo   - Start:   sc start ScreenRecorderServer
echo   - Stop:    sc stop ScreenRecorderServer
echo   - Status:  sc query ScreenRecorderServer
echo.
echo To uninstall, run: uninstall_server_service.bat
echo ================================================
pause
