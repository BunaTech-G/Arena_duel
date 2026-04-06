@echo off
echo =========================================
echo   Arena Duel - Setup LAN leger
echo =========================================
echo.

py -3.14 -m venv .venv
if errorlevel 1 (
    echo [ERREUR] Impossible de creer le venv avec Python 3.14
    pause
    exit /b 1
)

.\.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERREUR] Impossible de mettre pip a jour
    pause
    exit /b 1
)

.\.venv\Scripts\python.exe -m pip install -r requirements-lan.txt
if errorlevel 1 (
    echo [ERREUR] Impossible d installer les dependances LAN
    pause
    exit /b 1
)

echo.
echo [OK] Environnement LAN configure avec succes.
echo.
echo Lance ensuite : run_lan_ui.bat
echo.
pause
