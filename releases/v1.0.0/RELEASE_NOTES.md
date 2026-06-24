# Arena Duel — Version 1.0.0 (Première version stable)

Date : 2026-06-24

Résumé
-------

Première version stable d'Arena Duel, un jeu desktop Python centré sur le duel local et le jeu en réseau local.

Fonctionnalités clés
--------------------

- Forge locale (édition et préparation d'équipes localement)
- Mode LAN avec invitation IP:port (hôte et clients sur le même réseau)
- Formats de match : 1v1, 2v2 et 3v3
- Historique des joutes et chroniques des joueurs
- Version Windows portable (ZIP)
- Installateur Windows (EXE)
- Support Arduino optionnel

Livrables
---------

- `ArenaDuel_Windows.zip` — archive portable contenant le dossier `Portable/ArenaDuel`.
- `Setup_ArenaDuel.exe` — installateur Windows (généré via Inno Setup si disponible).

Intégrité et vérification
-------------------------

Vérifiez les checksums SHA256 pour valider l'intégrité des fichiers téléchargés :

- PowerShell (Windows) :

	Get-FileHash .\Setup_ArenaDuel.exe -Algorithm SHA256

- Linux/macOS :

	sha256sum ArenaDuel_Windows.zip

Signature
---------

Si un certificat de signature est fourni, vous pouvez vérifier la signature Windows :

signtool verify /pa /v Setup_ArenaDuel.exe

Remarques d'utilisation
-----------------------

- Aucun Python n'est nécessaire pour utiliser la version Windows distribuée (portable ou installée).
- Si Windows bloque la version portable (SmartScreen), utilisez l'installateur `Setup_ArenaDuel.exe`.
- Les binaires volumineux sont distribués via GitHub Releases ; le dépôt ne conserve pas les grosses archives dans l'historique Git.

Téléchargement
--------------

Release publique : https://github.com/on2-511/Arena_duel/releases/tag/v1.0.0

Remerciements
-------------

Merci à toutes les personnes qui soutiennent et testent Arena Duel.

© 2026 O(n²)

