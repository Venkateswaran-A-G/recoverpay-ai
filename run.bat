@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Starting RecoverPay AI Engine...

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

echo.
echo  ============================================================
echo   RecoverPay AI
echo   Starting RecoverPay AI Engine...
echo  ============================================================
echo.
echo   API        http://127.0.0.1:8000
echo   Dashboard  http://localhost:8000
echo   Health     http://localhost:8000/health
echo.
echo   Keep this window open while the engine is running.
echo   Press Ctrl+C to stop the server.
echo.

start "" /b %PY% -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
timeout /t 2 /nobreak > nul
start http://localhost:8000

echo   Browser opened. Waiting for uvicorn (reload) in this window.
echo.
endlocal
goto :eof
