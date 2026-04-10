# Architecture Arena Duel

## Vue d'ensemble

Arena Duel est organise autour d'un launcher desktop unique qui ouvre deux
grandes familles d'usage :

- forge locale : partie et historique du poste local
- hall LAN : hote autoritaire et clients relies au meme reseau local

## Points d'entree

- main.py : entree principale recommande pour la presentation V1
- main_lan.py : ouverture directe du hall LAN graphique
- network/server.py : serveur LAN CLI pour test bas niveau
- network/client.py : client LAN CLI de diagnostic

## Groupes logiques

### UI desktop

- ui/launcher.py : ecran d'accueil et orchestration globale
- ui/player_select.py : forge locale, enrôlement et validation de joute
- ui/network_lobby.py : hall LAN, invitation, roster, pret et historique
- ui/history_view.py : chroniques locales ou LAN
- ui/theme.py : palette, typographie et composants visuels partages

### Gameplay pygame

- game/game_window.py : boucle de match local
- game/net_match_window.py : boucle de match reseau
- game/arena.py et game/arena_layout.py : rendu et geographie de l'arene
- game/computer_opponent.py : adversaire local contre l'ordinateur
- game/audio.py : sons, musiques et fallbacks de lecture

### Reseau LAN

- network/server.py : serveur TCP autoritaire, lobby et demarrage des matchs
- network/client.py : client TCP et envoi des intentions de jeu
- network/net_utils.py : invitation LAN, detection IP, erreurs normalisees
- network/messages.py et network/protocol.py : messages et encodage

### Donnees

- db/database.py : connexion MariaDB et test de disponibilite
- db/players.py : registre des combattants
- db/match_repository.py : source de verite pour persistance et historique
- db/lobby_repository.py : sessions LAN et membres du hall
- db/migrations/001_v1_to_v2.sql : migration incrementale V1 vers V2

## Fichiers de configuration

- app_runtime.json : configuration runtime partagee (DB, bind LAN, port)
- client_lan_config.json : dernier hall LAN memorise pour un utilisateur
- runtime_utils.py : resolution des chemins en source et en build

## Build et livraison V1

- build_presentation.bat : script canonique pour produire l'exe PyInstaller
- ArenaDuel.spec : spec PyInstaller versionnee pour la build V1
- installer/arena_duel.iss : installateur Inno Setup base sur dist_release

## Regles de structure V1

- les dossiers build_release* et dist_release* sont des sorties generees
- la logique LAN et la logique locale restent separees dans les vues UI
- les fichiers SQL historiques sont gardes pour compatibilite, mais le point
  de reference V2 reste schema_v2.sql avec migration dans db/migrations