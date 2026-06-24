# Arena Duel

Release: v1.0.0 — téléchargements et installateur disponibles sur GitHub Releases
: https://github.com/on2-511/Arena_duel/releases/tag/v1.0.0

## Resume

Arena Duel est un jeu desktop Python avec interface CustomTkinter et combats pygame-ce.
Le projet propose une forge locale, un hall LAN (hote/client) et une base MariaDB
optionnelle pour l'historique des joutes.

## Lancement rapide

### Recommande

- Lance `run_local.bat`.
- Le script prepare automatiquement l'environnement Python si necessaire.
- Il verifie puis installe les dependances manquantes avant de demarrer le jeu.

### Important

- Sur un nouveau PC, evite `python main.py` directement.
- Utilise `run_local.bat` pour eviter les erreurs de dependances
  (`customtkinter`, `pygame-ce`, `Pillow`, etc.).

## Modes disponibles

### Local

- Partie hors reseau.
- Compatible sans connexion Internet.

### LAN - Heberger

- Lance un hall LAN local et ouvre une invitation IP:port.
- Les autres postes du meme reseau peuvent rejoindre.

### LAN - Rejoindre

- Rejoint un hall LAN via l'invitation de l'hote.

### Online (prototype)

- Mode online TCP present pour les tests reseau.

## Scripts utiles

- `run_local.bat` : lancer le jeu en mode source.
- `run_lan_ui.bat` : ouvrir directement le hall LAN graphique.
- `build_exe_quick.bat` : generer rapidement l'EXE.
- `build_presentation.bat` : build canonique PyInstaller.
- `build_windows_release.bat` : pack Windows complet (portable + zip + setup si dispo).

## Build EXE

- EXE de sortie : `dist_release/ArenaDuel/ArenaDuel.exe`.
- Le build embarque les assets necessaires au lancement.

## Stack technique

- Python
- CustomTkinter
- pygame-ce
- Pillow
- MariaDB Connector/Python
- PyInstaller
- Inno Setup

## Arborescence principale

- `ui/` : launcher et interfaces.
- `game/` : gameplay et boucle de joute.
- `network/` : client/serveur LAN et protocole.
- `db/` : persistance et repositories.
- `assets/` : icones, sons, sprites, fonds.

## Documentation

- `INSTALLATION.md`
- `docs/ARCHITECTURE.md`
- `docs/ARDUINO_INTEGRATION.md`
- `SOUTENANCE_LAN.md`
