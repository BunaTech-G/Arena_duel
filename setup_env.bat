@echo off
echo =========================================
echo   Arena Duel - Setup environnement dev
echo =========================================
echo.

REM 1) Création du venv avec Python 3.14
py -3.14 -m venv .venv
if errorlevel 1 (
    echo [ERREUR] Impossible de creer le venv avec Python 3.14
    pause
    exit /b 1
)

REM 2) Mise a jour de pip dans le venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERREUR] Impossible de mettre pip a jour
    pause
    exit /b 1
)

REM 3) Installation des dependances
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if errorlevel 1 (
    echo [ERREUR] Impossible d installer les dependances
    pause
    exit /b 1
)

echo.
echo [OK] Environnement configure avec succes.
echo.
echo Utilisation :
echo   - run_local.bat
echo   - run_server.bat
echo   - run_client_lan.bat
echo.
pause