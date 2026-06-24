Arena Duel - Livraison Windows
=========================================

Contenu de la livraison
-----------------------

- Portable\ArenaDuel\ArenaDuel.exe : version portable prete a lancer.
- Installer\Setup_ArenaDuel.exe : installateur Windows (si genere).

Prerequis
---------

- Windows 10 ou Windows 11 x64.
- Aucun Python requis pour executer la version portable.
- app_runtime.json reste editable a cote de l exe portable.

Comment generer la livraison
----------------------------
1. Lance `build_windows_release.bat` ou `build_exe_quick.bat`.
2. Localement les artefacts sont produits dans `dist_windows\ArenaDuel_Windows`.
3. Les livraisons finales sont publiées sur GitHub Releases (ex: `v1.0.0`).
	- Téléchargement public : https://github.com/on2-511/Arena_duel/releases/tag/v1.0.0

Ce que fait le script build_windows_release.bat
-----------------------------------------------

- Build PyInstaller du jeu.
- Preparation d un dossier Portable.
- Generation d un setup via Inno Setup si disponible.
- Compression ZIP finale de la livraison.
- Synchronisation optionnelle du hash installateur dans version.json.

Signature Windows (optionnel)
-----------------------------

- ARENA_DUEL_SIGN_PFX
- ARENA_DUEL_SIGN_PFX_PASSWORD
- ARENA_DUEL_SIGN_CERT_SHA1
- ARENA_DUEL_SIGNTOOL
- ARENA_DUEL_SIGN_TIMESTAMP_URL

Sans certificat editeur, Windows peut afficher SmartScreen.