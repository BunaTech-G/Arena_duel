Wireframes UI — Arena Duel

Objectif : maquettes claires et actionnables pour l'équipe technique et artistique.

1) HUD principal (en jeu)
- Timer : centre-haut, grand, contraste élevé. Taille visuelle recommandée : 48–64px.
- Scores : coin sup gauche (équipe A), coin sup droite (équipe B). Icône d'équipe + chiffre (32–36px).
- Barre de compétences : bas-centre. Icônes circulaires 56x56 px, anneau de cooldown 3–4px.
- Portrait joueur : bas-gauche. Sprite 64px haute, barre PV 120x12 px au-dessus/à côté.
- Mini-map / indicateurs : bas-droite, carré 140x140 px (optionnel selon arène).
- Notifications / événements : zone supérieure-centre sous le timer (bande 720x40 px), text-limit 1 ligne.

Disposition (schéma simplifié)

[ TOP ]
   [ Score A ]        [   TIMER (48-64px)   ]         [ Score B ]

[ centre de l'écran : arène ]

[ BOTTOM ]
[ Portrait ]                        [ Abilities (icônes circulaires) ]            [ Mini-map ]

Notes :
- Espacements réguliers (gutter 12–16px).
- Cibles interactives min 44x44 px.
- Texte UI base 14–16px, labels secondaires 12–13px.

2) Fenêtre de menu / inventaire / statistiques
- Header : titre + action principale (close/apply) à droite.
- Colonne gauche : avatar + stats clefs (level, HP, énergie, score).
- Corps : onglets (Inventory / Skills / Match Log) avec cartes remplies.
- Footer : actions contextuelles (equip, upgrade, back).
- Remplir l’espace : utiliser cartes/rows, éviter grands blancs.

3) Écran de sélection de personnage
- Grille 3x2 de slots (surtout lisible), chaque slot : portrait 128px, nom, rôle, short-stats.
- Preview large à droite : sprite 256px + actions/description.
- Boutons : Select (accent), Back.

4) Écran de pause / scoreboard
- Panel central semi-opaque, tableau clair (team | kills | deaths | ping).
- Bouton resume prominent, leave smaller.

5) Style & interactions (résumé)
- States : hover, pressed, disabled — contrastes nets.
- Tooltips : apparaissent après 250ms hover, texte max 2 lignes.
- Animations UI : micro-transitions 120–180ms (fade/scale) pour feedback, pas d’effets lourds.

Fichiers conseillés à créer/éditer :
- `ui/hud_panels.py` : implémenter layout HUD selon positions ci-dessus.
- `ui/theme.py` : tokens couleurs/typos.
- `ui/launcher.py`, `ui/player_select.py` : appliquer wireframes menus.

Livrable attendu : maquette PNG/SVG du HUD + notes d’implémentation (positions, tailles, assets requis).