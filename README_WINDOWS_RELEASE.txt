Arena Duel - Livraison Windows
=========================================

Contenu de la livraison
-----------------------

- `Portable\ArenaDuel\ArenaDuel.exe` : version portable prête à lancer.
- `Installer\Setup_ArenaDuel.exe` : installateur Windows (si généré).

Prérequis
---------

- Windows 10 ou Windows 11 x64.
- Aucun Python requis pour exécuter la version Windows distribuée.
- `app_runtime.json` peut être placé à côté de l'exécutable portable pour configuration locale.

Génération de la livraison
--------------------------

1. Exécutez `build_windows_release.bat` ou `build_exe_quick.bat`.
2. Les artefacts locaux sont produits dans `dist_windows\ArenaDuel_Windows`.
3. Les livraisons binaires finales sont publiées via GitHub Releases (ex: `v1.0.0`).

Vérification d'intégrité (SHA256)
--------------------------------

PowerShell (Windows) :

	Get-FileHash .\Setup_ArenaDuel.exe -Algorithm SHA256

Linux / macOS :

	sha256sum ArenaDuel_Windows.zip

Signature Windows (optionnel)
-----------------------------

Variables d'environnement utilisées pour la signature (CI / local) :

- `ARENA_DUEL_SIGN_PFX`
- `ARENA_DUEL_SIGN_PFX_PASSWORD`
- `ARENA_DUEL_SIGN_CERT_SHA1`
- `ARENA_DUEL_SIGNTOOL`
- `ARENA_DUEL_SIGN_TIMESTAMP_URL`

Sans certificat éditeur, Windows peut afficher un avertissement SmartScreen ; l'utilisation d'un installateur signé réduit ce risque.

Téléchargement : https://github.com/on2-511/Arena_duel/releases/tag/v1.0.0
