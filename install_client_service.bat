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
call "%INSTALL_DIR%\venv\Scripts\activate.bat"
pip install -r "%INSTALL_DIR%\requirements.txt"
echo Done.
pause

echo Step 5: Installing Windows service (using client's built-in service installer)...
call "%INSTALL_DIR%\venv\Scripts\python.exe" "%INSTALL_DIR%\screen_recorder.py" --install
if %errorLevel% neq 0 (
    echo ERROR: Failed to install client service.
    pause
    exit /b 1
)
echo Client service installed.
pause

echo Step 6: Starting service...
sc start ScreenRecSvc
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
echo Client Directory: %INSTALL_DIR%\client
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