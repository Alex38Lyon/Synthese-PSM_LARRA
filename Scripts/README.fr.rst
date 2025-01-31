====================
Scripts pour Therion
====================

---------
pyThtoDat
---------

.. centered:: Script pour convertir une database (.sql) produit par Therion                                    
.. centered:: en fichier Compass (.dat) et (.mak)


Usage : python pyThtoDat.py
Utilisation : 
	Exporter le fichier .sql avec Therion, commande dans fichier .thconfig: export database -o Outputs/database.sql
	Sélectionner le fichier database.sql à calculer dans la fenêtre
	Définir l’éventuel préfix à chaque station
	Résultat : fichiers (.dat) et (.mak) dans le même dossier
	Attention : Les stations sont nommées avec le numéro d'ordre de la BD Therion et pas les numéros des fichiers (.th)
	
------------
pyCreate_th2
------------

.. centered:: Script pour automatiser la création des dossiers et fichiers pour un fichier .th

Définir les différentes variables dans fichier config.ini   
Création des dossiers nécessaires d'après dossier 'template'
Création des fichiers nécessaires : th, th2, -tot.th
Création des scrap avec stations topo

Usage : python pyCreate_th2.py
