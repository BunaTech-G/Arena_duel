# Arena Duel — Version 1.0.0

Première version stable d'Arena Duel, un jeu desktop centré sur le duel local et le jeu en réseau local.

Résumé
------

Arena Duel propose : forge locale, hall LAN (hôte/clients), formats 1v1/2v2/3v3, et un historique des joutes.

Fonctionnalités principales
---------------------------

- Forge locale (création et édition d'équipes)
- Mode LAN avec invitation IP:port (hôte & clients sur le même réseau)
- Formats de match : 1v1, 2v2, 3v3
- Historique des joutes et chroniques des joueurs
- Version Windows portable (ZIP) et installateur (EXE)
- Support Arduino optionnel

Téléchargements officiels
------------------------

Release v1.0.0 disponible sur GitHub Releases : https://github.com/on2-511/Arena_duel/releases/tag/v1.0.0

Usage (Windows)
---------------

- Portable : dézippez `ArenaDuel_Windows.zip`, puis lancez `Portable\ArenaDuel\ArenaDuel.exe`.
- Installateur : exécutez `Setup_ArenaDuel.exe` en tant qu'administrateur pour une installation standard.
- Aucun Python n'est requis pour utiliser les versions Windows distribuées.

Vérification d'intégrité et signature
------------------------------------

- Vérifiez les checksums SHA256 :

  - PowerShell (Windows) : `Get-FileHash .\Setup_ArenaDuel.exe -Algorithm SHA256`
  - Linux/macOS : `sha256sum ArenaDuel_Windows.zip`

- Vérification de signature (si fournie) : `signtool verify /pa /v Setup_ArenaDuel.exe`

Conseils si Windows bloque la portable
-------------------------------------

- Si SmartScreen bloque l'exécutable portable, installez via `Setup_ArenaDuel.exe` signé.

Développement et build
----------------------

- Lancer en mode source : `run_local.bat` (prépare l'environnement Python si nécessaire).
- Build local (PyInstaller) : `build_exe_quick.bat`, `build_presentation.bat`.
- Pack release Windows : `build_windows_release.bat` (prépare portable, zip, et setup si Inno Setup présent).

Structure du dépôt
------------------

- `ui/`, `game/`, `network/`, `db/`, `assets/` — organisation principale.

Contribuer & Support
--------------------

- Ouvrez une issue : https://github.com/on2-511/Arena_duel/issues
- Licence : voir `LICENSE` à la racine du dépôt.

Remerciements
-------------

Merci à toutes les personnes qui soutiennent et testent Arena Duel.

© 2026 O(n²)

