@echo off
setlocal
echo =========================================
echo   Arena Duel - Setup environnement dev
echo =========================================
echo.

set "PYTHON_CMD="

REM 1) Selection d une version Python disponible
py -3.14 -c "import sys" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3.14"

if not defined PYTHON_CMD (
    py -3.13 -c "import sys" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3.13"
)

if not defined PYTHON_CMD (
    py -3.12 -c "import sys" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3.12"
)

if not defined PYTHON_CMD (
    py -3.11 -c "import sys" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3.11"
)

if not defined PYTHON_CMD (
    python -c "import sys" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo [ERREUR] Aucune installation Python detectee.
    echo Installe Python 3.11+ puis relance ce script.
    call :maybe_pause
    exit /b 1
)

echo [INFO] Python detecte: %PYTHON_CMD%

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Creation du venv .venv ...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERREUR] Impossible de creer le venv .venv
        call :maybe_pause
        exit /b 1
    )
) else (
    echo [INFO] Venv deja present: .venv
    .\.venv\Scripts\python.exe -c "import sys; print(sys.version_info[0])" >nul 2>nul
    if errorlevel 1 (
        echo [INFO] Venv existant invalide sur ce PC. Recreation du venv...
        rmdir /s /q ".venv"
        %PYTHON_CMD% -m venv .venv
        if errorlevel 1 (
            echo [ERREUR] Impossible de recreer le venv .venv
            call :maybe_pause
            exit /b 1
        )
    )
)

REM 2) Mise a jour de pip dans le venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERREUR] Impossible de mettre pip a jour
    call :maybe_pause
    exit /b 1
)

REM 3) Installation des dependances
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if errorlevel 1 (
    echo [ERREUR] Impossible d installer les dependances
    call :maybe_pause
    exit /b 1
)

echo.
echo [OK] Environnement configure avec succes.
echo.
echo Utilisation :
echo   - run_local.bat
echo   - run_lan_ui.bat
echo   - run_server.bat
echo   - run_client_lan.bat
echo   - build_presentation.bat
echo.
call :maybe_pause
exit /b 0

:maybe_pause
if /I "%ARENA_DUEL_NO_PAUSE%"=="1" exit /b 0
pause
exit /b 0