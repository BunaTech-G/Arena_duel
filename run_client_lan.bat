@echo off
echo =========================================
echo   Arena Duel - Client LAN CLI de diagnostic
echo =========================================
echo.
echo [INFO] Pour la presentation V1, prefere run_lan_ui.bat.
echo [INFO] Ce script reste utile pour un test reseau bas niveau.
echo.

if not exist .\.venv\Scripts\python.exe (
    echo [ERREUR] Le venv n existe pas.
    echo Lance d abord : setup_env.bat
    pause
    exit /b 1
)

set /p SERVER_INVITATION=Entrez l invitation LAN (IP ou IP:port) : 
set /p PLAYER_NAME=Entrez le pseudo : 

.\.venv\Scripts\python.exe -m network.client --server "%SERVER_INVITATION%" --name "%PLAYER_NAME%"
pause