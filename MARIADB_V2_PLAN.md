# MariaDB V2 Plan

## Objectif

Le projet dispose deja d'un domaine riche dans le runtime, mais la base ne retient qu'un sous-ensemble minimal des informations. Le but de la V2 est d'ajouter une vraie memoire applicative sans casser les flux actuels.

La cible couvre quatre axes :

- archives de match plus riches ;
- persistance propre des participants IA ;
- memoire du LAN avec salons et etats prets ;
- preferences et statistiques exploitables par l'interface.

Le schema cible est dans [schema_v2.sql](schema_v2.sql).
La migration incrementale depuis le schema legacy est dans [db/migrations/001_v1_to_v2.sql](db/migrations/001_v1_to_v2.sql).

## Ce Que Le Schema Couvre

### Tables coeur

- `players` : identites humaines durables.
- `arenas` : cartes jouables et version de layout.
- `matches` : joutes archivees, avec mode, source, carte et session LAN eventuelle.
- `match_players` : instantane des participants, humains ou IA, avec score individuel.

### Tables de contexte

- `player_preferences` : dernier camp, dernier slot et derniers choix de forge.
- `lobby_sessions` : salons LAN, code d'invitation, duree, statut.
- `lobby_members` : membres du salon, slot, equipe, readiness.

### Vues

- `v_match_history_cards` : vue compacte pour remplacer a terme la reconstruction manuelle de l'historique.
- `v_player_career_stats` : statistiques par joueur.
- `v_team_career_stats` : performances globales des bastions.

## Mapping Code Vers Tables

| Zone du code | Donnees produites | Table cible |
| --- | --- | --- |
| [game/game_window.py](game/game_window.py#L282) | `players_data`, `winner_team`, `duration_seconds` | `matches`, `match_players` |
| [ui/player_select.py](ui/player_select.py#L1640) | sauvegarde locale en fin de joute | service d'archivage unifie |
| [network/server.py](network/server.py#L366) | resultat LAN, `winner_team`, scores, participants | `matches`, `match_players` |
| [network/server.py](network/server.py#L42) | lobby, slots, ready, duree | `lobby_sessions`, `lobby_members` |
| [game/arena_layout.py](game/arena_layout.py#L10) | `map_id` et metadata de layout | `arenas`, `matches.arena_id` |
| [db/players.py](db/players.py#L6) | registre joueurs | `players`, `player_preferences` |
| [ui/history_view.py](ui/history_view.py#L556) | lecture historique | `v_match_history_cards` ou adaptateur Python |

## Strategie D'Integration

### Phase 1

Creer la nouvelle structure SQL sans modifier le runtime.

- charger [schema_v2.sql](schema_v2.sql) dans une base de test ;
- garder [shema.sql](shema.sql#L1) comme bootstrap legacy tant que le code n'a pas bascule ;
- ne rien changer aux ecritures actuelles dans l'immediat.

### Phase 2

Unifier les ecritures locale et LAN derriere un service unique.

- extraire un depot unique, par exemple `db/match_repository.py` ;
- faire converger [db/matches.py](db/matches.py#L32) et [db/network_match_repository.py](db/network_match_repository.py#L21) ;
- accepter des payloads plus riches : `mode_code`, `source_code`, `arena_id`, `lobby_session_id`, `control_mode`, `is_ai`.

### Phase 3

Brancher les producteurs de metadonnees deja disponibles.

- local : enrichir le payload construit dans [game/game_window.py](game/game_window.py#L282) avec `slot_number` et `ai_difficulty_code` ;
- LAN : enrichir [network/server.py](network/server.py#L397) avec `map_id`, `client_id_snapshot` et `ready_at_start` ;
- forge : memoriser les preferences depuis [ui/player_select.py](ui/player_select.py#L1604).

### Phase 4

Faire evoluer les lectures UI.

- remplacer la reconstruction manuelle de [db/matches.py](db/matches.py#L171) par une lecture de `v_match_history_cards` ;
- brancher `v_player_career_stats` dans [ui/history_view.py](ui/history_view.py#L556) pour afficher des resumes plus solides ;
- garder la degradation propre quand la base est indisponible, comme aujourd'hui dans [db/database.py](db/database.py#L1).

## Migration Depuis La Base Actuelle

La migration la plus sure est en deux temps.

### Etape 1

Backfill de reference.

- inserer l'arene `forgotten_sanctum` dans `arenas` ;
- recopier les joueurs existants tels quels dans `players` si la base cible est vide.

### Etape 2

Backfill des matches existants.

- recopier `matches` vers la nouvelle structure avec `mode_code = 'LEGACY'`, `source_code = 'LEGACY'`, `status_code = 'COMPLETED'` ;
- remplir `match_players.display_name_snapshot` a partir de `players.username` ;
- laisser `player_id` a `NULL` uniquement pour les futurs participants IA ;
- mettre `arena_code_snapshot = 'forgotten_sanctum'` pour l'historique existant si aucune carte historique n'est connue.

## Decisions Importantes

- Les IA ne doivent plus etre identifiees seulement par le prefixe `[IA]`. La source de verite doit devenir `match_players.is_ai`.
- Les vues de stats sont preferees a des tables d'agregation dans un premier temps. Cela limite le risque fonctionnel.
- Le LAN doit d'abord persister le salon et son roster, puis la joute. Le runtime expose deja ces donnees dans [network/server.py](network/server.py#L42).
- Le comportement hors ligne de la base ne doit pas regresser. Les vues UI doivent continuer a s'ouvrir meme si MariaDB ne repond pas.

## Priorite Recommandee

1. Mettre en place la V2 SQL en parallele de l'existant.
2. Unifier les ecritures de match locale et LAN.
3. Basculer l'historique sur une vue SQL compatible.
4. Ajouter les preferences joueur.
5. Persister les salons LAN.
