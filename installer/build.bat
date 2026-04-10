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

where ISCC >nul 2>nul
if errorlevel 1 (
  echo.
  echo [INFO] Inno Setup n est pas detecte sur ce poste.
  echo [INFO] L EXE est pret dans dist_release\ArenaDuel.
  echo [INFO] Pour generer le setup, compile installer\arena_duel.iss.
  echo.
  pause
  exit /b 0
)

ISCC installer\arena_duel.iss
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