# Arena Duel - Dossier de projet

## Introduction

Arena Duel est un projet de jeu desktop developpe en Python. L'application
propose deux usages complementaires :

1. un mode local, appele forge locale, pour lancer des joutes sur un seul
   poste ;
2. un mode LAN, dans lequel un poste hote ouvre un hall reseau et des clients
   rejoignent la partie sur le meme reseau local.

Le projet s'appuie sur une interface graphique desktop, un moteur de match,
une persistance de donnees pour l'historique des parties, ainsi qu'une
extension Arduino optionnelle destinee a enrichir la demonstration.

Ce dossier a un double objectif :

1. expliquer clairement l'architecture et le fonctionnement du projet ;
2. fournir une procedure d'installation, de configuration et de lancement
   suffisamment detaillee pour servir de support devant un professeur.

Important : le projet existe aujourd'hui sous deux formes d'exploitation.

1. Une installation complete, avec XAMPP, MariaDB et phpMyAdmin, qui permet de
   montrer la vraie couche de persistance du projet.
2. Une version de demonstration packagée, sous forme d'executable Windows,
   preparee pour l'oral et capable de fonctionner sans Python, sans XAMPP et
   sans MariaDB grace a un stockage local de demonstration.

Ce document commence volontairement par l'installation complete avec XAMPP,
puis presente la version de demonstration autonome actuellement livree.

