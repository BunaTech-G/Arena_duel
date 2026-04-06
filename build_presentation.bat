@echo off
echo =========================================
echo   Arena Duel - Build Presentation EXE
echo =========================================
echo.

if not exist .\.venv\Scripts\python.exe (
    echo [ERREUR] Le venv n existe pas.
    echo Lance d abord : setup_env.bat
    pause
    exit /b 1
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

.\.venv\Scripts\python.exe -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onedir ^
  --windowed ^
  --name ArenaDuel ^
  --icon assets\icons\app.ico ^
  --collect-data customtkinter ^
  --add-data "assets;assets" ^
  --add-data "app_runtime.json;." ^
  main.py

echo.
echo [OK] Build terminé.
echo Dossier final : dist\ArenaDuel
echo.
pause
