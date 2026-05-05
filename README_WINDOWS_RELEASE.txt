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
- Quand le setup est genere, le script met aussi a jour automatiquement
  windows_installer_sha256 dans version.json a partir du setup final.

Publication GitHub et auto-update
---------------------------------

- Le manifest version.json est lu par le jeu au demarrage pour verifier si une
  nouvelle version est disponible.
- Avant une publication, incremente la valeur version dans version.json.
- Conserve le nom Setup_ArenaDuel.exe pour l installateur publie afin que
  windows_installer_url reste valide sans changement de code.
- Lance build_windows_release.bat, puis recupere l installateur dans
  dist_windows\ArenaDuel_Windows\Installer\Setup_ArenaDuel.exe.
- Publie une release GitHub et ajoute Setup_ArenaDuel.exe comme asset.
- Le lien windows_installer_url pointe deja vers releases/latest/download,
  donc la derniere release publiee devient automatiquement la source de mise a
  jour.
- build_windows_release.bat met a jour automatiquement
  windows_installer_sha256 dans version.json si le setup a bien ete genere.
- Si tu veux changer la cadence de rappel, ajuste remind_later_hours dans
  version.json avant la publication.

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