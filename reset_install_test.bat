@echo off
setlocal EnableExtensions

echo =========================================
echo   Arena Duel - Reset test installation
echo =========================================
echo.
echo Ce script supprime UNIQUEMENT les elements locaux du projet:
echo   - .venv (racine)
echo   - Arena-Duel-Code\.venv
echo   - dossiers __pycache__
echo   - fichiers .pyc / .pyo
echo   - build/dist locaux
echo.
echo Il NE desinstalle PAS Python global ni les paquets globaux.
echo.

if /I not "%~1"=="--yes" (
    choice /C ON /N /M "Continuer ? (O/N): "
    if errorlevel 2 (
        echo.
        echo [INFO] Operation annulee.
        exit /b 0
    )
)

cd /d "%~dp0"

echo.
echo [1/5] Suppression des environnements virtuels...
if exist ".venv" (
    rmdir /s /q ".venv"
    echo   - .venv supprime
) else (
    echo   - .venv absent
)

if exist "Arena-Duel-Code\.venv" (
    rmdir /s /q "Arena-Duel-Code\.venv"
    echo   - Arena-Duel-Code\.venv supprime
) else (
    echo   - Arena-Duel-Code\.venv absent
)

echo.
echo [2/5] Suppression des caches Python...
for /d /r %%D in (__pycache__) do (
    if exist "%%D" rmdir /s /q "%%D"
)
for /r %%F in (*.pyc *.pyo) do (
    if exist "%%F" del /f /q "%%F" >nul 2>nul
)
echo   - caches Python nettoyes

echo.
echo [3/5] Suppression des artefacts build/dist (racine)...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "dist_demo" rmdir /s /q "dist_demo"
if exist "dist_release" rmdir /s /q "dist_release"
if exist "dist_windows" rmdir /s /q "dist_windows"
echo   - artefacts racine nettoyes

echo.
echo [4/5] Suppression des artefacts build/dist (Arena-Duel-Code)...
if exist "Arena-Duel-Code\build" rmdir /s /q "Arena-Duel-Code\build"
if exist "Arena-Duel-Code\dist" rmdir /s /q "Arena-Duel-Code\dist"
if exist "Arena-Duel-Code\dist_demo" rmdir /s /q "Arena-Duel-Code\dist_demo"
if exist "Arena-Duel-Code\dist_release" rmdir /s /q "Arena-Duel-Code\dist_release"
if exist "Arena-Duel-Code\dist_windows" rmdir /s /q "Arena-Duel-Code\dist_windows"
echo   - artefacts Arena-Duel-Code nettoyes

echo.
echo [5/5] Nettoyage termine.
echo.
echo Tu peux maintenant tester une install "comme sur un nouveau PC":
echo   1) setup_env.bat
echo   2) run_local.bat
echo.

exit /b 0
