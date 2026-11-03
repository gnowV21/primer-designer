@echo off
REM ============================================================
REM  Primer Designer - one-click launcher
REM  Starts Flask backend (:5000) + Vite frontend (:5173),
REM  then opens the app in your default browser.
REM ============================================================
setlocal
title Primer Designer launcher
cd /d "%~dp0"

echo ============================================================
echo  Primer Designer - starting backend + frontend
echo ============================================================

REM --- Free ports 5000 / 5173 if a previous run is still holding them ---
echo [1/4] Clearing old processes on ports 5000 and 5173...
for %%P in (5000 5173) do (
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%%P " ^| findstr LISTENING') do (
        echo       Port %%P held by PID %%A - stopping it (and child processes)
        taskkill /PID %%A /T /F >nul 2>&1
    )
)

REM --- Backend: Flask on :5000 (own window) ---
echo [2/4] Launching backend (Flask :5000)...
start "Primer Designer - Backend" cmd /k "cd /d "%~dp0backend" && python app.py"

REM --- Frontend: Vite on :5173 (own window) ---
echo [3/4] Launching frontend (Vite :5173)...
start "Primer Designer - Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

REM --- Wait for the frontend to come up, then open the browser ---
echo [4/4] Waiting for the frontend to be ready...
set "READY="
for /l %%i in (1,1,30) do (
    if not defined READY (
        timeout /t 1 /nobreak >nul
        netstat -ano | findstr ":5173 " | findstr LISTENING >nul 2>&1 && set "READY=1"
    )
)

if defined READY (
    echo       Frontend is up - opening http://localhost:5173
    start "" "http://localhost:5173"
) else (
    echo       Frontend did not report ready in 30s - check the Frontend window.
    echo       You can still open http://localhost:5173 manually once it finishes.
)

echo.
echo ============================================================
echo  Done. Two windows opened:
echo    - "Primer Designer - Backend"   (Flask  http://localhost:5000)
echo    - "Primer Designer - Frontend"  (Vite   http://localhost:5173)
echo  Close those windows (or press Ctrl+C in them) to stop.
echo ============================================================
echo.
echo This launcher window can be closed - the servers keep running.
pause
endlocal
