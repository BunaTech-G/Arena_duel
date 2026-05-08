# Arena Duel Online sur VPS Linux

Ce guide installe le serveur online Arena Duel en service systemd.

## Hypotheses

- Projet deploye dans /opt/arena_duel_clean
- Environnement virtuel dans /opt/arena_duel_clean/.venv
- Utilisateur systeme dedie: arena
- Port public du jeu: 27015/TCP

Le serveur online ecoute en TCP direct sur 0.0.0.0:27015 par defaut.

## Preparation du VPS

Installe les dependances systeme utiles a Python et au package mariadb:

~~~bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip build-essential pkg-config libmariadb-dev
~~~

Crée l'utilisateur systeme si besoin:

~~~bash
sudo useradd --system --create-home --shell /bin/bash arena
~~~

Deploie le projet puis installe les dependances Python:

~~~bash
cd /opt
sudo git clone https://github.com/BunaTech-G/Arena_duel.git arena_duel_clean
sudo chown -R arena:arena /opt/arena_duel_clean
cd /opt/arena_duel_clean
sudo -u arena python3 -m venv .venv
sudo -u arena /opt/arena_duel_clean/.venv/bin/pip install --upgrade pip
sudo -u arena /opt/arena_duel_clean/.venv/bin/pip install -r requirements.txt
~~~

## Installation du service

Le fichier service exemple du depot est dans tools/arena-duel-online.service.

Copie-le vers systemd:

~~~bash
sudo cp /opt/arena_duel_clean/tools/arena-duel-online.service /etc/systemd/system/arena-duel-online.service
~~~

Le service charge aussi optionnellement /etc/default/arena-duel-online pour les variables d'environnement de diagnostic.

Si ton chemin, ton utilisateur ou ton port sont differents, modifie ces lignes dans le service avant activation:

- User=arena
- Group=arena
- WorkingDirectory=/opt/arena_duel_clean
- EnvironmentFile=-/etc/default/arena-duel-online
- ExecStart=/opt/arena_duel_clean/.venv/bin/python -m network.online_server --host 0.0.0.0 --port 27015

Pour activer temporairement le diagnostic de l'annuaire online sans modifier l'unite systemd, cree le fichier d'environnement:

~~~bash
sudo tee /etc/default/arena-duel-online >/dev/null <<'EOF'
ARENA_ONLINE_DIAGNOSTIC_LIST_ROOMS=1
EOF
~~~

Pour revenir au comportement normal, supprime la variable ou mets-la a 0, puis redemarre le service.

Recharge systemd puis active le service:

~~~bash
sudo systemctl daemon-reload
sudo systemctl enable --now arena-duel-online.service
sudo systemctl status arena-duel-online.service
~~~

Suivi des logs:

~~~bash
sudo journalctl -u arena-duel-online.service -f
~~~

Quand le diagnostic est actif, chaque requete LIST_ROOMS ecrit une ligne de log prefixee par ONLINE/LIST_ROOMS avec le detail de chaque room et l'idle de chaque client.

## Firewall

Si UFW est actif:

~~~bash
sudo ufw allow 27015/tcp
sudo ufw status
~~~

Pense aussi a ouvrir le meme port TCP dans le firewall du fournisseur VPS.

## Test rapide

Depuis une machine cliente ou depuis ton poste de dev, tu peux valider le lobby online avec le smoke test du depot:

~~~bash
python tools/test_online_client.py --host TON_IP_VPS --port 27015 --scenario create-join
~~~

Si tu preferes tester l'interface graphique, ouvre ensuite la fenetre online du client, puis renseigne l'IP et le port du VPS dans les champs Serveur et Port avant de te connecter.

## Maintenance

Redemarrer le service:

~~~bash
sudo systemctl restart arena-duel-online.service
~~~

Arreter le service:

~~~bash
sudo systemctl stop arena-duel-online.service
~~~

Desactiver le demarrage automatique:

~~~bash
sudo systemctl disable arena-duel-online.service
~~~

## Notes utiles

- Le bridge hardware est desactive par defaut dans app_runtime.json, ce qui convient a un VPS sans Arduino.
- Si MariaDB n'est pas disponible au demarrage, le jeu degrade proprement la persistence et le serveur peut quand meme rester joignable.
- Si tu veux faire ecouter le service sur un autre port, change le port dans le service systemd et ouvre le meme port cote firewall.
