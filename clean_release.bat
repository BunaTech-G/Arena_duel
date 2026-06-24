@echo off
setlocal

echo =========================================
echo   Arena Duel - Clean release artifacts
echo =========================================
echo.

echo [INFO] Suppression des repertoires temporaires et de build...
if exist build_release rmdir /s /q build_release
if exist dist_release rmdir /s /q dist_release
if exist dist_windows rmdir /s /q dist_windows
if exist __pycache__ rmdir /s /q __pycache__

echo [INFO] Suppression des fichiers temporaires PyInstaller...
if exist *.spec del /q *.spec >nul 2>nul

echo [INFO] Nettoyage du dossier .venv cache pip wheels...
if exist .venv\Lib\site-packages\__pycache__ rmdir /s /q .venv\Lib\site-packages\__pycache__ >nul 2>nul

echo.
echo [OK] Nettoyage termine.
exit /b 0
