# Installation — Arena Duel

## Vue d'ensemble

Ce document explique comment installer **Arena Duel** proprement sur un nouveau PC en mode **développement / test LAN** et en mode **démonstration / portable**.

Le projet repose sur :

- **Python 3.14.x** pour le mode développement
- un **environnement virtuel** (`.venv`)
- un fichier **`requirements-dev.txt`**
- des scripts **`.bat`** pour automatiser l'installation et le lancement

> Recommandation importante : utilisez **Python 3.14.x** et non Python 3.15 alpha/pré-release.

---

## 1. Prérequis

### Prérequis système

- Windows 10 / 11 / Windows Server
- Accès réseau local pour le mode LAN
- Accès Internet si vous utilisez GitHub / pip

### Prérequis logiciels

- **Python 3.14.x**
- **Git** ou **TortoiseGit** si vous récupérez le projet depuis GitHub
- **XAMPP** si vous utilisez la partie base de données (MariaDB / phpMyAdmin)

---

## 2. Structure recommandee du projet

Le dossier du projet doit contenir au minimum :

```text
arena_duel/
├── main.py
├── main_lan.py
├── requirements-dev.txt
├── requirements-lan.txt
├── setup_env.bat
├── setup_env_lan.bat
├── run_local.bat
├── run_lan_ui.bat
├── run_server.bat
├── run_client_lan.bat
├── schema_v2.sql
├── shema.sql
├── build_presentation.bat
├── ArenaDuel.spec
├── requirements-arduino.txt
├── ui/
├── game/
├── hardware/
├── db/
├── network/
├── docs/
└── assets/
```

Notes V1 :

- schema_v2.sql est le bootstrap SQL canonique pour une base neuve
- shema.sql est conserve comme alias legacy pour compatibilite avec d'anciens guides
- run_lan_ui.bat est le point d'entree recommande pour le hall LAN graphique
- run_client_lan.bat reste un outil CLI de diagnostic reseau
- requirements-arduino.txt contient uniquement la dependance optionnelle pyserial

---

## 3. Installation propre sur un nouveau PC (mode développement)

### Étape 1 — Installer Python

Installez **Python 3.14.x**.

Pendant l'installation, cochez impérativement :

```text
Add Python to PATH
```

---

### Étape 2 — Récupérer le projet

Deux possibilités :

- **Cloner le dépôt GitHub**
- **Copier le dossier source** via clé USB / ZIP / partage réseau

Exemple de destination :

```powershell
C:\Users\NomUtilisateur\Desktop\arena_duel
```

---

### Étape 3 — Ouvrir PowerShell dans le projet

```powershell
cd C:\Users\NomUtilisateur\Desktop\arena_duel
```

---

### Étape 4 — Créer automatiquement l'environnement Python

Lancez :

```powershell
setup_env.bat
```

Ce script doit :

1. créer le venv `.venv`
2. mettre `pip` à jour
3. installer toutes les dépendances depuis `requirements-dev.txt`

---

### Étape 5 — Lancer le projet

#### Application complète

```powershell
run_local.bat
```

#### Hall LAN graphique

```powershell
run_lan_ui.bat
```

#### Serveur LAN CLI

```powershell
run_server.bat
```

#### Client LAN CLI de diagnostic

```powershell
run_client_lan.bat
```

#### Build presentation EXE

```powershell
build_presentation.bat
```

#### Option Arduino facultative

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-arduino.txt
```

Puis activez le bridge dans `app_runtime.json` seulement si vous branchez le montage.

---

## 4. Fichiers recommandés à la racine

### `requirements-dev.txt`

Créez ce fichier à la racine du projet :

```txt
customtkinter==5.2.2
pygame-ce==2.5.7
mariadb
```

### `requirements-arduino.txt`

Fichier optionnel pour le pont série Arduino :

```txt
pyserial>=3.5,<4
```

---

### `setup_env.bat`

Créez ce fichier à la racine du projet :

```bat
@echo off
echo =========================================
echo   Arena Duel - Setup environnement dev
echo =========================================
echo.

py -3.14 -m venv .venv
if errorlevel 1 (
    echo [ERREUR] Impossible de creer le venv avec Python 3.14
    pause
    exit /b 1
)

.\.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERREUR] Impossible de mettre pip a jour
    pause
    exit /b 1
)

.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if errorlevel 1 (
    echo [ERREUR] Impossible d installer les dependances
    pause
    exit /b 1
)

echo.
echo [OK] Environnement configure avec succes.
echo.
echo Utilisation :
echo   - run_local.bat
echo   - run_server.bat
echo   - run_client_lan.bat
echo.
pause
```

---

### `run_local.bat`

```bat
@echo off
echo =========================================
echo   Arena Duel - Lancement local
echo =========================================
echo.

if not exist .\.venv\Scripts\python.exe (
    echo [ERREUR] Le venv n existe pas.
    echo Lance d abord : setup_env.bat
    pause
    exit /b 1
)

.\.venv\Scripts\python.exe main.py
pause
```

---

### `run_server.bat`

```bat
@echo off
echo =========================================
echo   Arena Duel - Serveur LAN
echo =========================================
echo.

