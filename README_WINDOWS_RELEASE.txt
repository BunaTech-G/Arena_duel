Arena Duel - Livraison Windows
=========================================

Cette livraison contient deux modes de distribution :

- Portable\ArenaDuel\ArenaDuel.exe : version portable a lancer directement.
- Installer\Setup_ArenaDuel.exe : installateur Windows si present.

Configuration et prerequis
--------------------------

- Windows 10 ou Windows 11 x64.
- Le fichier app_runtime.json reste editable a cote de l exe portable.
- Les modes forge locale et hall LAN sont inclus.
- Selon la configuration choisie, certaines fonctions peuvent utiliser MariaDB,
  mais le build Windows inclut deja les assets et le runtime Python embarque.

Livraison publiee
-----------------

- Le script build_windows_release.bat prepare le dossier dist_windows,
  une archive zip et, si Inno Setup est installe, un vrai setup Windows.
- Le script sait aussi signer l exe et le setup si un certificat Windows est
  configure dans l environnement.

Variables d environnement de signature
--------------------------------------

- ARENA_DUEL_SIGN_PFX : chemin vers un certificat .pfx.
- ARENA_DUEL_SIGN_PFX_PASSWORD : mot de passe du certificat .pfx.
- ARENA_DUEL_SIGN_CERT_SHA1 : empreinte SHA1 d un certificat deja installe.
- ARENA_DUEL_SIGNTOOL : chemin explicite vers signtool.exe.
- ARENA_DUEL_SIGN_TIMESTAMP_URL : URL de timestamp RFC 3161.

Tant qu aucune signature editeur n est appliquee, Windows peut encore afficher
un avertissement SmartScreen sur certaines machines. La chaine de build est
desormais prete pour une signature SHA-256 afin de limiter ces alertes.