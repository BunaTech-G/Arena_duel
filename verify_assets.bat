@echo off
setlocal

echo =========================================
echo   Arena Duel - Verification des assets requis
echo =========================================
echo.

set /a MISSING=0

rem Fichiers critiques
if not exist "app_runtime.json" (
  echo [ERREUR] Fichier manquant: app_runtime.json
  set /a MISSING+=1
)

if not exist "version.json" (
  echo [ERREUR] Fichier manquant: version.json
  set /a MISSING+=1
)

if not exist "assets\asset_manifest.json" (
  echo [ERREUR] Fichier manquant: assets\asset_manifest.json
  set /a MISSING+=1
)

if not exist "assets\icons\app.ico" (
  echo [ERREUR] Fichier manquant: assets\icons\app.ico
  set /a MISSING+=1
)

if not exist "assets\images\arena_duel.ico" (
  echo [ERREUR] Fichier manquant: assets\images\arena_duel.ico
  set /a MISSING+=1
)

if not exist "main.py" (
  echo [ERREUR] Fichier manquant: main.py
  set /a MISSING+=1
)

rem Dossiers importants
if not exist "assets" (
  echo [ERREUR] Dossier manquant: assets
  set /a MISSING+=1
)

if not exist "assets\icons" (
  echo [ERREUR] Dossier manquant: assets\icons
  set /a MISSING+=1
)

if not exist "assets\images" (
  echo [ERREUR] Dossier manquant: assets\images
  set /a MISSING+=1
)

if not exist "assets\sprites" (
  echo [ERREUR] Dossier manquant: assets\sprites
  set /a MISSING+=1
)

if not exist "assets\sounds" (
  echo [ERREUR] Dossier manquant: assets\sounds
  set /a MISSING+=1
)

if %MISSING% gtr 0 (
  echo.
  echo [ERREUR] %MISSING% fichiers ou dossiers manquants. Le build ne peut pas continuer.
  echo Verifie que tu as bien recupere le dossier assets et les fichiers de configuration.
  echo Si tu as clone le depot, execute: git submodule update --init --recursive
  exit /b 1
)

echo [OK] Tous les assets requis sont presents.
exit /b 0
