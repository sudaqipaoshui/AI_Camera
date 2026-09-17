@echo off
REM Run WebSocket Temperature Monitor Tool on Windows

echo ============================================================
echo WebSocket Temperature Monitor Tool
echo ============================================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Set UTF-8 encoding
chcp 65001 >nul

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not installed or not in PATH
    echo Please run install_windows.bat to install
    pause
    exit /b 1
)

REM Check dependencies
python -c "import websocket, cv2, numpy" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Dependencies not installed
    echo Please run install_windows.bat to install dependencies
    pause
    exit /b 1
)

echo [OK] Environment check passed
echo.
echo Connecting to camera and starting data collection...
echo Press Ctrl+C to stop
echo.
echo ============================================================
echo.

REM Run main program
python crawler_v2.py

echo.
echo ============================================================
echo Program stopped
echo ============================================================
echo.
echo Report location: allure-report\websocket\
echo.

pause
