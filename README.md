# Arena Duel

## Présentation

Arena Duel est un jeu desktop Python orienté duel local et LAN.

Le projet combine :

- une interface desktop en CustomTkinter
- un moteur de match en pygame-ce pour la forge locale et le LAN
- une persistance MariaDB pour les joueurs, les joutes et les chroniques
- un mode LAN avec hote autoritaire et clients relies au meme reseau local
- une extension Arduino optionnelle pour LCD I2C / buzzer

## Technologies

- Python
- pygame-ce
- CustomTkinter
- MariaDB Connector/Python
- Pillow
- pyserial en option pour l'integration Arduino
- PyInstaller
- Inno Setup

## Formats de jeu

- 1v1
- 2v2
- 3v3

## Modes d'utilisation

### Forge locale

- partie independante du reseau
- base MariaDB locale du poste
- historique local consultable depuis le launcher
- la forge locale utilise pygame-ce

### Hall LAN hote

- le launcher demarre le serveur LAN integre
- l'hote joue et heberge sur le meme poste
- le hall affiche une vraie invitation LAN IP:port
- l'historique LAN consultable pendant la session provient de l'hote

### Hall LAN client

- le client rejoint l'hote via son invitation LAN
- le client n'ecrit pas directement dans la base de l'hote
- l'historique LAN est demande au serveur de l'hote pendant la session
- le mode local du client reste independant

## Entrees principales

- main.py : launcher principal recommande pour la V1
- main_lan.py : ouverture directe du hall LAN graphique
- run_local.bat : lancement rapide en dev
- run_lan_ui.bat : lancement rapide du hall LAN graphique
- run_client_lan.bat : client CLI de diagnostic seulement

## Build V1

- build_presentation.bat : build canonique de l'exe PyInstaller
- ArenaDuel.spec : spec versionnee de la build
- installer/build.bat : build presentation puis generation du setup si Inno Setup est present

## Structure utile

- ui/ : launcher, forge, hall LAN, historique, theme
- game/ : gameplay local et reseau, arene, audio, HUD
- network/ : serveur LAN, client, protocole et utilitaires d'invitation
- db/ : repositories MariaDB, migration V1 vers V2, registre des joueurs
- hardware/ : pont materiel optionnel, facade hardware et implementation Arduino
- assets/ : backgrounds, icones, sons, sprites, manifests
- docs/ : architecture, installation, soutenance et checklist UI

## Documentation

- INSTALLATION.md : installation et execution sur un nouveau PC
- docs/ARCHITECTURE.md : vue d'ensemble technique du projet
- docs/ARDUINO_INTEGRATION.md : protocole serie et activation du pont Arduino optionnel
- SOUTENANCE_LAN.md : script de demonstration LAN pour la presentation
- MARIADB_V2_PLAN.md : trajectoire de schema et de persistance

## Extension Arduino optionnelle

- le jeu fonctionne integralement sans Arduino
- l'activation se fait dans app_runtime.json
- la dependance serie reste separee dans requirements-arduino.txt
- en cas d'absence de port, de pyserial manquant ou de deconnexion du cable, le jeu continue sans crash
