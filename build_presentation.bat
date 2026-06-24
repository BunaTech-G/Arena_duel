@echo off
setlocal

echo =========================================
echo   Arena Duel - Build Presentation EXE
echo =========================================
echo.
echo [INFO] Script canonique de build V1.
echo [INFO] Le spec versionne ArenaDuel.spec fait foi pour l EXE.
echo.

set "PYTHON_EXE=.\.venv\Scripts\python.exe"
set "DIST_DIR=dist_release"
set "WORK_DIR=build_release"

if not exist "%PYTHON_EXE%" (
    echo [INFO] Venv absent. Initialisation automatique...
    set "ARENA_DUEL_NO_PAUSE=1"
    call setup_env.bat
    if errorlevel 1 (
        echo [ERREUR] Echec de l initialisation Python.
        call :maybe_pause
        exit /b 1
    )
) else (
    "%PYTHON_EXE%" -c "import sys" >nul 2>nul
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

echo [INFO] Installation des dependances requises pour le build...
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERREUR] Impossible de mettre pip a jour
    call :maybe_pause
    exit /b 1
)

"%PYTHON_EXE%" -m pip install -r requirements-dev.txt
if errorlevel 1 (
    echo [ERREUR] Impossible d installer les dependances.
    call :maybe_pause
    exit /b 1
)

if exist "%WORK_DIR%" rmdir /s /q "%WORK_DIR%"
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"

echo [INFO] Regeneration du pack d icones officiel...
"%PYTHON_EXE%" tools\gen_icon.py
if errorlevel 1 (
  echo.
  echo [ERREUR] La generation des icones a echoue.
  call :maybe_pause
  exit /b 1
)

echo [INFO] Verification des assets avant PyInstaller...
call verify_assets.bat
if errorlevel 1 (
    echo [ERREUR] Verification des assets a echoue. Corrige les erreurs precedentes.
    call :maybe_pause
    exit /b 1
)

echo [INFO] Si dist\ArenaDuel est verrouille par l Explorateur, OneDrive ou un ancien EXE,
echo [INFO] cette build utilise un dossier de sortie propre pour eviter le blocage.
echo.

"%PYTHON_EXE%" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --distpath "%DIST_DIR%" ^
    --workpath "%WORK_DIR%" ^
    "%~dp0ArenaDuel.spec"

if errorlevel 1 (
    echo.
    echo [ERREUR] Le build PyInstaller a echoue.
    echo Ferme Arena Duel, ferme tout Explorateur ouvert sur dist\ArenaDuel,
    echo puis relance ce script.
  call :maybe_pause
    exit /b 1
)

  copy /y "app_runtime.json" "%DIST_DIR%\ArenaDuel\app_runtime.json" >nul
  copy /y "assets\images\arena_duel.ico" "%DIST_DIR%\ArenaDuel\arena_duel.ico" >nul

echo.
echo [OK] Build terminé.
echo Dossier final : %DIST_DIR%\ArenaDuel
echo EXE final : %DIST_DIR%\ArenaDuel\ArenaDuel.exe
echo.
echo Pour ecraser dist\ArenaDuel, ferme d abord tout programme ou fenetre
echo qui utilise ce dossier, puis relance une build standard si tu en as besoin.
echo.
call :maybe_pause
exit /b 0

:maybe_pause
if /I "%ARENA_DUEL_NO_PAUSE%"=="1" exit /b 0
pause
exit /b 0
