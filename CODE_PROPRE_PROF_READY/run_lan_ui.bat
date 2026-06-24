@echo off
echo =========================================
echo   Arena Duel - Lobby LAN Graphique
echo =========================================
echo.

if not exist .\.venv\Scripts\python.exe (
    echo [ERREUR] Le venv n existe pas.
    echo Lance d abord : setup_env.bat
    pause
    exit /b 1
)

.\.venv\Scripts\python.exe main_lan.py
pause