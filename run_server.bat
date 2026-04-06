@echo off
echo =========================================
echo   Arena Duel - Serveur LAN
echo =========================================
echo.

if not exist .\.venv\Scripts\python.exe (
    echo [ERREUR] Le venv n existe pas.
    echo Lance d abord : setup_env.bat
    pause
    exit /b 1
)

.\.venv\Scripts\python.exe -m network.server --host 0.0.0.0 --port 5000
pause
``