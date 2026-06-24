# CI: Build and Release

Ce workflow GitHub Actions automatise la construction Windows, la génération des artefacts (portable ZIP + installer) et la publication d'une Release GitHub.

Fichier workflow: `.github/workflows/build-and-release.yml`

Secrets requis (Settings → Secrets → Actions):

- `ARENA_DUEL_SIGN_PFX` (optionnel): contenu du fichier PFX encodé en base64. Utilisé pour signer l'installateur si vous activez la signature.
- `ARENA_DUEL_SIGN_PFX_PASSWORD` (optionnel): mot de passe du fichier PFX.
- `GITHUB_TOKEN`: fourni automatiquement par GitHub Actions (ne pas remplacer sauf cas avancé).

Utilisation manuelle depuis l'UI:

1. Ouvrez Actions → Build and Release → Run workflow.
2. Saisissez le tag (ex: `v1.0.1`) et cochez `sign=true` si vous avez configuré le PFX.

Notes:

- Le workflow s'exécute sous `windows-latest` et dépend des scripts de build présents dans le dépôt (`build_windows_release.bat`, `build_exe_quick.bat`, `build_presentation.bat`). Il essaie ces scripts dans cet ordre.
- Le signeur utilise `signtool` disponible sur runners Windows. Fournissez `ARENA_DUEL_SIGN_PFX` encodé en base64 pour éviter d'exposer le fichier brut.
- Les artefacts sont publiés en Release via `softprops/action-gh-release`.

Si vous souhaitez :
- ajouter un job multi-plateforme (mac/linux) → dites‑le.
- automatiser le tagging (par version in repo) → je peux ajouter une étape pour lire `version.json`.
