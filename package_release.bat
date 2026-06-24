@echo off
setlocal

echo =========================================
echo   Arena Duel - Package release (Portable + Installer)
echo =========================================
echo.

set "DIST_DIR=dist_release"
set "EXE=%DIST_DIR%\ArenaDuel\ArenaDuel.exe"
set "RELEASE_ROOT=dist_windows\ArenaDuel_Windows"
set "PORTABLE_DIR=%RELEASE_ROOT%\Portable\ArenaDuel"
set "INSTALLER_DIR=%RELEASE_ROOT%\Installer"
set "ZIP_PATH=dist_windows\ArenaDuel_Windows.zip"

if not exist "%EXE%" (
    echo [ERREUR] Executable introuvable : %EXE%
    echo Lance d'abord : build_exe_quick.bat
    exit /b 1
)

echo [INFO] Nettoyage du dossier release precedent...
if exist "%RELEASE_ROOT%" rmdir /s /q "%RELEASE_ROOT%"

echo [INFO] Creation des dossiers release...
mkdir "%PORTABLE_DIR%" >nul 2>nul || (
    echo [ERREUR] Impossible de creer %PORTABLE_DIR%
    exit /b 1
)
mkdir "%INSTALLER_DIR%" >nul 2>nul || (
    echo [ERREUR] Impossible de creer %INSTALLER_DIR%
    exit /b 1
)

echo [INFO] Copie de l'executable vers le mode portable...
xcopy "%EXE%" "%PORTABLE_DIR%\" /y >nul 2>nul
if errorlevel 1 (
    echo [ERREUR] Impossible de copier l'executable vers %PORTABLE_DIR%
    exit /b 1
)

echo [INFO] Copie des fichiers runtime et metadonnees...
copy /y "version.json" "%RELEASE_ROOT%\" >nul 2>nul
copy /y "app_runtime.json" "%RELEASE_ROOT%\" >nul 2>nul
copy /y "README_WINDOWS_RELEASE.txt" "%RELEASE_ROOT%\" >nul 2>nul
copy /y "LICENSE" "%RELEASE_ROOT%\LICENSE.txt" >nul 2>nul
copy /y "assets\images\arena_duel.ico" "%RELEASE_ROOT%\" >nul 2>nul

echo [INFO] Recherche d'Inno Setup pour generer l'installateur...
set "ISCC_EXE="
where ISCC >nul 2>nul
if not errorlevel 1 set "ISCC_EXE=ISCC"
if not defined ISCC_EXE if exist "C:\Program Files\Inno Setup 7\ISCC.exe" set "ISCC_EXE=C:\Program Files\Inno Setup 7\ISCC.exe"
if not defined ISCC_EXE if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC_EXE=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

if defined ISCC_EXE (
    echo [INFO] Generation de l'installateur Windows via ISCC...
    "%ISCC_EXE%" installer\arena_duel.iss
    if errorlevel 1 (
        echo [ERREUR] La generation de l'installateur a echoue.
    ) else (
        if exist "installer\Setup_ArenaDuel.exe" (
            copy /y "installer\Setup_ArenaDuel.exe" "%INSTALLER_DIR%\Setup_ArenaDuel.exe" >nul 2>nul
        )
    )
) else (
    echo [INFO] Inno Setup non detecte — generation de l'installateur sautee.
)

echo [INFO] Creation de l'archive ZIP de la release...
if exist "%ZIP_PATH%" del /q "%ZIP_PATH%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%RELEASE_ROOT%\*' -DestinationPath '%ZIP_PATH%' -Force" >nul 2>nul
if errorlevel 1 (
    echo [ERREUR] Echec de la creation de l'archive ZIP.
    exit /b 1
)

echo.
echo [OK] Packaging termine.
echo Dossier release : %RELEASE_ROOT%
echo Portable : %PORTABLE_DIR%\ArenaDuel.exe
if exist "%INSTALLER_DIR%\Setup_ArenaDuel.exe" echo Installateur : %INSTALLER_DIR%\Setup_ArenaDuel.exe
echo Archive : %ZIP_PATH%
echo.
exit /b 0
