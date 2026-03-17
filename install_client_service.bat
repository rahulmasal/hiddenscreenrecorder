@echo off
echo ================================================
echo   Screen Recorder Client - Windows Service Installer
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
set INSTALL_DIR=C:\ScreenRecorderClient
set SCRIPT_DIR=%~dp0
set CLIENT_DIR=%SCRIPT_DIR%client
set SHARED_DIR=%SCRIPT_DIR%shared

echo Step 1: Creating installation directory...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"
if not exist "%INSTALL_DIR%\ScreenRecSvc" mkdir "%INSTALL_DIR%\ScreenRecSvc"
if not exist "%INSTALL_DIR%\ScreenRecSvc\recordings" mkdir "%INSTALL_DIR%\ScreenRecSvc\recordings"
if not exist "%INSTALL_DIR%\ScreenRecSvc\offline_queue" mkdir "%INSTALL_DIR%\ScreenRecSvc\offline_queue"
echo Done.
pause

echo Step 2: Copying client files...
xcopy /E /I /Y "%CLIENT_DIR%\*" "%INSTALL_DIR%\"
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
"%INSTALL_DIR%\venv\Scripts\pip.exe" install -r "%INSTALL_DIR%\requirements.txt"
echo Done.
pause

echo Step 5: Configuring Server IP...
set /p SERVER_IP="Enter Server IP address (e.g., 192.168.1.100): "
if "%SERVER_IP%"=="" (
    set SERVER_IP=localhost
)
echo Creating config file with server URL: http://%SERVER_IP%:5000
set CONFIG_DIR=%INSTALL_DIR%\ScreenRecSvc
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"
(
    echo {"server_url": "http://%SERVER_IP%:5000"}
) > "%CONFIG_DIR%\config.json"
type "%CONFIG_DIR%\config.json"
echo Config file written to: %CONFIG_DIR%\config.json
echo Done.
pause

echo Step 6: Downloading NSSM...
if not exist "%SCRIPT_DIR%nssm.exe" (
    echo NSSM not found. Attempting to download...
    curl -L --max-time 30 -o "%SCRIPT_DIR%nssm.zip" https://nssm.cc/release/nssm-2.24.zip
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
    tar -xf "%SCRIPT_DIR%nssm.zip" -C "%SCRIPT_DIR%"
    if not exist "%SCRIPT_DIR%nssm-2.24\win64\nssm.exe" (
        echo ERROR: Failed to extract NSSM properly.
        echo.
        echo Please download NSSM manually:
        echo 1. Go to https://nssm.cc/download
        echo 2. Download nssm-2.24.zip
        echo 3. Extract nssm.exe from the win64 folder
        echo 4. Place nssm.exe in: %SCRIPT_DIR%
        echo 5. Run this script again
        if exist "%SCRIPT_DIR%nssm.zip" del "%SCRIPT_DIR%nssm.zip"
        pause
        exit /b 1
    )
    copy "%SCRIPT_DIR%nssm-2.24\win64\nssm.exe" "%SCRIPT_DIR%nssm.exe"
    rmdir /s /q "%SCRIPT_DIR%nssm-2.24"
    del "%SCRIPT_DIR%nssm.zip"
    echo NSSM downloaded and extracted successfully.
) else (
    echo NSSM already exists, skipping download.
)
pause

echo Step 7: Copying license and public key if present...
if exist "%SCRIPT_DIR%license.key" (
    copy /Y "%SCRIPT_DIR%license.key" "%INSTALL_DIR%\license.key"
    echo license.key copied to %INSTALL_DIR%.
) else (
    echo WARNING: license.key not found in %SCRIPT_DIR%
    echo Place license.key at %INSTALL_DIR%\license.key before starting the service.
)
if exist "%SCRIPT_DIR%public_key.pem" (
    copy /Y "%SCRIPT_DIR%public_key.pem" "%INSTALL_DIR%\public_key.pem"
    echo public_key.pem copied to %INSTALL_DIR%.
) else (
    echo WARNING: public_key.pem not found in %SCRIPT_DIR%
    echo Get it from the server at C:\ScreenRecorderServer\keys\public_key.pem
)
pause

