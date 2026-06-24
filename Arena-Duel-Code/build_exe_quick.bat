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

echo [INFO] Verification PyInstaller...
.\.venv\Scripts\python.exe -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo [INFO] PyInstaller manquant. Installation automatique...
    .\.venv\Scripts\python.exe -m pip install pyinstaller
    if errorlevel 1 (
        echo [ERREUR] Impossible d installer PyInstaller.
        call :maybe_pause
        exit /b 1
    )
)

echo [INFO] Lancement du build canonique...
set "ARENA_DUEL_NO_PAUSE=1"
call build_presentation.bat
if errorlevel 1 (
    echo [ERREUR] Le build de l EXE a echoue.
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
