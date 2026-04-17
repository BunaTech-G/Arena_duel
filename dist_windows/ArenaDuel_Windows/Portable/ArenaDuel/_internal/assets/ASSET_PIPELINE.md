# Arena Duel Asset Pipeline

This folder now contains the base structure required to move Arena Duel from prototype visuals to a maintainable fantasy arena pipeline.

## Current goals

- keep the existing game functional
- prepare clean hooks for maps, sprites, portraits and UI art
- allow placeholder visuals now and final assets later
- avoid hardcoded one-off file lookups in future refactors

## Directory layout

assets/
  icons/
  fonts/
  sounds/
  ui/
  maps/
    forgotten_sanctum/
  sprites/
    skeleton_mascot/
  portraits/
  backgrounds/
  prompts/

## What is ready now

- asset registry file: assets/asset_manifest.json
- background registry file: assets/backgrounds/manifest.json
- map data seed: assets/maps/forgotten_sanctum/layout.json
- sprite contract seed: assets/sprites/skeleton_mascot/manifest.json
- art briefs: assets/prompts/ASSET_BRIEFS.md
- loader hooks: game/asset_pipeline.py
- working preview PNGs for floor, portrait and skeleton idle/walk frames

## How future phases should use this

1. Load asset metadata from game/asset_pipeline.py instead of scattering file names.
2. Read map obstacle data from JSON before replacing hardcoded arena rectangles.
3. Read sprite animation frame lists from the sprite manifest before integrating animation states.
4. Replace placeholder files without changing the code-facing relative paths.
5. Keep preview assets replaceable by preserving their ids in the manifests.

## Placeholder strategy

The project does not yet ship final sprite sheets or final painted backgrounds.
Until those arrive, the pipeline uses:

- JSON manifests for structure
- starter generated PNG assets for immediate runtime integration
- procedural pygame surfaces as safe fallback placeholders when files are missing
- explicit expected filenames for future replacement

## Files intended to be replaced later

- assets/icons/icon_skeleton_mascot.png
- assets/backgrounds/launcher_sanctum_bg.png
- assets/backgrounds/arena_forgotten_sanctum_floor.png
- assets/portraits/skeleton_mascot_portrait.png
- all files listed in assets/sprites/skeleton_mascot/manifest.json
- all files listed under ui_assets in assets/asset_manifest.json

## Packaging note

PyInstaller already collects the whole assets directory, so these new paths are compatible with the existing build strategy.