if not exist .\.venv\Scripts\python.exe (
    echo [ERREUR] Le venv n existe pas.
    echo Lance d abord : setup_env.bat
    pause
    exit /b 1
)

.\.venv\Scripts\python.exe -m network.server --host 0.0.0.0 --port 5000
pause
```

---

### `run_client_lan.bat`

```bat
@echo off
echo =========================================
echo   Arena Duel - Client LAN (CLI)
echo =========================================
echo.

if not exist .\.venv\Scripts\python.exe (
    echo [ERREUR] Le venv n existe pas.
    echo Lance d abord : setup_env.bat
    pause
    exit /b 1
)

set /p SERVER_IP=Entrez l IP du serveur : 
set /p PLAYER_NAME=Entrez le pseudo : 

.\.venv\Scripts\python.exe -m network.client --host %SERVER_IP% --port 5000 --name %PLAYER_NAME%
pause
```

---

## 5. Base de données (MariaDB / XAMPP)

Si vous utilisez la sauvegarde des joueurs, matchs et scores :

1. Installez **XAMPP**
2. Démarrez **Apache** et **MySQL**
3. Ouvrez :

```text
http://localhost/phpmyadmin
```

1. Creez la base :

```text
arena_duel_v2_db
```

1. Pour une installation neuve, importez le fichier :

```text
shema.sql
```

1. Si vous avez deja une base legacy avec des donnees, appliquez ensuite :

```text
db/migrations/001_v1_to_v2.sql
```

---

## 6. Mode LAN (plusieurs PC)

### PC 1 — Serveur

```powershell
run_server.bat
```

### PC 2 / PC 3 / ... — Clients

Deux options :

#### Option A — interface complète

```powershell
run_local.bat
```

Puis :

- cliquer sur **Multijoueur LAN**
- entrer l'IP du serveur
- entrer le pseudo
- cliquer sur **Se connecter**

#### Option B — test CLI

```powershell
run_client_lan.bat
```

---

## 7. Mise à jour du projet avec Git

### Important

Un `git push` sur un PC **ne met pas automatiquement les autres PC à jour**.

Sur chaque autre PC, il faut faire un **pull**.

### Avec TortoiseGit

1. clic droit dans le dossier du projet
2. **Git Sync**
3. **Pull**

Si des dépendances ont été ajoutées, relancez ensuite :

```powershell
setup_env.bat
```

---

## 8. Mode démonstration / portable

Pour une démo sans installer Python :

- utilisez le build portable généré par **PyInstaller**
- prenez le dossier :

```text
dist\ArenaDuel
```

- ou distribuez une archive :

```text
ArenaDuel_Portable.zip
```

### Attention

Dans ce mode :

- **Python n'est pas nécessaire** sur le PC cible
- mais la **base de données reste séparée**

Si le projet depend de MariaDB / phpMyAdmin, il faut toujours installer XAMPP et importer `shema.sql` pour une base neuve, ou appliquer `db/migrations/001_v1_to_v2.sql` sur une base legacy existante.

---

## 9. Bonnes pratiques

- Toujours utiliser **Python 3.14.x** pour ce projet
- Toujours lancer **`setup_env.bat`** sur un nouveau PC
- Ne pas installer les modules à la main un par un sauf dépannage exceptionnel
- Ne pas pousser **`.venv`**, **`dist`** ou **`build`** sur GitHub
- Toujours faire un **pull** sur les autres PC après un push

---

## 10. `.gitignore` recommandé

```gitignore
__pycache__/
*.pyc
*.pyo
*.pyd

.venv/
venv/
env/

build/
dist/
*.spec

.idea/
.vscode/
.DS_Store
Thumbs.db
*.log
*.tmp
*.bak
.coverage
htmlcov/
.pytest_cache/
*.sqlite3
*.db
```

---

## 11. Procédure rapide résumée

Sur un nouveau PC :

1. Installer **Python 3.14.x**
2. Récupérer le projet
3. Ouvrir PowerShell dans le dossier du projet
4. Lancer :

```powershell
setup_env.bat
```

1. Lancer ensuite selon le besoin :

```powershell
run_local.bat
```

ou

```powershell
run_server.bat
```

ou

```powershell
run_client_lan.bat
```

---

## 12. Dépannage rapide

### Erreur : module manquant

Relancer :

```powershell
setup_env.bat
```

### GitHub inaccessible

Vérifier :

- passerelle réseau
- DNS
- accès Internet

### Le client LAN ne se connecte pas

Vérifier :

- que le serveur est lancé
- l'adresse IP du serveur
- le port `5000`
- le pare-feu Windows

---

## 13. Conclusion

La méthode recommandée pour **Arena Duel** est :

- **source + venv + requirements + scripts .bat** pour le développement et les tests LAN
- **build portable PyInstaller** pour la démonstration

Cette organisation permet :

- une installation rapide
- une configuration identique sur chaque PC
- moins d’erreurs
- une maintenance plus simple
- une démo plus professionnelle
