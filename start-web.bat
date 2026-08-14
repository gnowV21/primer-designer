@echo off
REM ============================================================
REM  HG Lab - Primer Designer : one-click launcher
REM  Opens Backend + Frontend, each in its own window,
REM  then opens the browser. Close a window to stop that piece.
REM ============================================================

set "ROOT=%~dp0"

echo Starting HG Lab Primer Designer...
echo Root: %ROOT%
echo.

REM --- 1. Backend (Flask on :5000) -----------------------------
REM  Reloader is OFF on purpose to avoid the watcher restarting on
REM  site-packages churn.
start "Backend :5000" cmd /k "cd /d "%ROOT%backend" && python -c "import app; app.app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)""

REM --- 2. Frontend (Vite on :5173, or :5174 if busy) -----------
start "Frontend :5173" cmd /k "cd /d "%ROOT%frontend" && npm run dev"

REM --- 3. Give the servers a head start, then open the browser -
echo Waiting for the dev server to come up...
timeout /t 6 /nobreak >nul
start "" "http://localhost:5173"

echo.
echo Both windows launched. If the browser shows nothing,
echo check the "Frontend" window for the real port (5173 or 5174).
echo Close each window to stop that server.
