@echo off
setlocal

cd /d %~dp0\..

echo =========================================
echo   Arena Duel - Build Presentation + Installer
echo =========================================
echo.

call build_presentation.bat
if errorlevel 1 (
  exit /b 1
)

set "ISCC_EXE="
where ISCC >nul 2>nul
if not errorlevel 1 set "ISCC_EXE=ISCC"
if not defined ISCC_EXE if exist "C:\Program Files\Inno Setup 7\ISCC.exe" set "ISCC_EXE=C:\Program Files\Inno Setup 7\ISCC.exe"
if not defined ISCC_EXE if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC_EXE=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE (
  echo.
  echo [INFO] Inno Setup n est pas detecte sur ce poste.
  echo [INFO] L EXE est pret dans dist_release\ArenaDuel.
  echo [INFO] Pour generer le setup, compile installer\arena_duel.iss.
  echo.
  pause
  exit /b 0
)

"%ISCC_EXE%" installer\arena_duel.iss
if errorlevel 1 (
  echo.
  echo [ERREUR] La generation de l installateur a echoue.
  pause
  exit /b 1
)

echo.
echo [OK] Installateur genere avec succes.
echo Fichier final : installer\Setup_ArenaDuel.exe
echo.
pause