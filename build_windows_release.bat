@echo off
setlocal

echo =========================================
echo   Arena Duel - Livraison Windows
echo =========================================
echo.

set "PYTHON_EXE=.\.venv\Scripts\python.exe"
set "DIST_DIR=dist_release"
set "RELEASE_DIR=dist_windows\ArenaDuel_Windows"
set "PORTABLE_DIR=%RELEASE_DIR%\Portable\ArenaDuel"
set "INSTALLER_DIR=%RELEASE_DIR%\Installer"
set "ZIP_PATH=dist_windows\ArenaDuel_Windows.zip"
set "EXE_PATH=%DIST_DIR%\ArenaDuel\ArenaDuel.exe"
set "SETUP_PATH=installer\Setup_ArenaDuel.exe"
set "SIGN_TIMESTAMP_URL=https://timestamp.digicert.com"
set "SETUP_READY="

if defined ARENA_DUEL_SIGN_TIMESTAMP_URL (
    set "SIGN_TIMESTAMP_URL=%ARENA_DUEL_SIGN_TIMESTAMP_URL%"
)

if not exist "%PYTHON_EXE%" (
    echo [ERREUR] Le venv n existe pas.
    echo Lance d abord : setup_env.bat
    call :maybe_pause
    exit /b 1
)

if exist "dist_windows" rmdir /s /q "dist_windows"

set "ARENA_DUEL_NO_PAUSE=1"
call build_presentation.bat
if errorlevel 1 (
    exit /b 1
)

call :maybe_sign "%EXE_PATH%"
if errorlevel 1 (
    exit /b 1
)

call :find_iscc
if defined ISCC_EXE (
    echo [INFO] Generation de l installateur Windows...
    "%ISCC_EXE%" installer\arena_duel.iss
    if errorlevel 1 (
        echo.
        echo [ERREUR] La generation de l installateur a echoue.
        call :maybe_pause
        exit /b 1
    )

    set "SETUP_READY=1"

    call :maybe_sign "%SETUP_PATH%"
    if errorlevel 1 (
        exit /b 1
    )
) else (
    echo [INFO] Inno Setup n est pas detecte sur ce poste.
    echo [INFO] La livraison sera preparee en mode portable seulement.
)

mkdir "%PORTABLE_DIR%" >nul 2>nul
xcopy "%DIST_DIR%\ArenaDuel\*" "%PORTABLE_DIR%\" /e /i /y >nul
if errorlevel 1 (
    echo.
    echo [ERREUR] Impossible de preparer le dossier portable.
    call :maybe_pause
    exit /b 1
)

copy /y "README_WINDOWS_RELEASE.txt" "%RELEASE_DIR%\README_WINDOWS_RELEASE.txt" >nul
copy /y "LICENSE" "%RELEASE_DIR%\LICENSE.txt" >nul

if defined SETUP_READY if exist "%SETUP_PATH%" (
    mkdir "%INSTALLER_DIR%" >nul 2>nul
    copy /y "%SETUP_PATH%" "%INSTALLER_DIR%\Setup_ArenaDuel.exe" >nul
)

if exist "%ZIP_PATH%" del /q "%ZIP_PATH%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%RELEASE_DIR%\*' -DestinationPath '%ZIP_PATH%' -Force" >nul
if errorlevel 1 (
    echo.
    echo [ERREUR] Impossible de generer l archive zip Windows.
    call :maybe_pause
    exit /b 1
)

echo.
echo [OK] Livraison Windows preparee.
echo Dossier release : %RELEASE_DIR%
echo Portable : %PORTABLE_DIR%\ArenaDuel.exe
if defined SETUP_READY if exist "%INSTALLER_DIR%\Setup_ArenaDuel.exe" (
    echo Installateur : %INSTALLER_DIR%\Setup_ArenaDuel.exe
)
echo Archive zip : %ZIP_PATH%
echo.
call :maybe_pause
exit /b 0

:find_iscc
set "ISCC_EXE="
where ISCC >nul 2>nul
if not errorlevel 1 set "ISCC_EXE=ISCC"
if not defined ISCC_EXE if exist "C:\Program Files\Inno Setup 7\ISCC.exe" set "ISCC_EXE=C:\Program Files\Inno Setup 7\ISCC.exe"
if not defined ISCC_EXE if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC_EXE=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
exit /b 0

:find_signtool
set "SIGNTOOL_EXE="
if defined ARENA_DUEL_SIGNTOOL if exist "%ARENA_DUEL_SIGNTOOL%" set "SIGNTOOL_EXE=%ARENA_DUEL_SIGNTOOL%"
if not defined SIGNTOOL_EXE (
    where signtool >nul 2>nul
    if not errorlevel 1 set "SIGNTOOL_EXE=signtool"
)
if not defined SIGNTOOL_EXE (
    for %%P in ("C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe") do set "SIGNTOOL_EXE=%%~fP"
)
exit /b 0

:maybe_sign
set "TARGET_FILE=%~1"
if not exist "%TARGET_FILE%" (
    echo [ERREUR] Fichier introuvable pour la signature : %TARGET_FILE%
    exit /b 1
)

set "SIGN_MODE="
if defined ARENA_DUEL_SIGN_PFX set "SIGN_MODE=pfx"
if not defined SIGN_MODE if defined ARENA_DUEL_SIGN_CERT_SHA1 set "SIGN_MODE=sha1"

if not defined SIGN_MODE (
    echo [INFO] Signature Windows non configuree. Artefact laisse non signe : %TARGET_FILE%
    exit /b 0
)

call :find_signtool
if not defined SIGNTOOL_EXE (
    echo [ERREUR] Signature demandee mais signtool.exe est introuvable.
    exit /b 1
)

echo [INFO] Signature de %TARGET_FILE%...
if /I "%SIGN_MODE%"=="pfx" (
    if not exist "%ARENA_DUEL_SIGN_PFX%" (
        echo [ERREUR] Certificat PFX introuvable : %ARENA_DUEL_SIGN_PFX%
        exit /b 1
    )
    if not defined ARENA_DUEL_SIGN_PFX_PASSWORD (
        echo [ERREUR] ARENA_DUEL_SIGN_PFX_PASSWORD est requis pour signer via PFX.
        exit /b 1
    )
    "%SIGNTOOL_EXE%" sign /fd SHA256 /td SHA256 /tr "%SIGN_TIMESTAMP_URL%" /f "%ARENA_DUEL_SIGN_PFX%" /p "%ARENA_DUEL_SIGN_PFX_PASSWORD%" "%TARGET_FILE%"
    if errorlevel 1 exit /b 1
) else (
    "%SIGNTOOL_EXE%" sign /fd SHA256 /td SHA256 /tr "%SIGN_TIMESTAMP_URL%" /sha1 "%ARENA_DUEL_SIGN_CERT_SHA1%" "%TARGET_FILE%"
    if errorlevel 1 exit /b 1
)

"%SIGNTOOL_EXE%" verify /pa "%TARGET_FILE%" >nul
if errorlevel 1 (
    echo [ERREUR] Verification de signature echouee : %TARGET_FILE%
    exit /b 1
)

exit /b 0

:maybe_pause
if /I "%ARENA_DUEL_NO_PAUSE%"=="1" exit /b 0
pause
exit /b 0