echo Step 8: Removing any existing service before installing...
"%SCRIPT_DIR%nssm.exe" stop ScreenRecSvc >nul 2>&1
"%SCRIPT_DIR%nssm.exe" remove ScreenRecSvc confirm >nul 2>&1
timeout /t 3 /nobreak >nul

echo Step 9: Installing Windows service...

:: -----------------------------------------------------------------------
:: Configure the service to run under the currently logged-in user account
:: instead of SYSTEM.  Windows services that run as SYSTEM are isolated in
:: Session 0 and cannot access the interactive desktop / display.
:: Running as the real user account places the service in the user session
:: so that mss / screen-capture APIs see the actual screen.
:: -----------------------------------------------------------------------
echo.
echo IMPORTANT: The service must run as YOUR Windows user account (not SYSTEM)
echo so that it can capture the screen.  Please enter your Windows credentials.
echo.
set /p SVC_USER="Enter Windows username (e.g. DOMAIN\Username or .\Username): "
if "%SVC_USER%"=="" (
    echo No username entered. Service will run as LocalSystem (screen capture may not work).
    set SVC_USER=LocalSystem
    set SVC_PASS=
) else (
    set /p SVC_PASS="Enter Windows password for %SVC_USER%: "
)
echo.

"%SCRIPT_DIR%nssm.exe" install ScreenRecSvc "%INSTALL_DIR%\venv\Scripts\python.exe" "%INSTALL_DIR%\screen_recorder.py"
"%SCRIPT_DIR%nssm.exe" set ScreenRecSvc AppDirectory "%INSTALL_DIR%"
"%SCRIPT_DIR%nssm.exe" set ScreenRecSvc DisplayName "Screen Recording Service"
"%SCRIPT_DIR%nssm.exe" set ScreenRecSvc Description "Automatic screen recording service"
"%SCRIPT_DIR%nssm.exe" set ScreenRecSvc Start SERVICE_AUTO_START
"%SCRIPT_DIR%nssm.exe" set ScreenRecSvc AppStdout "%INSTALL_DIR%\logs\service.log"
"%SCRIPT_DIR%nssm.exe" set ScreenRecSvc AppStderr "%INSTALL_DIR%\logs\service_error.log"
"%SCRIPT_DIR%nssm.exe" set ScreenRecSvc AppRotateFiles 1
"%SCRIPT_DIR%nssm.exe" set ScreenRecSvc AppRotateOnline 1
"%SCRIPT_DIR%nssm.exe" set ScreenRecSvc AppRotateSeconds 86400
"%SCRIPT_DIR%nssm.exe" set ScreenRecSvc AppRotateBytes 1048576
:: Do not restart when process exits cleanly (no license = exit 0)
"%SCRIPT_DIR%nssm.exe" set ScreenRecSvc AppExit Default Restart
"%SCRIPT_DIR%nssm.exe" set ScreenRecSvc AppExit 0 Exit

:: Set the service logon account so it runs in the user's desktop session
if not "%SVC_USER%"=="LocalSystem" (
    echo Configuring service to log on as: %SVC_USER%
    "%SCRIPT_DIR%nssm.exe" set ScreenRecSvc ObjectName "%SVC_USER%" "%SVC_PASS%"
    if %errorLevel% neq 0 (
        echo WARNING: Failed to set service logon account. Screen capture may not work.
        echo You can change it manually via Services.msc ^> ScreenRecSvc ^> Log On tab.
    ) else (
        echo Service logon account configured successfully.
    )
) else (
    echo.
    echo WARNING: Service is configured to run as LocalSystem (Session 0).
    echo Screen capture will be attempted via automatic user-session detection,
    echo but for reliable capture it is strongly recommended to run the service
    echo as the target user account ^(re-run this installer and enter credentials^).
    echo.
)
echo Service installed.
pause

echo Step 10: Starting service...
"%SCRIPT_DIR%nssm.exe" start ScreenRecSvc
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
echo Service Name: ScreenRecSvc
echo Installation Directory: %INSTALL_DIR%
echo Logs Directory: %INSTALL_DIR%\logs
echo.
echo The client will start automatically on system boot.
echo.
echo To manage the service:
echo   - Start:   sc start ScreenRecSvc
echo   - Stop:    sc stop ScreenRecSvc
echo   - Status:  sc query ScreenRecSvc
echo.
echo To uninstall, run: uninstall_client_service.bat
echo ================================================
echo.
pause
