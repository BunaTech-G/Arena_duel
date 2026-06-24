@echo off
setlocal

echo =========================================
echo   Arena Duel - Build EXE rapide
echo =========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Venv absent. Initialisation automatique...
    set "ARENA_DUEL_NO_PAUSE=1"
    call setup_env.bat
    if errorlevel 1 (
        echo [ERREUR] Echec de l initialisation Python.
        call :maybe_pause
        exit /b 1
    )
)

echo [INFO] Verification de l environnement Python et des dependances...
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Venv absent. Initialisation automatique...
    set "ARENA_DUEL_NO_PAUSE=1"
    call setup_env.bat
    if errorlevel 1 (
        echo [ERREUR] Echec de l initialisation Python.
        call :maybe_pause
        exit /b 1
    )
) else (
    .\.venv\Scripts\python.exe -c "import sys" >nul 2>nul
    if errorlevel 1 (
        echo [INFO] Venv existant invalide. Recreation automatique...
        rmdir /s /q ".venv" >nul 2>nul
        set "ARENA_DUEL_NO_PAUSE=1"
        call setup_env.bat
        if errorlevel 1 (
            echo [ERREUR] Echec de la recreation du venv.
            call :maybe_pause
            exit /b 1
        )
    )
)

echo [INFO] Installation des dependances requises...
.\.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERREUR] Impossible de mettre pip a jour
    call :maybe_pause
    exit /b 1
)

.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if errorlevel 1 (
    echo [ERREUR] Impossible d installer les dependances.
    call :maybe_pause
    exit /b 1
)

echo [INFO] Lancement du build canonique...
set "ARENA_DUEL_NO_PAUSE=1"
call build_presentation.bat
if errorlevel 1 (
    echo [ERREUR] Le build de l EXE a echoue.
    call :maybe_pause
    exit /b 1
)

echo [INFO] Packaging release (portable + installer)...
call package_release.bat
if errorlevel 1 (
    echo [ERREUR] Le packaging a echoue.
    call :maybe_pause
    exit /b 1
)

echo.
echo [OK] EXE genere dans dist_release\ArenaDuel\ArenaDuel.exe
echo.
call :maybe_pause
exit /b 0

:maybe_pause
if /I "%ARENA_DUEL_NO_PAUSE%"=="1" exit /b 0
pause
exit /b 0
