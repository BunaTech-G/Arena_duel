@echo off
setlocal
echo =========================================
echo   Arena Duel - Lancement local
echo =========================================
echo.

if not exist .\.venv\Scripts\python.exe (
    echo [INFO] Venv absent. Initialisation automatique...
    set "ARENA_DUEL_NO_PAUSE=1"
    call setup_env.bat
    if errorlevel 1 (
        echo [ERREUR] Echec de l initialisation de l environnement.
        call :maybe_pause
        exit /b 1
    )
)

echo [INFO] Verification integrite du venv...
.\.venv\Scripts\python.exe -c "import sys; print(sys.version_info[0])" >nul 2>nul
if errorlevel 1 (
    echo [INFO] Venv detecte mais invalide sur ce PC. Recreation automatique...
    if exist ".venv" rmdir /s /q ".venv"
    set "ARENA_DUEL_NO_PAUSE=1"
    call setup_env.bat
    if errorlevel 1 (
        echo [ERREUR] Echec de recreation de l environnement.
        call :maybe_pause
        exit /b 1
    )
)

echo [INFO] Verification des dependances runtime...
.\.venv\Scripts\python.exe -c "import customtkinter, pygame, PIL" >nul 2>nul
if errorlevel 1 (
    echo [INFO] Dependances manquantes detectees. Installation automatique...
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERREUR] Impossible d installer requirements.txt
        call :maybe_pause
        exit /b 1
    )
)

.\.venv\Scripts\python.exe main.py
call :maybe_pause
exit /b 0

:maybe_pause
if /I "%ARENA_DUEL_NO_PAUSE%"=="1" exit /b 0
pause
exit /b 0