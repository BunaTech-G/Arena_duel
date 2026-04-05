@echo off
setlocal

REM Se placer à la racine du projet
cd /d %~dp0\..

echo ================================
echo  Arena Duel - Build PyInstaller
echo ================================

REM Trouver automatiquement le dossier CustomTkinter
for /f "delims=" %%i in ('python -c "import customtkinter, os; print(os.path.dirname(customtkinter.__file__))"') do set CTK_DIR=%%i

if not exist "%CTK_DIR%" (
    echo [ERREUR] Dossier CustomTkinter introuvable.
    pause
    exit /b 1
)

echo CustomTkinter detecte ici :
echo %CTK_DIR%

python -m pip install -U pyinstaller

REM Nettoyage ancien build
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build
pyinstaller --noconfirm --clean --onedir --windowed ^
  --name "ArenaDuel" ^
  --icon "assets\\images\\arena_duel.ico" ^
  --add-data "%CTK_DIR%;customtkinter/" ^
  --add-data "assets;assets" ^
  main.py

echo.
echo Build termine.
echo Le dossier genere est :
echo dist\\ArenaDuel
pause