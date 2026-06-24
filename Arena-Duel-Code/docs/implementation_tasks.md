Tâches d'implémentation — Refonte visuelle Arena Duel

But : définir étapes techniques et fichiers à modifier pour intégrer la refonte UI/HUD et assets.

Priorité haute (Phase 1 — prototype HUD & map lisible)
1) Ajouter tokens visuels (couleurs, typos, tailles)
   - Fichier cible : `ui/theme.py`
   - Livraison : palette hex, tailles de fonte, tokens boutons, tokens HUD
   - Estimation : 1–2 jours

2) Implémenter layout HUD minimal (positionner éléments)
   - Fichier cible : `ui/hud_panels.py`
   - Actions : timer central, scores aux coins, barre de compétences bas-centre, portrait bas-gauche
   - Livraison : layout non stylisé mais fonctionnel (placeholders)
   - Estimation : 1–2 jours

3) Créer assets prototypes (placeholder SVG/PNGs)
   - Dossier : `assets/ui/` (icônes, buttons, ability-ring.svg)
   - Fichiers : `ability_ring.svg`, `icon_timer.svg`, `icon_score.svg`, `portrait_placeholder.png`
   - Estimation : 1 jour

4) Adapter arène prototype pour lisibilité
   - Fichiers cibles : `game/arena_layout.py`, `game/arena.py`
   - Actions : ajouter obstacles simples (collisions + visuel), définir spawn points symétriques
   - Livraison : arène prototype avec 3 obstacles tactiques
   - Estimation : 2 jours

5) Intégrer palette & UI dans launcher/menus
   - Fichiers : `ui/launcher.py`, `ui/player_select.py`
   - Actions : appliquer `ui/theme.py` aux fenêtres, boutons, listes
   - Estimation : 1 jour

Priorité moyenne (Phase 2 — art & animations)
6) Produire 1 personnage stylisé complet (idle/walk/attack)
   - Dossier : `assets/characters/<char_id>/`
   - Résolutions : 64/96/128
   - Estimation : 3–5 jours (artiste)

7) VFX & anneau de cooldown
   - Dossier : `assets/vfx/`
   - Fichiers : sprite sheet ou SVG anim pour anneau cooldown
   - Estimation : 1–2 jours

8) Tests d’ergonomie et ajustements
   - Actions : tests lisibilité HUD à 1280x720 et 1920x1080, ajuster tailles et contrastes
   - Estimation : 1 jour

Livrables techniques attendus
- `ui/theme.py` : tokens et helpers (couleurs, fontes, tailles)
- `ui/hud_panels.py` : layout HUD modulable
- `game/arena_layout.py` / `game/arena.py` : arène prototype avec obstacles
- `assets/ui/` et `assets/characters/` : placeholders et conventions de naming
- Documentation courte : `docs/wireframes_UI.md`, `docs/assets_checklist.md`, `docs/implementation_tasks.md`

Prochaines étapes proposées
- Je peux implémenter immédiatement `ui/theme.py` avec les tokens de base.
- Ensuite, je prototyperai `ui/hud_panels.py` en plaçant des placeholders.

Dis-moi si je commence par :
- A) `ui/theme.py` (tokens couleurs/typos) puis HUD,
- B) Prototype HUD direct (`ui/hud_panels.py`) avec placeholders,
- C) Les deux (ordre A puis B).