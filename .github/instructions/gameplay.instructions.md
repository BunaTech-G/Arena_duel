---
applyTo: "game/**/*.py"
---

# Règles gameplay Arena Duel

- Travailler à partir du gameplay Python existant sans refonte complète.
- Conserver les assets, collisions, déplacements, logique de direction et intégrations déjà en place.
- Pour un nouveau composant de gameplay temps réel ou une migration locale explicitement demandée, privilégier Arcade.
- Ne pas déplacer le coeur du gameplay vers CustomTkinter.
- Si un composant UI gêne le rendu temps réel ou la fluidité, corriger uniquement ce composant avec la migration minimale nécessaire.
- Ne jamais introduire de logique lourde dans la boucle principale sans justification.
- Éviter les allocations répétées à chaque frame.
- Préserver la réactivité des contrôles.
- Préférer les changements d’état simples aux systèmes trop complexes.
- Ne pas lancer d’animation continue si une frame fixe par direction suffit.
