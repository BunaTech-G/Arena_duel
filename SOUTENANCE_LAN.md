# Soutenance LAN - Arena Duel

Ce document sert de script de démonstration pour présenter la version finale LAN de Arena Duel.

## Objectif de la démo

Montrer clairement que l'application gère deux usages distincts sans ambiguïté :

- un mode local indépendant
- un mode LAN hôte / client cohérent

Le message produit à faire passer pendant la soutenance est simple :

- le mode local reste autonome
- le mode LAN repose sur un hôte qui fait autorité
- les clients LAN rejoignent simplement l'hôte
- l'historique LAN consulté pendant la session provient de l'hôte

## Préparation avant la soutenance

### Poste hôte

- vérifier que MariaDB est lancé sur le poste hôte
- vérifier que la base `arena_duel_v2_db` existe
- lancer Arena Duel depuis le launcher principal
- vérifier que le son fonctionne
- vérifier que le pare-feu Windows autorise l'application si nécessaire

### Poste client

- lancer Arena Duel sur le poste client
- vérifier que le client est sur le même réseau local
- noter l'adresse IP affichée par le poste hôte une fois le serveur LAN démarré
- ne pas lancer de serveur sur le poste client

### Matériel conseillé

- 2 PC sur le même LAN
- souris et clavier disponibles sur les deux postes
- XAMPP déjà lancé sur le host si la base MariaDB est présentée en direct

## Message d'architecture à dire pendant la présentation

Formulation courte recommandée :

"L'application garde un mode local totalement indépendant. En LAN, l'hôte démarre le serveur intégré, joue en même temps que les autres, pilote l'état du match et reste la source de vérité pour la sauvegarde et l'historique réseau. Les clients rejoignent simplement l'hôte et consultent son historique pendant la session, sans devoir se comporter comme un serveur MariaDB."

## Déroulé soutenance - version courte 5 à 7 minutes

### 0:00 - 0:45

Présenter le launcher principal.

À montrer :

- un seul point d'entrée : `main.py`
- les trois usages visibles : local, héberger, rejoindre
- l'état MariaDB et l'état du serveur LAN

À dire :

- "J'ai gardé un launcher unique pour éviter de séparer artificiellement le produit."
- "Le mode local et le mode LAN partagent la même application mais pas la même logique métier."

### 0:45 - 1:30

Montrer le mode local sans lancer une vraie partie complète.

À montrer :

- ouverture du mode local
- sélection des joueurs
- historique local depuis le launcher

À dire :

- "Le mode local reste intact et continue à utiliser la base locale du poste."
- "Je n'ai pas cassé l'existant pour ajouter le LAN final."

### 1:30 - 2:30

Passer au mode hôte LAN sur le poste serveur.

À montrer :

- clic sur `Héberger une partie LAN`
- démarrage automatique du serveur intégré
- IP et port affichés clairement
- connexion du joueur hôte dans le lobby

À dire :

- "L'hébergement est autonome depuis le launcher, il n'y a plus besoin de lancer manuellement le serveur avant."
- "L'hôte peut héberger et jouer sur le même poste."

### 2:30 - 3:30

Sur le poste client, rejoindre la partie.

À montrer :

- clic sur `Rejoindre une partie LAN`
- saisie de l'IP du host
- connexion du client au lobby
- affichage du mode courant et de la source de l'historique

À dire :

- "Le client LAN n'est pas traité comme un serveur."
- "Il rejoint simplement l'hôte et récupère les données réseau utiles via TCP."

### 3:30 - 4:15

Montrer l'historique LAN depuis le lobby client ou host.

À montrer :

- bouton `Voir l'historique LAN`
- affichage d'une fenêtre d'historique indiquant sa source

À dire :

- "L'historique consulté en session LAN vient du host."
- "On évite ainsi les incohérences entre historique local du client et historique de la partie hébergée."

### 4:15 - 5:30

Lancer une partie LAN courte.

À montrer :

- deux joueurs passent en prêt
- démarrage automatique du match
- jeu en temps réel sur les deux machines
- fin de match et retour automatique au lobby

À dire :

- "Quand tous les joueurs sont prêts, le match démarre automatiquement."
- "L'état du match est piloté par l'hôte, puis tout le monde revient proprement au lobby à la fin."

### 5:30 - 6:15

Montrer le retour au lobby et la confirmation de sauvegarde.

À montrer :

- message de retour au lobby
- indication que l'historique LAN a été sauvegardé ou message clair d'erreur si la base est indisponible
- consultation immédiate de l'historique LAN

