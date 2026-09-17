@echo off
REM Windows Installation Script
REM Auto-install all dependencies

echo ============================================================
echo WebSocket Temperature Monitor - Windows Installer
echo ============================================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not installed
    echo.
    echo Please install Python first:
    echo 1. Visit https://www.python.org/downloads/
    echo 2. Download and install Python 3.7+
    echo 3. Check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

echo [OK] Python installed
python --version
echo.

REM Upgrade pip
echo ============================================================
echo Step 1/3: Upgrade pip
echo ============================================================
python -m pip install --upgrade pip
echo.

REM Install dependencies
echo ============================================================
echo Step 2/3: Install dependencies
echo ============================================================
echo.
echo Installing: websocket-client opencv-python numpy protobuf pyyaml
echo This may take a few minutes...
echo.

REM Try installing pre-built wheel packages first (avoid compilation issues)
echo [Step 1] Trying to install pre-built packages...
python -m pip install --only-binary :all: websocket-client opencv-python numpy protobuf pyyaml

if %errorlevel% neq 0 (
    echo.
    echo [Step 2] Pre-built packages failed, trying Chinese mirror...
    echo.
    python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --only-binary :all: websocket-client opencv-python numpy protobuf pyyaml

    if %errorlevel% neq 0 (
        echo.
        echo [Step 3] Trying compatible numpy version (avoid GCC compilation issues)...
        echo.
        REM Install older but stable numpy version (1.24.x), compatible with GCC 7.3
        python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple websocket-client opencv-python "numpy<2.0" protobuf pyyaml

        if %errorlevel% neq 0 (
            echo.
            echo [Step 4] Last attempt: install pre-built numpy only...
            echo.
            python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --only-binary numpy numpy
            python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple websocket-client opencv-python protobuf pyyaml
        )
    )
)

echo.

REM Verify installation
echo ============================================================
echo Step 3/3: Verify installation
echo ============================================================
echo.

python -c "import websocket; print('[OK] websocket-client')" 2>nul || echo [FAIL] websocket-client
python -c "import cv2; print('[OK] opencv-python')" 2>nul || echo [FAIL] opencv-python
python -c "import numpy; print('[OK] numpy')" 2>nul || echo [FAIL] numpy
python -c "from google.protobuf import __version__; print('[OK] protobuf')" 2>nul || echo [FAIL] protobuf
python -c "import yaml; print('[OK] pyyaml')" 2>nul || echo [FAIL] pyyaml

echo.
echo ============================================================
echo Installation completed!
echo ============================================================
echo.
echo Next steps:
echo 1. Run debug check: run_windows_debug.bat
echo 2. Run main program: python crawler_v2.py
echo.

pause
