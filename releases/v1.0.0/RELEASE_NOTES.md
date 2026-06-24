# Release v1.0.0

Date: 2026-06-24

Résumé
-------

Première release publique Windows : distribution portable (ZIP) et installateur (EXE).

Assets
------

- ArenaDuel_Windows.zip — archive portable (dossier Portable/ArenaDuel).
- Setup_ArenaDuel.exe — installateur Windows (Inno Setup).

Téléchargement
-------------

Release publique : https://github.com/on2-511/Arena_duel/releases/tag/v1.0.0

Installation rapide
-------------------

- Portable : dézipper `ArenaDuel_Windows.zip`, puis exécuter `Portable\ArenaDuel\ArenaDuel.exe`.
- Installateur : exécuter `Setup_ArenaDuel.exe` en tant qu'administrateur pour une installation standard.

Vérification d'intégrité (optionnel)
-----------------------------------

- PowerShell : `Get-FileHash .\Setup_ArenaDuel.exe -Algorithm SHA256`
- Linux/macOS : `sha256sum ArenaDuel_Windows.zip`

Signature (si disponible)
-------------------------

- Vérifier la signature Windows : `signtool verify /pa /v Setup_ArenaDuel.exe`.
- Pour signer : utilisez un certificat PFX et `signtool` (exemple dans le README principal).

Notes techniques
---------------

- Les binaires volumineux sont publiés dans GitHub Releases. Ils ont été retirés du suivi Git dans l'arbre du dépôt pour alléger l'historique.
- Pour construire localement : exécuter `build_windows_release.bat` ou `build_exe_quick.bat`.

Support & Licence
-----------------

- Ouvrez une issue : https://github.com/on2-511/Arena_duel/issues
- Licence : voir le fichier `LICENSE` à la racine du dépôt.

Crédits
-------

- Mainteneur : `on2-511`

