Arena Duel — Version 1.0.0
==========================

Merci d'avoir choisi Arena Duel. Ce fichier contient les informations essentielles
pour utiliser la version distribuée sur Windows (portable et installateur).

Contenu de la livraison
-----------------------

- `ArenaDuel_Windows.zip` — archive portable. Dézippez puis lancez `Portable\ArenaDuel\ArenaDuel.exe`.
- `Setup_ArenaDuel.exe` — installateur Windows pour une installation standard.

Points importants
-----------------

- Aucun Python n'est requis pour utiliser les versions Windows fournies.
- Si Windows affiche un avertissement SmartScreen pour l'exécutable portable, utilisez l'installateur (`Setup_ArenaDuel.exe`).

Vérification d'intégrité
------------------------

Vérifiez les checksums SHA256 fournis (fichier .sha256 ou ci-dessous) :

PowerShell (Windows) :

  Get-FileHash .\Setup_ArenaDuel.exe -Algorithm SHA256

Linux / macOS :

  sha256sum ArenaDuel_Windows.zip

Signature (si applicable)
------------------------

Pour vérifier la signature Windows :

  signtool verify /pa /v Setup_ArenaDuel.exe

Support
-------

Ouvrez une issue sur GitHub : https://github.com/on2-511/Arena_duel/issues

Merci à toutes les personnes qui soutiennent et testent Arena Duel.

© 2026 O(n²)
