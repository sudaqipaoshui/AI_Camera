@echo off
chcp 65001 >nul
title ReplayLab 启动器
cd /d e:\AI_Camera\ReplayLab
echo 正在启动 ReplayLab 两个后台服务(最小化窗口, 日志在窗内可看)...
REM 视频源(8000): 摄像头 wget 视频用, 必须 python.exe + --bind 0.0.0.0
start "RL-视频源8000" /min "E:\TestTools\venv\Scripts\python.exe" -m http.server 8000 --bind 0.0.0.0 --directory E:\TestTools
timeout /t 2 >nul
REM Web平台(5000)
start "RL-平台5000" /min "E:\TestTools\venv\Scripts\python.exe" "e:\AI_Camera\ReplayLab\web\app.py"
echo.
echo ============================================
echo   本机平台   http://localhost:5000
echo   局域网访问 http://192.168.2.124:5000
echo   视频源     http://192.168.2.124:8000
echo ============================================
echo 两个服务在任务栏以最小化窗口运行, 关闭对应窗口即停止该服务。
if /i "%~1"=="autorun" goto :eof
pause