[Capture a inserer ici : vue d'ensemble du projet ou ecran principal du launcher]

---

## 1. Presentation du projet

Arena Duel est un jeu de duel en arene oriente presentation desktop. Le projet
repose sur un launcher principal qui centralise les usages suivants :

1. ouvrir la forge locale ;
2. ouvrir un hall LAN sur le poste hote ;
3. rejoindre un hall LAN depuis un poste client ;
4. consulter les chroniques, c'est-a-dire l'historique des joutes archivees.

L'application est construite autour d'une logique claire :

1. le launcher sert de point d'entree unique ;
2. le mode local permet de jouer et d'enregistrer des parties sur le poste ;
3. le mode LAN permet d'heberger une partie reseau locale avec un hote qui
   fait autorite ;
4. la base de donnees conserve les joueurs, les matchs et les historiques ;
5. l'extension Arduino vient en bonus et n'est jamais obligatoire.

Le projet a ete pense pour etre demonstrable dans un cadre scolaire ou
universitaire, avec une interface visuelle, une structure logicielle claire,
et une separation nette entre le jeu, le reseau, la persistance et
l'extension electronique.

[Capture a inserer ici : arborescence simplifiee du projet]

---

## 2. Objectif du jeu et de l'application

L'objectif fonctionnel du projet est de proposer une application de jeu
desktop capable de :

1. lancer des affrontements locaux entre joueurs humains ou contre une IA ;
2. organiser des parties sur reseau local via un hall LAN ;
3. memoriser les joueurs et les resultats des joutes ;
4. afficher un historique exploitable pour une demonstration ou un suivi ;
5. ouvrir le projet a une extension interdisciplinaire avec Arduino.

Sur le plan pedagogique, Arena Duel permet de montrer plusieurs competences en
une seule application :

1. developpement d'interface graphique ;
2. programmation evenementielle ;
3. gestion d'une base de donnees relationnelle ;
4. architecture client/serveur en reseau local ;
5. packaging d'une application Windows ;
6. extension materielle facultative.

Le projet n'est donc pas seulement un jeu. Il constitue aussi un support de
presentation de competences logicielles et systemes.

[Capture a inserer ici : ecran du launcher montrant les modes disponibles]

---

## 3. Technologies utilisees

Le projet reel s'appuie sur les technologies suivantes.

| Couche | Technologie | Role dans le projet |
| --- | --- | --- |
| Interface desktop | CustomTkinter | Construction du launcher, de la forge, des chroniques et du hall LAN |
| Moteur de jeu | pygame-ce | Rendu du match, gameplay, audio, arene |
| Langage principal | Python 3.14 | Coordination generale de l'application |
| Persistance | MariaDB | Stockage des joueurs, matchs, halls LAN et vues statistiques |
| Administration BD | phpMyAdmin via XAMPP | Creation, import et verification de la base |
| Serveur local de services web | Apache via XAMPP | Hebergement de phpMyAdmin |
| Connecteur Python/BD | MariaDB Connector/Python | Connexion du jeu a la base |
| Packaging Windows | PyInstaller | Production de l'executable portable |
| Installateur Windows | Inno Setup | Generation optionnelle d'un setup |
| Extension materielle | pyserial et Arduino | Communication serie facultative vers LCD I2C et buzzer |

Technologiquement, le projet est organise autour des repertoires suivants :

1. ui pour l'interface ;
2. game pour le gameplay ;
3. network pour le LAN ;
4. db pour la base de donnees et les repositories ;
5. hardware pour l'extension Arduino ;
6. assets pour les ressources graphiques et sonores.

[Capture a inserer ici : schema d'architecture generale du projet]

---

## 4. Prerequis d'installation

Avant toute installation, il faut distinguer deux cas d'usage.

### 4.1 Cas 1 - Installation complete du projet

Ce cas est celui a presenter si l'on veut montrer la couche base de donnees,
phpMyAdmin et la logique complete du projet.

Prerequis recommandes :

1. Windows 10 ou Windows 11 ;
2. droits d'installation suffisants sur le poste ;
3. XAMPP ;
4. Python 3.14.x, si l'on lance le projet depuis les sources ;
5. le dossier complet du projet ;
6. un acces reseau local si l'on veut demontrer le mode LAN sur deux postes.

### 4.2 Cas 2 - Version de demonstration packagée

Ce cas correspond a la version preparée pour l'oral.

Prerequis recommandes :

1. Windows 10 ou Windows 11 ;
2. le dossier portable de demonstration ;
3. aucun Python ;
4. aucun XAMPP ;
5. aucune installation MariaDB obligatoire.

Important : la version de demonstration actuelle utilise un stockage local de
demonstration. Elle fonctionne donc meme si la base de donnees n'est pas
installee sur la machine de presentation.

[Capture a inserer ici : resume visuel des deux modes d'exploitation du projet]

---

## 5. Installation des outils necessaires

### 5.1 Installation de XAMPP

La premiere etape de l'installation complete consiste a mettre en place XAMPP.

#### 5.1.1 A quoi sert XAMPP dans le projet

Dans Arena Duel, XAMPP sert principalement a fournir un environnement simple
pour administrer la base de donnees locale.

Concretement :

1. le module MySQL de XAMPP fournit le moteur de base de donnees utilise par
   le projet ;
2. phpMyAdmin permet de creer la base, d'importer le schema SQL et de verifier
   les tables ;
3. Apache sert a afficher phpMyAdmin dans le navigateur.

Il est important de bien comprendre la repartition des roles :

1. le jeu communique avec la base de donnees via le connecteur MariaDB Python ;
2. phpMyAdmin n'est pas utilise par le jeu directement ;
3. phpMyAdmin sert uniquement a preparer, controler et administrer la base ;
4. Apache est necessaire pour ouvrir phpMyAdmin, mais n'est pas indispensable
   pour jouer une fois la base correctement configuree.

Autrement dit, si l'on veut seulement que le jeu se connecte a la base, le
service MySQL/MariaDB est indispensable. Si l'on veut administrer cette base
avec une interface graphique, il faut en plus demarrer Apache afin d'utiliser
phpMyAdmin.

[Capture a inserer ici : ecran d'installation de XAMPP]

#### 5.1.2 Telechargement et installation de XAMPP

Procedure recommandee :

1. telecharger XAMPP depuis le site officiel Apache Friends ;
2. lancer l'installateur en mode administrateur si necessaire ;
3. choisir un dossier d'installation simple, par exemple C:/xampp ;
4. terminer l'installation puis ouvrir XAMPP Control Panel.

#### 5.1.3 Composants utiles a cocher

Pour ce projet, les composants les plus utiles sont les suivants :

1. Apache ;
2. MySQL, qui correspond dans ce contexte a l'instance locale compatible
   MariaDB utilisee par le projet ;
3. PHP ;
4. phpMyAdmin.

Les composants suivants ne sont pas necessaires pour Arena Duel dans sa forme
actuelle, sauf besoin particulier :

1. FileZilla ;
2. Mercury ;
3. Tomcat ;
4. Webalizer.

Si l'installateur propose trop d'elements, la solution la plus simple pour ce
projet est de conserver uniquement ce qui est utile a la gestion de la base de
donnees et de son interface d'administration.

[Capture a inserer ici : selection des composants XAMPP]

#### 5.1.4 Demarrage de XAMPP Control Panel

Une fois XAMPP installe :

1. ouvrir XAMPP Control Panel ;
2. verifier que les modules Apache et MySQL sont visibles ;
3. lancer d'abord MySQL ;
4. lancer ensuite Apache.

Ordre recommande :

1. MySQL ;
2. Apache.

Cet ordre est recommande parce qu'il permet de s'assurer que le moteur de base
de donnees est bien operationnel avant d'ouvrir l'interface phpMyAdmin.

#### 5.1.5 Role des services demarres

1. MySQL/MariaDB : sert a stocker les joueurs, les parties, les halls LAN et
   les chroniques du projet.
2. Apache : sert a rendre phpMyAdmin accessible dans le navigateur via une
   adresse locale telle que http://localhost/phpmyadmin.

En pratique :

1. pour preparer la base, il faut MySQL et Apache ;
2. pour jouer apres configuration, MySQL est indispensable ;
3. Apache peut etre arrete si phpMyAdmin n'est plus necessaire.

[Capture a inserer ici : interface principale de XAMPP]

[Capture a inserer ici : XAMPP Control Panel avec Apache et MySQL demarres]

### 5.2 Installation de Python et du projet source

Cette sous-partie est utile si l'on veut lancer Arena Duel depuis les sources,
et pas seulement utiliser l'executable de demonstration.

Etapes recommandees :

1. installer Python 3.14.x ;
2. cocher l'option Add Python to PATH pendant l'installation ;
3. recuperer le projet sur le poste ;
4. ouvrir un terminal dans le dossier du projet ;
5. executer setup_env.bat ;
6. verifier la creation du dossier .venv ;
7. lancer run_local.bat ou main.py selon le besoin.

[Capture a inserer ici : installation de Python avec l'option Add Python to PATH]

[Capture a inserer ici : dossier source du projet sur le poste]

---

## 6. Mise en place de la base de donnees

### 6.1 Ouvrir phpMyAdmin depuis XAMPP

Une fois Apache et MySQL demarres dans XAMPP :

1. cliquer sur le bouton Admin du module MySQL ou du module Apache selon la
   configuration locale ;
2. ou bien ouvrir manuellement le navigateur a l'adresse
   http://localhost/phpmyadmin ;
3. verifier que l'interface phpMyAdmin s'affiche correctement.

Dans le cadre du projet, phpMyAdmin sert a :

1. creer la base de donnees ;
2. importer le schema SQL ;
3. verifier la presence des tables ;
4. observer les donnees enregistrees par le jeu.

[Capture a inserer ici : page d'accueil phpMyAdmin]

### 6.2 Creer la base de donnees

La base attendue par le projet s'appelle : arena_duel_v2_db.

Procedure recommandee :

1. dans phpMyAdmin, cliquer sur Nouvelle base de donnees ;
2. saisir le nom arena_duel_v2_db ;
3. choisir un interclassement compatible UTF-8, idealement utf8mb4_unicode_ci ;
4. valider la creation.

Remarque importante : le fichier schema_v2.sql contient deja une instruction
CREATE DATABASE IF NOT EXISTS arena_duel_v2_db. Il est donc possible de laisser
le script creer lui-meme la base. Neanmoins, dans un compte rendu, il est plus
clair et plus pedagogique de montrer d'abord la creation de la base, puis son
import.

[Capture a inserer ici : creation de la base de donnees arena_duel_v2_db]

### 6.3 Importer le fichier SQL du projet

Le fichier SQL principal du projet est : schema_v2.sql.

Un second fichier, shema.sql, existe comme alias legacy de compatibilite, mais
le fichier de reference a utiliser pour une installation propre est bien
schema_v2.sql.

Procedure d'import recommandee :

1. selectionner la base arena_duel_v2_db dans la colonne de gauche ;
2. cliquer sur l'onglet Importer ;
3. choisir le fichier schema_v2.sql depuis le dossier du projet ;
4. conserver les options d'import standard si aucune contrainte particuliere
   n'est imposee ;
5. lancer l'import ;
6. attendre le message de succes.

Le script va :

1. creer les tables necessaires ;
2. inserer au moins une arene par defaut, Forgotten Sanctum ;
3. creer plusieurs vues SQL utilisees pour les historiques et statistiques.

[Capture a inserer ici : import du fichier schema_v2.sql]

### 6.4 Verifications apres import

Apres l'import, il faut verifier les points suivants :

1. la base arena_duel_v2_db apparait bien dans phpMyAdmin ;
2. les tables players, arenas, player_preferences, lobby_sessions,
   lobby_members, matches et match_players sont presentes ;
3. les vues v_match_history_cards, v_player_career_stats et
   v_team_career_stats existent egalement ;
4. la table arenas contient l'arene forgotten_sanctum ;
5. aucune erreur SQL bloquante n'a ete signalee pendant l'import.

Si ces elements sont visibles, la base peut etre consideree comme prete.

[Capture a inserer ici : apercu des tables apres import]

[Capture a inserer ici : exemple de contenu de la table arenas]

---

## 7. Explication de la base de donnees du projet

La base arena_duel_v2_db joue un role central dans l'installation complete du
projet. Elle ne sert pas seulement a stocker un score. Elle conserve plusieurs
types d'informations relies au jeu et au mode LAN.

### 7.1 Role global de la base

La base sert a :

1. enregistrer les joueurs ;
2. conserver l'historique des matchs ;
3. memoriser les participants a chaque joute ;
4. stocker les informations du hall LAN ;
5. fournir des vues de lecture pour l'historique et certaines statistiques.

### 7.2 Tables principales

#### players

Cette table represente le registre des combattants.

Elle contient notamment :

1. l'identifiant du joueur ;
2. son nom, stocke dans le champ username ;
3. son statut ;
4. des dates de creation et de mise a jour.

Dans le jeu, cette table est alimentee lors de l'enrolement d'un combattant
dans la forge locale.

#### arenas

Cette table repertorie les arenes connues par le projet.

Elle contient notamment :

1. un code logique d'arene ;
2. un libelle ;
3. le chemin vers le layout correspondant ;
4. une version de layout ;
5. un indicateur d'activation.

Une arene par defaut est creee dans le script : forgotten_sanctum.

#### player_preferences

Cette table sert a memoriser certaines preferences associees a un joueur,
comme l'arene ou le mode local recemment utilises.

#### lobby_sessions

Cette table correspond aux sessions LAN ouvertes par un poste hote.

Elle permet de conserver :

1. le code d'invitation ;
2. le joueur hote ;
3. l'arene choisie ;
4. la duree du match ;
5. l'etat du hall ;
6. les dates d'ouverture et de fermeture.

#### lobby_members

Cette table recense les membres presents dans un hall LAN.

Elle stocke notamment :

1. la session LAN concernee ;
2. le joueur ;
3. le nom affiche ;
4. le slot occupe ;
5. l'equipe ;
6. l'etat pret ou non pret.

#### matches

Cette table constitue le coeur de l'historique des joutes.

Elle enregistre notamment :

1. le mode de match ;
2. la source, locale ou LAN ;
3. l'arene ;
4. les scores des deux equipes ;
5. l'equipe gagnante ;
6. la duree ;
7. les dates de debut, fin et archivage.

#### match_players

Cette table detaille les participants de chaque match.

Elle permet de savoir :

1. qui a participe ;
2. dans quelle equipe ;
3. a quel slot ;
4. si le participant etait une IA ;
5. quel score individuel a ete associe.

### 7.3 Vues principales

Le schema cree aussi plusieurs vues utiles pour la lecture.

#### v_match_history_cards

Cette vue assemble les informations principales d'une joute afin de pouvoir
afficher une chronique lisible dans l'interface : arene, joueurs de l'equipe A,
joueurs de l'equipe B, scores, vainqueur, duree et date.

#### v_player_career_stats

Cette vue agrège les statistiques par joueur : nombre de matchs, victoires,
defaites, matchs nuls et score total.

#### v_team_career_stats

Cette vue resume les statistiques globales par equipe.

[Capture a inserer ici : apercu de la base de donnees et des tables]

[Capture a inserer ici : exemple de contenu d'une table importante, par exemple players ou matches]

---

## 8. Liaison entre le jeu et la base de donnees

La liaison entre Arena Duel et la base de donnees repose sur un principe tres
simple : l'application lit un fichier de configuration runtime, puis ouvre une
connexion MariaDB a partir de ces parametres.

### 8.1 Fichier de configuration principal

Le fichier a surveiller est : app_runtime.json.

Dans ce fichier, on retrouve les parametres suivants :

1. db_host ;
2. db_port ;
3. db_user ;
4. db_password ;
5. db_name ;
6. db_connect_timeout.

Valeurs actuellement prevues par defaut pour l'installation locale :

1. db_host = localhost ;
2. db_port = 3306 ;
3. db_user = root ;
4. db_password = chaine vide si XAMPP est en configuration locale simple ;
5. db_name = arena_duel_v2_db.

Si le mot de passe root de XAMPP a ete modifie, il faut mettre a jour
db_password en consequence.

[Capture a inserer ici : fichier app_runtime.json avec les parametres de connexion]

### 8.2 Fichiers Python concernes

La liaison reelle au niveau code s'appuie principalement sur les elements
suivants :

1. runtime_utils.py charge la configuration runtime ;
2. db/database.py ouvre la connexion avec mariadb.connect ;
3. db/players.py interagit avec le registre des combattants ;
4. db/match_repository.py archive les joutes et reconstruit l'historique ;
5. ui/launcher.py permet de verifier visuellement l'etat de la liaison.

Le fonctionnement est le suivant :

1. l'application charge les valeurs de app_runtime.json ;
2. db/database.py tente une connexion a l'hote et au port specifies ;
3. si la connexion reussit, le launcher peut annoncer que les chroniques sont
   pretes ;
4. si la connexion echoue, le launcher signale que le sanctuaire est
   indisponible.

### 8.3 Verification concrete de la liaison

Pour verifier que la liaison fonctionne reellement :

1. demarrer MySQL dans XAMPP ;
2. verifier que la base arena_duel_v2_db existe ;
3. lancer le jeu ;
4. cliquer sur le bouton Verifier le sanctuaire dans le launcher ;
5. observer le message retourne par l'interface.

Comportement attendu :

1. si tout est correct, le launcher affiche un etat de type Chroniques pretes ;
2. si la base n'est pas joignable, le launcher affiche un message du type
   Sanctuaire indisponible.

[Capture a inserer ici : preuve que la connexion a la base fonctionne depuis le launcher]

### 8.4 Problemes de liaison les plus frequents

Les causes les plus classiques sont :

1. MySQL n'est pas demarre ;
2. le port n'est pas 3306 ;
3. le mot de passe root n'est pas celui attendu ;
4. la base arena_duel_v2_db n'a pas ete importee ;
5. le fichier app_runtime.json ne contient pas les bons parametres.

La correction consiste alors a verifier l'ordre suivant :

1. etat de MySQL dans XAMPP ;
2. existence de la base dans phpMyAdmin ;
3. valeurs du fichier app_runtime.json ;
4. nouveau test via le bouton Verifier le sanctuaire.

### 8.5 Cas particulier de la version de demonstration

La version portable preparee pour l'oral contient elle aussi un fichier
app_runtime.json, place a cote de l'executable. Dans ce cas precis, le fichier
active un mode de demonstration autonome avec stockage local. Cela signifie que
la version orale actuelle ne depend pas d'une base MariaDB pour fonctionner.

Cette nuance est importante a expliquer devant un professeur :

1. l'architecture complete du projet repose bien sur MariaDB ;
2. mais la version de demonstration a ete volontairement securisee pour
   l'oral, afin d'eviter qu'une panne XAMPP ou une indisponibilite de base ne
   bloque toute la soutenance.

[Capture a inserer ici : ecran du jeu apres liaison reussie ou lancement en mode demonstration]

---

## 9. Installation du jeu et de la demonstration

### 9.1 Installation du jeu depuis les sources

Cette methode est adaptee a une machine de developpement ou a une presentation
technique complete.

Procedure recommandee :

1. recuperer le dossier source complet ;
2. installer Python 3.14.x ;
3. lancer setup_env.bat ;
4. verifier la presence du dossier .venv ;
5. demarrer XAMPP et la base si l'on veut la persistance complete ;
6. lancer main.py ou run_local.bat.

Le point d'entree principal du projet est main.py, qui ouvre le launcher.

### 9.2 Installation de la version de demonstration packagée

La version de demonstration actuelle est livree dans le dossier suivant :

dist_demo/ArenaDuel_Demo_Windows.

Le lancement principal se fait via :

dist_demo/ArenaDuel_Demo_Windows/Portable/ArenaDuel/ArenaDuel.exe.

Cette version est adaptee a l'oral car elle :

1. ne demande pas Python ;
2. ne demande pas pip ;
3. ne demande pas XAMPP ;
4. ne demande pas MariaDB ;
5. utilise un stockage local de demonstration ;
6. embarque sa propre configuration runtime.

Les donnees de demonstration sont enregistrees dans le dossier utilisateur,
generalement sous la forme %APPDATA%/ArenaDuel/arena_duel_demo_state.json.

Si la demonstration doit etre reinitialisee, il suffit de fermer le jeu,
supprimer ce fichier, puis relancer l'executable.

[Capture a inserer ici : dossier contenant la demo Windows]

[Capture a inserer ici : executable ArenaDuel.exe pret a etre lance]

#### 9.2.1 Ce qu'il faut conserver dans le dossier de demonstration

Pour eviter tout probleme, il faut conserver ensemble :

1. le dossier Portable ;
2. l'executable ArenaDuel.exe ;
3. le fichier app_runtime.json livre avec l'executable ;
4. le sous-dossier _internal ;
5. les assets livres dans le package.

Il ne faut pas isoler ArenaDuel.exe seul hors de son dossier, car le build
portable s'appuie sur des fichiers embarques autour de l'executable.

#### 9.2.2 Quand faut-il encore utiliser XAMPP avant le lancement

Reponse nuancee :

1. si l'on utilise la version de demonstration actuelle, XAMPP n'est pas
   necessaire ;
2. si l'on veut montrer la vraie chaine complete avec base et phpMyAdmin,
   alors il faut demarrer MySQL avant le lancement ;
3. Apache ne devient necessaire que si l'on veut ouvrir phpMyAdmin pendant la
   demonstration.

[Capture a inserer ici : premier ecran du jeu apres lancement]

---

## 10. Procedure complete de lancement

Pour etre utile en soutenance, il est preferable de presenter deux procedures :

1. la procedure complete, qui montre le projet avec XAMPP et la base ;
2. la procedure rapide, qui correspond a la demonstration autonome packagée.

### 10.1 Procedure complete avec XAMPP et base de donnees

1. Installer XAMPP.
2. Ouvrir XAMPP Control Panel.
3. Demarrer MySQL.
4. Demarrer Apache.
5. Ouvrir phpMyAdmin a l'adresse http://localhost/phpmyadmin.
6. Creer la base arena_duel_v2_db si necessaire.
7. Importer le fichier schema_v2.sql.
8. Verifier la presence des tables et des vues.
9. Verifier le contenu de app_runtime.json.
10. Lancer le projet avec main.py ou run_local.bat.
11. Dans le launcher, cliquer sur Verifier le sanctuaire.
12. Verifier que l'etat de connexion est correct.
13. Ouvrir la forge locale ou le hall LAN selon le scenario de demonstration.
14. Jouer une joute.
15. Ouvrir les chroniques pour verifier l'archivage.

[Capture a inserer ici : phpMyAdmin avec base importee et tables visibles]

[Capture a inserer ici : launcher avec verification du sanctuaire reussie]

### 10.2 Procedure rapide pour l'oral avec la demo packagée

1. Ouvrir le dossier dist_demo/ArenaDuel_Demo_Windows.
2. Entrer dans Portable/ArenaDuel.
3. Double-cliquer sur ArenaDuel.exe.
4. Ouvrir la forge locale.
5. Choisir des combattants deja presents dans le registre de demonstration.
6. Lancer une joute.
7. Ouvrir les chroniques pour montrer que la demonstration archive bien les
   resultats dans son stockage local.

Cette version est la plus fiable pour l'oral, car elle reduit fortement les
risques lies a l'environnement machine.

[Capture a inserer ici : procedure rapide de lancement de la demo]

---

## 11. Fonctionnement general du projet

Le fonctionnement global du projet peut etre presente de la maniere suivante.

### 11.1 Point d'entree unique

Le fichier main.py ouvre le launcher principal. Cette interface regroupe les
fonctions essentielles du projet :

1. ouvrir la forge locale ;
2. ouvrir le hall LAN ;
3. rejoindre un hall ;
4. consulter les chroniques ;
5. verifier l'etat du sanctuaire, c'est-a-dire la connexion aux donnees.

### 11.2 Forge locale

La forge locale correspond au mode de jeu sur un seul poste.

Dans ce mode :

1. les joueurs sont choisis localement ;
2. le match se lance sans dependance reseau ;
3. le resultat peut etre archive dans la base si celle-ci est active ;
4. dans la demo packagée, le resultat est archive dans le stockage local de
   demonstration.

[Capture a inserer ici : ecran de forge locale]

### 11.3 Hall LAN

Le mode LAN se decompose en deux roles :

1. le poste hote ;
2. le poste client.

Le poste hote :

1. demarre le serveur LAN integre ;
2. genere une invitation de type IP:port ;
3. centralise l'etat du hall et du match ;
4. archive les resultats LAN.

Le poste client :

1. rejoint le hall via l'invitation ;
2. participe au lobby et au match ;
3. consulte l'historique LAN fourni par l'hote ;
4. n'a pas besoin d'agir comme serveur MariaDB.

Cette architecture permet de separer clairement le mode local et le mode LAN,
ce qui rend la demonstration plus lisible.

[Capture a inserer ici : hall LAN cote hote]

[Capture a inserer ici : hall LAN cote client]

### 11.4 Historique et chroniques

Le projet contient une vue chroniques qui permet de relire les matchs joues.

Les chroniques affichent notamment :

1. les joueurs de l'equipe A ;
2. les joueurs de l'equipe B ;
3. les scores ;
4. le vainqueur ;
5. la duree du match ;
6. la date.

L'historique est alimente par les donnees issues des tables matches et
match_players, ou par la vue v_match_history_cards.

[Capture a inserer ici : ecran des chroniques]

### 11.5 Parcours utilisateur type

Un parcours simple a presenter est le suivant :

1. ouverture du launcher ;
2. verification rapide de l'etat du sanctuaire ;
3. ouverture de la forge locale ;
4. choix des combattants ;
5. lancement de la joute ;
6. retour au launcher ou aux chroniques ;
7. consultation du resultat archive.

En LAN, on remplace la forge locale par :

1. ouverture du hall LAN sur le poste hote ;
2. connexion du client via l'invitation ;
3. preparation du lobby ;
4. lancement du match ;
5. retour au hall ;
6. consultation de l'historique LAN.

[Capture a inserer ici : exemple d'interface de partie ou d'ecran de combat]

[Capture a inserer ici : ecran final ou resultat d'une joute]

---

## 12. Difficultes rencontrees et choix techniques

Plusieurs choix techniques importants structurent le projet.

### 12.1 Conserver un launcher unique

Le projet a fait le choix de garder une entree principale unique. Ce choix est
interessant pedagogiquement, car il montre que le mode local et le mode LAN ne
sont pas deux applications differentes, mais deux usages d'un meme produit.

### 12.2 Separer clairement le local et le LAN

Un autre choix important est de ne pas confondre la logique locale et la
logique reseau.

Le mode local reste autonome. Le mode LAN repose sur un hote autoritaire. Cela
rend la demonstration plus robuste et plus facile a expliquer.

### 12.3 Centraliser l'archivage des matchs

Le projet enregistre les matchs de maniere structuree, avec une table pour le
match et une table pour les participants. Ce choix est plus solide qu'un simple
stockage de score, car il permet d'afficher un historique riche et evolutif.

### 12.4 Rendre la demonstration orale plus fiable

Un point important du travail recent a consisté a preparer une version de
demonstration moins fragile. La version portable actuelle peut fonctionner sans
MariaDB afin d'eviter qu'un incident sur XAMPP ne compromette toute la
soutenance.

Ce n'est pas une simplification de l'architecture, mais un choix de robustesse
pour la presentation.

### 12.5 Garder l'extension Arduino optionnelle

L'extension materielle a ete isolee pour que le jeu continue a fonctionner meme
en cas d'absence de carte, de port serie ou de bibliotheque pyserial.

Ce choix est important car il montre une bonne separation des responsabilites.

---

## 13. Ce qu'il reste possible d'ameliorer

Le projet est deja presentable, mais plusieurs pistes d'amelioration sont
possibles.

1. enrichir davantage les statistiques joueurs et equipes ;
2. ajouter plusieurs arenes et les exposer plus visiblement dans l'interface ;
3. etendre le mode LAN avec davantage d'outils de supervision ;
4. proposer un veritable installateur toujours genere, meme sur un poste sans
   Inno Setup ;
5. produire une documentation utilisateur finale encore plus illustree ;
6. renforcer la personnalisation des combattants et de l'historique ;
7. automatiser davantage les tests de build Windows.

[Capture a inserer ici : idee d'evolution future ou schema d'amelioration]

---

## 14. Problemes possibles et solutions

Cette section est utile pour accompagner l'installation et la demonstration.

### 14.1 XAMPP ne demarre pas

Cause probable : installation incomplete, droits insuffisants ou conflit de
ports.

Solution :

1. relancer XAMPP en administrateur ;
2. verifier qu'aucun autre serveur n'occupe deja les ports utilises ;
3. reinstaller XAMPP si necessaire dans un dossier simple comme C:/xampp.

### 14.2 MySQL ne se lance pas

Cause probable : port 3306 deja occupe, service bloque ou donnees XAMPP
corrompues.

Solution :

1. verifier les messages dans XAMPP Control Panel ;
2. verifier si un autre service MySQL est deja actif ;
3. libérer le port ou ajuster le port configure ;
4. reporter le changement de port dans app_runtime.json si besoin.

[Capture a inserer ici : message d'erreur MySQL dans XAMPP]

### 14.3 phpMyAdmin n'est pas accessible

Cause probable : Apache n'est pas demarre ou le port web est occupe.

Solution :

1. verifier qu'Apache est bien demarre ;
2. tester http://localhost/phpmyadmin ;
3. si localhost ne repond pas, verifier les ports web utilises par Apache.

### 14.4 L'import SQL echoue

Cause probable : mauvais fichier, base non selectionnee ou erreur de droits.

Solution :

1. utiliser schema_v2.sql ;
2. verifier que la base arena_duel_v2_db existe ;
3. relancer l'import depuis phpMyAdmin ;
4. observer la ligne exacte d'erreur si phpMyAdmin en affiche une.

### 14.5 Le jeu ne se connecte pas a la base

Cause probable : mauvais host, mauvais mot de passe, base absente ou MySQL
eteint.

Solution :

1. verifier app_runtime.json ;
2. verifier que MySQL tourne ;
3. verifier que la base arena_duel_v2_db est bien importee ;
4. cliquer sur Verifier le sanctuaire dans le launcher.

[Capture a inserer ici : comparaison entre configuration correcte et incorrecte]

### 14.6 L'executable ne trouve pas certains fichiers

Cause probable : executable deplace seul hors de son dossier portable.

Solution :

1. remettre ArenaDuel.exe dans son dossier d'origine ;
2. conserver le dossier _internal et les autres fichiers autour de lui ;
3. relancer depuis Portable/ArenaDuel.

### 14.7 Le LAN ne fonctionne pas

Cause probable : postes non connectes au meme reseau, pare-feu Windows,
invitation IP incorrecte ou port indisponible.

Solution :

1. verifier que les deux postes sont sur le meme reseau local ;
2. verifier l'invitation IP:port fournie par l'hote ;
3. autoriser l'application dans le pare-feu Windows si necessaire ;
4. tester d'abord le mode local pour confirmer que l'application elle-meme est
   saine.

[Capture a inserer ici : invitation LAN visible cote hote]

### 14.8 La version de demonstration se comporte de facon inhabituelle

Cause probable : donnees locales de demo deja polluees par des essais
precedents.

Solution :

1. fermer le jeu ;
2. supprimer le fichier %APPDATA%/ArenaDuel/arena_duel_demo_state.json ;
3. relancer l'executable.

---

## 15. Bonus - Extension Arduino

L'extension Arduino constitue un bonus technique et pedagogique du projet.

### 15.1 Idee generale

L'objectif de cette extension est de faire sortir une partie des informations
du jeu vers un montage electronique externe.

Le jeu peut ainsi communiquer certains evenements de match a une carte Arduino,
par exemple :

1. changement d'etat du jeu ;
2. mise a jour du score ;
3. annonce du vainqueur ;
4. signal sonore de fin ou d'evenement important.

### 15.2 Lien entre le jeu et l'electronique

Le gameplay ne parle pas directement au port serie. Il passe par une facade
logicielle dediee, ce qui permet de garder une architecture propre.

Les fichiers impliques sont principalement :

1. hardware/service.py ;
2. hardware/bridge.py ;
3. hardware/arduino.py.

Le protocole serie transmet des messages simples tels que RESET, STATE, SCORE
ou WINNER.

### 15.3 Role de l'ecran LCD I2C

L'ecran LCD I2C permet d'afficher des informations externes au PC,
principalement :

1. l'etat du jeu ;
2. le score courant ;
3. le resultat final.

Ce composant renforce l'aspect demonstratif et donne une dimension physique au
projet.

### 15.4 Role du buzzer

Le buzzer sert a signaler des evenements importants, par exemple :

1. debut ou fin de phase ;
2. alerte de resultat ;
3. retour sonore visible pour le public.

### 15.5 Fonctionnalite strictement optionnelle

Un point essentiel a souligner dans le compte rendu est le suivant :

1. le jeu fonctionne integralement sans Arduino ;
2. si le support serie est desactive, rien ne casse ;
3. si pyserial n'est pas installe, le jeu continue ;
4. si aucun port n'est detecte, le jeu continue ;
5. si la liaison tombe, le jeu continue.

Cette robustesse est pedagogiquement interessante car elle montre une bonne
gestion du fallback.

### 15.6 Interet pedagogique et technique

L'extension Arduino permet de montrer que le projet ne se limite pas a une
application logicielle classique. Elle introduit une dimension
interdisciplinaire entre informatique, interface, temps reel et electronique.

Dans une presentation, cette partie peut etre utilisee comme ouverture,
amelioration future ou bonus de valorisation technique.

[Capture a inserer ici : montage Arduino]

[Capture a inserer ici : ecran LCD affichant les scores]

[Capture a inserer ici : vue d'ensemble du montage electronique]

---

## Conclusion

Arena Duel est un projet coherent, demonstrable et pedagogiquement riche. Il
combine une interface desktop, un moteur de jeu, une base de donnees, une
logique reseau locale et une extension Arduino optionnelle.

Son interet principal, dans un contexte de presentation, est de montrer a la
fois :

1. une application complete et visible ;
2. une vraie logique de persistance ;
3. une architecture LAN intelligible ;
4. une capacite de packaging reelle pour Windows ;
5. une ouverture vers l'electronique embarquee.

Enfin, le projet dispose maintenant d'une version de demonstration autonome,
plus fiable pour l'oral, tout en conservant une architecture complete avec base
de donnees pour l'explication technique et le dossier de soutenance.

[Capture a inserer ici : capture finale de conclusion ou vue complete du projet]