À dire :

- "La sauvegarde est centralisée côté host."
- "Si la base n'est pas disponible, l'erreur est visible, on n'a pas un faux succès silencieux."

### 6:15 - 7:00

Conclure sur la robustesse.

À dire :

- "Le mode local est préservé."
- "Le flux LAN final est cohérent : accueil, hébergement, connexion, lobby, ready, match, fin, retour lobby, historique."
- "Le packaging Windows embarque les assets, les sons, l'icône et la configuration runtime."

## Version très courte 2 à 3 minutes

Si le temps est limité, suivre ce script :

1. Ouvrir le launcher et montrer les trois entrées.
2. Héberger une partie LAN depuis le poste host.
3. Rejoindre avec un poste client.
4. Montrer l'historique LAN côté client.
5. Lancer un match très court déjà prêt à être montré.
6. Montrer le retour lobby et la sauvegarde centralisée côté host.

Phrase de conclusion recommandée :

"La valeur du projet n'est pas seulement d'avoir un mode réseau, mais d'avoir un mode LAN propre où les rôles host et client sont clairs, où le local reste intact, et où la démonstration produit reste stable et compréhensible."

## Démo technique détaillée - points à souligner

### Séparation local / LAN

- le mode local continue à lire et écrire localement comme avant
- le mode LAN n'impose pas au client une base MariaDB distante
- le launcher garde un comportement lisible pour les deux usages

### Rôle de l'hôte

- démarre le serveur LAN intégré
- joue en même temps qu'il héberge
- conserve la vérité sur l'état du match
- centralise la sauvegarde du résultat
- expose l'historique LAN aux clients pendant la session

### Rôle du client

- rejoint via IP
- reçoit les états réseau
- participe au lobby et au match
- consulte l'historique du host sans changer sa logique locale permanente

## Checklist juste avant de passer à l'oral

- lancer le host une première fois pour vérifier son IP LAN
- vérifier qu'au moins un match existe déjà dans l'historique
- vérifier que les sons sont actifs
- vérifier qu'un client peut se connecter au lobby
- vérifier que le retour lobby après match fonctionne
- vérifier que le bouton d'historique LAN répond
- fermer les fenêtres inutiles sur le bureau

## Plan B si un imprévu survient

### Cas 1 - MariaDB du host ne démarre pas

Montrer quand même :

- le launcher
- l'hébergement LAN
- la connexion client
- le lobby
- le démarrage du match

À dire :

- "Le gameplay LAN et la synchronisation réseau restent démontrables. La couche de persistance signale maintenant explicitement si la base n'est pas disponible."

### Cas 2 - Le client ne peut pas rejoindre

Plan de secours :

- utiliser `127.0.0.1` sur le poste host pour montrer le flux LAN intégré
- montrer que le serveur est démarré depuis le launcher
- expliquer que le port et l'IP sont configurables par runtime

### Cas 3 - Temps très court

Faire uniquement :

- launcher
- héberger
- connecter le host
- montrer l'historique LAN
- montrer le packaging prêt pour l'EXE

## Questions probables du jury et réponses courtes

### "Pourquoi garder le mode local séparé ?"

"Parce qu'il répond à un usage différent et qu'il devait rester stable. J'ai choisi une amélioration à faible risque plutôt qu'une fusion artificielle qui aurait créé des régressions."

### "Pourquoi le client LAN ne se connecte pas directement à MariaDB ?"

"Parce que cela rendrait la démonstration fragile, dépendante d'une exposition réseau de la base, et brouillerait le rôle du client. Le client récupère ce dont il a besoin via le protocole LAN, l'hôte restant la source de vérité."

### "Comment gérez-vous la fin de partie ?"

"Le match renvoie proprement au lobby, réactive l'interface, conserve les sons et remonte explicitement le statut de sauvegarde de l'historique."

### "Qu'avez-vous sécurisé pour le packaging ?"

"Les assets, les sons, l'icône et la configuration runtime sont embarqués dans la build. Le comportement reste cohérent entre source et EXE."

## Ordre conseillé d'ouverture des fenêtres pendant la démo

1. Launcher host
2. Lobby host
3. Launcher client
4. Lobby client
5. Match
6. Historique LAN

## Résultat attendu en fin de soutenance

Le jury doit retenir trois choses :

- le mode local n'a pas été cassé
- le mode LAN final a une logique claire host / client
- le projet est assez propre et robuste pour être présenté comme une version finale démontrable