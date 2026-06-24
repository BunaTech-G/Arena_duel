Checklist d'assets — Arena Duel

But : liste d'assets nécessaire et conventions pour l'équipe artistique et technique.

1) Personnages (squelettes stylisés)
- Sheets par personnage : 3 résolutions cibles -> 64px, 96px, 128px hauteur.
- Animations minimales : idle (6 frames), walk (8), attack (6), hit (4), dash (4), death (6 non-gore fade).
- Format : PNG (avec alpha) + PSD/Source (ou .xcf). Nommage : `char_<id>_<action>_<size>_<frame>.png` (ex. `char_skul_attack_64_01.png`).
- Palette limitée : 3 couleurs de base + 1 accent.

2) Portraits & icons
- Portraits : 128x128 px (UI), 64x64 pour liste.
- Icons UI : SVG (preferred) + PNG export 32x32, 24x24, 16x16. Naming: `icon_<name>_32.png`.
- States icons (disabled, active) : export distinct ou layered SVG.

3) UI elements
- Buttons : source SVG + PNG 3 scales (1x, 1.5x, 2x).
- Panels/backgrounds : 9-slice / scalable PNG (for in-game windows).
- Fonts : variable or regular TTF/OTF; fallback system sans-serif.
- Color tokens : provide hex + usage (primary, accent, bg, text-primary, text-secondary).

4) Map & arène
- Tilesets : base ground tiles 64x64 (or 128x128 for hi-res). Provide variants for edges.
- Obstacles props : separate PNGs with alpha. Sizes: small (64x64), medium (128x128), large (256x256).
- Decorative layer vs collision layer: provide separate images/masks and collision data (JSON).
- Naming: `map_<arena>_tileset.png`, `map_<arena>_prop_<name>_64.png`.

5) VFX & FX
- Hit sparks : sprite sheet 128x128 frames (transparent).
- Cooldown/ability ring : vector or anim PNG (56x56 base).
- UI transitions: small Lottie or sprite sequences (optional).

6) Audio
- SFX : bite sized (50–500ms) for click, select, ability, hit, score.
- Music : loopable track 90–150 BPM, ambient fantasy.
- Naming: `sfx_<event>_01.wav`, `music_<arena>_loop.mp3`.

7) Export & organisation
- Root folders:
  - `assets/characters/` (sheets + source)
  - `assets/ui/` (icons, buttons, panels)
  - `assets/maps/<arena>/` (tilesets, props, collision json)
  - `assets/sfx/`, `assets/music/`
- Meta files per folder: `manifest.json` listing files, resolutions, usage.

8) Conventions techniques
- Spritesheets optional but prefer single-frame PNGs for easy editing.
- All assets with alpha must be trimmed and accompanied by pivot/anchor metadata (JSON): `{ "pivot": [x,y], "size": [w,h] }`.
- Provide scale variants (1x/2x) for UI to support different resolutions.

9) Priorités de livraison
- Phase 1 (urgent): HUD icons + ability ring, player portrait + 1 character idle/walk, tileset for prototype arena.
- Phase 2: full character animation sets, extra arena props, VFX set.

Notes finales
- Tester chaque icône à 16/24/32px.
- Valider lisibilité personnages à 64px en condition réelle d’arène.

Fichiers de référence à ajouter : `assets/manifest.json`, `docs/wireframes_UI.md` (maquette HUD).