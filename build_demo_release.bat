@echo off
setlocal

echo =========================================
echo   Arena Duel - Build Demo Windows
echo =========================================
echo.

set "PYTHON_EXE=.\.venv\Scripts\python.exe"
set "DIST_DIR=dist_release"
set "WORK_DIR=build_release"
set "DEMO_DIR=dist_demo\ArenaDuel_Demo_Windows"
set "PORTABLE_DIR=%DEMO_DIR%\Portable\ArenaDuel"
set "INSTALLER_DIR=%DEMO_DIR%\Installer"
set "ZIP_PATH=dist_demo\ArenaDuel_Demo_Windows.zip"

if not exist "%PYTHON_EXE%" (
    echo [ERREUR] Le venv n existe pas.
    echo Lance d abord : setup_env.bat
    call :maybe_pause
    exit /b 1
)

if exist "%WORK_DIR%" rmdir /s /q "%WORK_DIR%"
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
if exist "dist_demo" rmdir /s /q "dist_demo"

echo [INFO] Regeneration du pack d icones officiel...
"%PYTHON_EXE%" tools\gen_icon.py
if errorlevel 1 (
    echo.
    echo [ERREUR] La generation des icones a echoue.
    call :maybe_pause
    exit /b 1
)

echo [INFO] Build PyInstaller de la version demo...
"%PYTHON_EXE%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --distpath "%DIST_DIR%" ^
  --workpath "%WORK_DIR%" ^
  ArenaDuel.spec

if errorlevel 1 (
    echo.
    echo [ERREUR] Le build PyInstaller a echoue.
    call :maybe_pause
    exit /b 1
)

copy /y "app_runtime.demo.json" "%DIST_DIR%\ArenaDuel\app_runtime.json" >nul
copy /y "assets\images\arena_duel.ico" "%DIST_DIR%\ArenaDuel\arena_duel.ico" >nul
copy /y "README_DEMO.txt" "%DIST_DIR%\ArenaDuel\README_DEMO.txt" >nul

mkdir "%PORTABLE_DIR%" >nul 2>nul
xcopy "%DIST_DIR%\ArenaDuel\*" "%PORTABLE_DIR%\" /e /i /y >nul

if errorlevel 1 (
    echo.
    echo [ERREUR] Impossible de preparer le dossier portable de demo.
    call :maybe_pause
    exit /b 1
)

copy /y "README_DEMO.txt" "%DEMO_DIR%\README_DEMO.txt" >nul

set "ISCC_EXE="
where ISCC >nul 2>nul
if not errorlevel 1 set "ISCC_EXE=ISCC"
if not defined ISCC_EXE if exist "C:\Program Files\Inno Setup 7\ISCC.exe" set "ISCC_EXE=C:\Program Files\Inno Setup 7\ISCC.exe"
if not defined ISCC_EXE if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC_EXE=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE (
    echo.
    echo [INFO] Inno Setup n est pas detecte sur ce poste.
    echo [INFO] Le plan B installateur n a pas ete genere.
) else (
    echo [INFO] Generation du plan B installateur...
    "%ISCC_EXE%" installer\arena_duel.iss
    if errorlevel 1 (
        echo.
        echo [ERREUR] La generation de l installateur a echoue.
        call :maybe_pause
        exit /b 1
    )

    mkdir "%INSTALLER_DIR%" >nul 2>nul
    copy /y "installer\Setup_ArenaDuel.exe" "%INSTALLER_DIR%\Setup_ArenaDuel.exe" >nul
)

if exist "%ZIP_PATH%" del /q "%ZIP_PATH%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%DEMO_DIR%\*' -DestinationPath '%ZIP_PATH%' -Force" >nul
if errorlevel 1 (
    echo.
    echo [ERREUR] Impossible de generer l archive zip de livraison.
    call :maybe_pause
    exit /b 1
)

copy /y "app_runtime.json" "%DIST_DIR%\ArenaDuel\app_runtime.json" >nul
copy /y "assets\images\arena_duel.ico" "%DIST_DIR%\ArenaDuel\arena_duel.ico" >nul
if exist "%DIST_DIR%\ArenaDuel\README_DEMO.txt" del /q "%DIST_DIR%\ArenaDuel\README_DEMO.txt"

echo.
echo [OK] Livraison demo preparee.
echo Dossier final : %DEMO_DIR%
echo Archive zip : %ZIP_PATH%
echo Lancement principal : %PORTABLE_DIR%\ArenaDuel.exe
if exist "%INSTALLER_DIR%\Setup_ArenaDuel.exe" (
    echo Plan B installateur : %INSTALLER_DIR%\Setup_ArenaDuel.exe
)
echo.
call :maybe_pause
exit /b 0

:maybe_pause
if /I "%ARENA_DUEL_NO_PAUSE%"=="1" exit /b 0
pause
exit /b 0