# Arena Duel - Copilot Rules

## Mission

Assist on Arena Duel by working from the existing project, the current structure, and the code already in place.

## Existing project first

- Preserve the current architecture and tree whenever possible.
- Never restart from zero if a local fix on the existing code is enough.
- Do not rename, move, recreate, or delete files unless it is genuinely necessary.
- Reuse existing systems, helpers, assets, and logic before creating anything new.
- Do not replace a working system only to make it look cleaner.

## Change strategy

- Start by analyzing the existing code and identifying the exact files and systems involved.
- Keep everything that already works.
- Make targeted, local, minimal edits.
- Avoid full rewrites and broad refactors unless the user explicitly asks for them.
- If a structural or technical change is required, keep it minimal, coherent, and justified.

## Technical choices

- Keep the existing Pygame runtime intact unless a specific gameplay component is explicitly targeted for change.
- For new real-time gameplay work or isolated gameplay migrations requested by the user, prefer Arcade over introducing more UI-driven solutions.
- Do not attempt a full Pygame-to-Arcade rewrite unless the user explicitly asks for that migration scope.
- Do not introduce CustomTkinter as the base for the core gameplay loop.
- CustomTkinter is acceptable for the launcher, secondary interfaces, tools, or editors.
- If an existing CustomTkinter area does not interfere with rendering, collisions, movement, or responsiveness, keep it.
- If a CustomTkinter component blocks or complicates real-time gameplay, change only that component and prefer a minimal migration toward Arcade.
- Do not introduce another technology without a concrete reason.

## Gameplay safety

- Never break movement, collisions, asset references, direction handling, or scene integration.
- Favor responsive controls and clear direction handling.
- If a system uses fixed directional sprites, do not introduce continuous animation unless explicitly requested.
- Keep combat, pickup logic, and runtime state changes lightweight and readable.

## Performance

- Avoid heavy logic in update/process loops.
- Avoid repeated allocations every frame.
- Prefer cached references and state-based updates.
- Do not add expensive visual effects unless explicitly requested.

## Code changes

- Show only the necessary code changes.
- Explain briefly what changed and why.
- Warn before any risky change and propose the safest version first.
