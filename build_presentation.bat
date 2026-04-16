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
    echo [ERREUR] Le venv n existe pas.
    echo Lance d abord : setup_env.bat
    pause
    exit /b 1
)

if exist "%WORK_DIR%" rmdir /s /q "%WORK_DIR%"
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"

echo [INFO] Regeneration du pack d icones officiel...
"%PYTHON_EXE%" tools\gen_icon.py
if errorlevel 1 (
  echo.
  echo [ERREUR] La generation des icones a echoue.
  pause
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
  ArenaDuel.spec

if errorlevel 1 (
    echo.
    echo [ERREUR] Le build PyInstaller a echoue.
    echo Ferme Arena Duel, ferme tout Explorateur ouvert sur dist\ArenaDuel,
    echo puis relance ce script.
    pause
    exit /b 1
)

  copy /y "app_runtime.json" "%DIST_DIR%\ArenaDuel\app_runtime.json" >nul

echo.
echo [OK] Build terminé.
echo Dossier final : %DIST_DIR%\ArenaDuel
echo EXE final : %DIST_DIR%\ArenaDuel\ArenaDuel.exe
echo.
echo Pour ecraser dist\ArenaDuel, ferme d abord tout programme ou fenetre
echo qui utilise ce dossier, puis relance une build standard si tu en as besoin.
echo.
pause
