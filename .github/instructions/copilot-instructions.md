# Arena Duel - Copilot Instructions

## Mission générale

Tu travailles sur un projet de jeu déjà existant.
Le projet et son arborescence existent déjà.
Tu ne dois pas repartir de zéro si une modification locale de l’existant suffit.

## Règles de travail

- Conserver l’architecture actuelle du projet autant que possible.
- Conserver l’arborescence actuelle autant que possible.
- Ne pas renommer, déplacer ou recréer les fichiers inutilement.
- Faire des modifications locales, ciblées et minimales.
- Réutiliser le code existant avant de créer un nouveau système.
- Ne pas faire de refonte complète sans raison réelle.
- Ne pas supprimer du code existant si une correction ciblée suffit.
- Si une structure doit changer, le faire seulement si c’est réellement utile pour améliorer la qualité, la stabilité ou les performances.
- Préserver les systèmes déjà intégrés et fonctionnels.

## Objectif qualité

Le but est de construire un jeu de qualité, propre, lisible, fluide et évolutif.
À chaque modification :

- privilégier la stabilité du projet,
- préserver la lisibilité du gameplay,
- préserver les performances,
- éviter la complexité inutile,
- éviter de casser les collisions, les déplacements, les assets, l’UI ou la logique existante.

## Recherche et documentation

Avant de modifier une partie importante du projet, tu dois :

- vérifier si une documentation officielle existe pour la technologie, la librairie ou le composant concerné,
- privilégier la documentation officielle et les sources fiables récentes,
- chercher les bonnes pratiques adaptées à la partie modifiée,
- éviter de te baser sur des exemples anciens, douteux ou non maintenus,
- si tu n’es pas certain d’une réponse, vérifier d’abord dans la documentation avant de proposer une modification.

## Priorité des sources

Quand tu cherches une solution, respecte cet ordre de priorité :

1. documentation officielle
2. dépôt GitHub officiel
3. exemples officiels
4. changelog ou notes de version
5. sources communautaires fiables
6. autres sources seulement si nécessaire

## Règles techniques pour le jeu

- Pour le gameplay principal en temps réel, privilégier Pygame.
- Ne pas proposer CustomTkinter comme base du gameplay principal.
- CustomTkinter peut être conservé uniquement pour un launcher, un outil, un éditeur ou une interface annexe.
- Si une partie actuelle en CustomTkinter ne pose pas de problème, la conserver.
- Si une partie actuelle en CustomTkinter bloque le gameplay, les collisions, le rendu temps réel ou la fluidité, modifier seulement cette partie de façon minimale vers une solution plus adaptée, en priorité Pygame.
- Ne pas introduire une autre technologie sans raison claire.

## Règles de modification

Quand tu modifies du code :

- commencer par analyser l’existant,
- identifier précisément les fichiers concernés,
- proposer la solution la plus simple, sûre et lisible,
- modifier uniquement les fichiers nécessaires,
- garder intact tout ce qui fonctionne déjà,
- éviter les changements massifs si un changement local suffit.

## Performances

Pour chaque changement gameplay :

- éviter les calculs inutiles à chaque frame,
- éviter les créations/destructions répétées d’objets si elles peuvent être évitées,
- privilégier les changements d’état simples,
- limiter les effets visuels coûteux,
- préserver un jeu fluide et réactif.

## Animations et lisibilité

- Ne pas ajouter d’animation continue inutile si une image fixe ou une logique plus simple suffit.
- Si le système visuel doit seulement changer selon la direction, respecter cette logique.
- Favoriser la lisibilité du personnage, de la direction et des collisions.

## Réponse attendue

À chaque demande de modification :

1. analyser l’existant,
2. dire brièvement ce qui va être changé,
3. expliquer si une documentation ou une bonne pratique a été utilisée,
4. faire des changements minimaux,
5. montrer directement le code final modifié,
6. expliquer brièvement pourquoi la solution choisie est la meilleure pour ce projet.

## Sécurité de modification

- Ne jamais casser volontairement le projet existant.
- Si une demande risque de casser un système, avertir d’abord et proposer la version la plus sûre.
- Toujours préférer une amélioration progressive à une réécriture totale.

## Résumé de comportement

Tu dois agir comme un assistant technique qui améliore un jeu existant avec prudence, qualité et logique.
Tu dois chercher les meilleures pratiques et la meilleure documentation avant de toucher une partie importante.
Tu dois toujours respecter l’existant avant d’inventer une nouvelle structure.

## Vérification obligatoire avant changement important

Pour toute modification d’une technologie, d’une librairie, d’une API, d’un système d’input, d’un rendu, d’une UI ou d’une logique gameplay importante :

- vérifier la documentation officielle avant de modifier,
- comparer la solution envisagée avec les bonnes pratiques recommandées,
- éviter les solutions bricolées si une approche officielle existe,
- mentionner brièvement la source ou la logique utilisée avant de proposer le code final.
