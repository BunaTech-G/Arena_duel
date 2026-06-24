# Auto-Update VPS

Arena Duel peut verifier une mise a jour au lancement sans changer le code a chaque release.

## Source de configuration

Le jeu lit les URLs de mise a jour dans cet ordre:

1. Variables d'environnement `ARENA_DUEL_UPDATE_MANIFEST_URL` et `ARENA_DUEL_UPDATE_PAGE_URL`
2. `app_runtime.json` ou `app_runtime.user.json` avec `update_manifest_url` et `update_page_url`
3. Valeurs par defaut GitHub

Exemple dans `app_runtime.user.json`:

```json
{
  "update_manifest_url": "https://updates.mondomaine.com/arena/version.json",
  "update_page_url": "https://updates.mondomaine.com/arena/releases"
}
```

## Manifest distant

Exemple minimal:

```json
{
  "version": "1.1.0",
  "windows_installer_url": "https://updates.mondomaine.com/arena/Setup_ArenaDuel.exe",
  "windows_installer_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "release_notes": [
    "Nouveau mode online plus stable",
    "Correction des sessions fantomes",
    "Detection Wi-Fi et Ethernet amelioree"
  ],
  "remind_later_hours": 24
}
```

Champs reconnus:

1. `version` : version distante comparee a la version locale du jeu.
2. `windows_installer_url` : installateur Windows telecharge si une mise a jour existe.
3. `windows_installer_sha256` : hash de verification de l'installateur.
4. `release_notes` : liste de changements affiches dans la fenetre de mise a jour.
5. `remind_later_hours` ou `remind_later_seconds` : duree avant de reproposer la meme version.

## Publication d'une release

1. Construire le nouvel installateur Windows.
2. Mettre a jour `version.json` avec la nouvelle version et les `release_notes`.
3. Calculer le hash du setup avec `python tools/update_windows_manifest.py version.json chemin/vers/Setup_ArenaDuel.exe`.
4. Uploader le setup sur le VPS.
5. Uploader le `version.json` final sur le VPS.

## Comportement en jeu

1. Au lancement, Arena Duel essaie de lire le manifest distant.
2. Si aucune connexion ou aucun manifest valide n'est disponible, le jeu continue normalement.
3. Si une version plus recente existe, le joueur voit `Mettre a jour` ou `Plus tard`.
4. Sous Windows, le jeu peut telecharger l'installateur puis l'ouvrir automatiquement.
