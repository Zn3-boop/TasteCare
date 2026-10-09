@echo off
chcp 65001 >nul
echo ========================================
echo AI Desktop Agent - 一键启动所有服务
echo ========================================
echo.

:: 设置 Python 路径（优先使用 venv）
if exist "d:\ecv - 副本\venv\Scripts\python.exe" (
    set "PYTHON=d:\ecv - 副本\venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)
echo [0/4] Python: %PYTHON%

:: 1. 启动后端服务
echo [1/4] 启动后端服务 (端口 8000)...
start "Server" cmd /k "cd /d d:\ecv - 副本\apps\server && %PYTHON% -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

:: 2. 启动Edge TTS API
echo [2/4] 启动TTS服务 (端口 8080)...
start "TTS" cmd /k "cd /d d:\ecv - 副本\edge-tts-api && %PYTHON% -m uvicorn main:app --host 127.0.0.1 --port 8080"

:: 3. 启动Whisper STT
echo [3/4] 启动Whisper STT (端口 9001)...
start "Whisper" cmd /k "cd /d d:\ecv - 副本\local-whisper-stt && %PYTHON% server.py"

:: 4. 启动 Web Demo 前端开发服务器
echo [4/4] 启动 Web Demo 前端 (端口 3000)...
start "Frontend" cmd /k "cd /d d:\ecv - 副本\apps\web && pnpm dev"

echo.
echo ========================================
echo 所有服务已启动！
echo - 后端:   http://127.0.0.1:8000
echo - TTS:    http://127.0.0.1:8080
echo - Whisper: http://127.0.0.1:9001
echo - Web Demo: http://127.0.0.1:3000
echo ========================================
echo.
echo 按任意键关闭此窗口...
pause >nul