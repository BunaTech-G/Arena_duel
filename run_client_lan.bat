@echo off
echo =========================================
echo   Arena Duel - Client LAN (CLI)
echo =========================================
echo.

if not exist .\.venv\Scripts\python.exe (
    echo [ERREUR] Le venv n existe pas.
    echo Lance d abord : setup_env.bat
    pause
    exit /b 1
)

set /p SERVER_IP=Entrez l IP du serveur : 
set /p PLAYER_NAME=Entrez le pseudo : 

.\.venv\Scripts\python.exe -m network.client --host %SERVER_IP% --port 5000 --name %PLAYER_NAME%
pause