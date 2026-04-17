# Skeleton Duo Fighters

Sprite package for two collectible skeleton arena fighters.

## Intended files

- `skeleton_fighter_ember_sheet.png`
- `skeleton_fighter_aether_sheet.png`
- `skeleton_duo_master_sheet.png`
- `manifest.json`

## Sheet layout

- frame size: `64x64`
- directions per character: `front`, `back`, `left`, `right`
- walking frames per direction: `4`
- row order: `front`, `back`, `left`, `right`
- column order: `walk_0`, `walk_1`, `walk_2`, `walk_3`
- anchor: `center_bottom`

## Character roles

- `ember`: agile duelist, warm gold/orange accent, lighter silhouette
- `aether`: sturdy guardian, cool cyan accent, broader silhouette

## Current state

- `source/Perso.png` is now the canonical raw drop used to build `skeleton_duo_master_sheet.png`
- detected format: transparent `PNG`, `1024x1024`
- automatic alpha scan suggests 4 large horizontal bands and multiple animation columns
- exact slicing still needs visual confirmation before runtime extraction
- automatic extraction has now been generated in `extracted/perso_auto`
- normalized frame size: `219x254`
- extracted naming: `row01_col01.png` through `row04_col05.png`
- preview sheet: `extracted/perso_auto/atlas_preview.png`

## Integration note

The naming is now stable enough for future runtime integration. Keep `skeleton_duo_master_sheet.png` as the canonical imported sheet unless you intentionally replace it with a better export.
