# Intégration Arduino optionnelle

## Principe

Le support Arduino est un bonus matériel facultatif.

- si le support est désactivé, le jeu ne fait rien de plus
- si aucun Arduino n'est trouvé, le jeu continue normalement
- si `pyserial` n'est pas installé, le jeu continue normalement
- si la liaison série tombe en cours de partie, le jeu continue normalement

Le gameplay ne parle jamais directement au port série.
Il émet uniquement des événements de match via `MatchHardwareService`.

## Architecture

- `hardware/service.py` : façade utilisée par le jeu
- `hardware/bridge.py` : abstraction runtime + bridge no-op
- `hardware/arduino.py` : implémentation série Arduino optionnelle
- `docs/arduino/ArenaDuelArduinoV1.ino` : sketch Arduino V1 prêt à téléverser

## Protocole série V1

Messages texte envoyés ligne par ligne :

- `RESET`
- `STATE:LOBBY`
- `STATE:COMBAT`
- `STATE:RESULT`
- `SCORE:x,y`
- `WINNER:A`
- `WINNER:B`
- `WINNER:DRAW`

## Configuration runtime

Dans `app_runtime.json` :

```json
{
  "hardware_bridge_enabled": false,
  "hardware_bridge_backend": "arduino",
  "hardware_serial_port": "",
  "hardware_serial_auto_detect": true,
  "hardware_serial_baudrate": 115200,
  "hardware_serial_timeout_seconds": 0.2,
  "hardware_serial_write_timeout_seconds": 0.2
}
```

## Activation

1. Installer l'option série : `pip install -r requirements-arduino.txt`
2. Activer `hardware_bridge_enabled`
3. Laisser l'auto-détection active ou renseigner `hardware_serial_port`
4. Lancer le jeu normalement

## Sketch V1 fourni

Le sketch V1 se trouve dans `docs/arduino/ArenaDuelArduinoV1.ino`.

Hypothèses matérielles actuelles :

- LCD I2C 16x2 à l'adresse `0x27`
- LED de statut sur D7
- buzzer sur D8
- vitesse série `115200`

Bibliothèque Arduino requise :

- `LiquidCrystal_I2C`

## Comportement de fallback

- support désactivé : bridge no-op
- backend inconnu : bridge no-op
- pyserial absent : bridge no-op + log explicite
- port non détecté : bridge no-op + log explicite
- ouverture série impossible : bridge no-op + log explicite
- erreur en cours d'écriture : bridge Arduino désactivé proprement pour le reste de la session

## Logs

Les logs matériels sont écrits dans le dossier utilisateur runtime :

- `arena_duel_hardware.log`
