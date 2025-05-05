Scripts pour Therion
====================

🇬🇧 [Read in English](./README.en.md)

pyThtoDat
---------

Script pour convertir une database (.sql) produit par Therion
en fichier Compass (.dat) et (.mak)


Usage : python pyThtoDat.py

Utilisation :
	- Exporter le fichier .sql avec Therion, commande dans fichier .thconfig: 'export database -o Outputs/database.sql'
	- Sélectionner le fichier database.sql à calculer dans la fenêtre
	- Définir l’éventuel préfix à chaque station

Résultat : fichiers (.dat) et (.mak) dans le même dossier

Attention : Les stations sont nommées avec le numéro d'ordre de la BD Therion et pas les numéros des fichiers (.th)

	
pyCreate_th2
------------

Script pour automatiser la création des dossiers et fichiers pour un fichier .th

Usage : python pyCreate_th2.py

Utilisation :
	- Définir les différentes variables dans fichier config.ini   
	- Création des dossiers nécessaires d'après dossier 'template'
	- Création des fichiers nécessaires : th, th2, -tot.th
	- Création des scraps avec les stations topo


pyThStat
--------

Script pour calculer les statistiques des entités jonctionnées d'un fichier database (.sql) produit par Therion

Utilisation:
	- Exporter le fichier sql avec therion, commande therion.thconfig : export database -o Outputs/database.sql
	- Commande : python pythStat.py ./chemin/fichier.sql
	- Ou : python pythStat.py  pour ouvrir une fenêtre
	
	
pyThtoBD (développement en cours)
--------

Script pour exporter une base Therion vers une base de données type Karsteau 

Utilisation:
	- Placer des fichiers Export_bd.ini dans chacun des dossiers des cavités à exporter                                    
	- Lancer python pyThtoDB.py, sélectionner le dossier therion à exporter                                                 
	- Résultats pour Karsteau dans le dossier /Outputs/Export_bd/                                                             
	- A venir - Importer le résultat de l'importation dans Karsteau    

[Détails](./pyThtoBD/README.rst)	