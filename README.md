# Arena Duel

## Présentation
Arena Duel est un jeu local multijoueur développé en Python.

Le projet combine :
- une interface desktop en CustomTkinter
- un moteur de jeu en pygame-ce
- une base de données MariaDB
- phpMyAdmin via XAMPP pour l’administration des données

## Technologies
- Python
- pygame-ce
- CustomTkinter
- MariaDB Connector/Python
- XAMPP / phpMyAdmin
- Git / GitHub

## Formats de jeu
- 1v1
- 2v2
- 3v3

## Modes d'utilisation

### Mode local
- partie indépendante du réseau
- base MariaDB locale du poste
- historique local consultable depuis le launcher

### Mode LAN hôte
- le launcher démarre le serveur LAN intégré
- l'hôte joue et héberge sur le même poste
- la base MariaDB de l'hôte reste la source de vérité
- l'historique LAN consulté pendant la session provient de l'hôte

### Mode LAN client
- le client rejoint l'hôte via son IP
- le client n'écrit pas directement dans la base MariaDB de l'hôte
- l'historique LAN est demandé au serveur de l'hôte pendant la session
- le mode local du client reste indépendant

## Lancer le projet
```bash
python main.py