****************************************************************************
Export db Therion  <--> db KARSTEAU
***************************************************************************

Créer manuellement dans chaque dossier d'une cavité à exporter un fichier export_bd.ini
     - vide au début
     - après exécution du script contient l'ID Therion de la cavité à exporter 

Résultats dans le dossier /Outputs/Export_bd de la db Therion :
	- Export_bd.log	: log de l'export
	- Export_bd.bd		: base de données de transfert
	- Export_bd.xlxs	: fichier excel pour l'export vers Karsteau
	- Export_bd.zip	: archive brute des données Therion
 

==============================
Table des données exportées :
==============================

Cavité (la liste est générée automatiquement en recherchant dans les dossiers les fichiers export_bd.ini copiés manuellement)
-----------------------------------------------------------------------------------------------------------
CAVITE_ID                : Clé interne de la cavité (unique, entier, génération par le script) 	
CAVITE_NAME              : Nom de la cavité (via la valeur -title de la survey du fichiet _tot.th du dossier contenant la cavité)
CAVITE_SYNO_1            : Synonyme 1 de la cavité  !!! Pas dispo dans Therion
CAVITE_SYNO_2            : Synonyme 2 de la cavité  !!! Pas dispo dans Therion
CAVITE_SYNO_3	          : Synonyme 3 de la cavité  !!! Pas dispo dans Therion
CAVITE_DEV	          : Développement de la cavité (via le fichier .log de la cavité)
CAVITE_DENIV_PLUS	     : Dénivelé positif de la cavité, à voir définition Karsteau si plusieurs entrées ?
CAVITE_DENIV_MOINS	     : Dénivelé négatif de la cavité (via le fichier .log de la cavité)
CAVITE_PATH	          : Interne au script pour identifier la cavité, chemin dans la base vers le dossier contenant la cavité   
CAVITE_KEY_KARSTEAU	     : Retour Karsteau, clé unique d'identification de la cavité
CAVITE_DATE_UPDATE	     : Date de mise à jour de la cavité (date d'execution du script)

Entrées (la liste des entrées est générée après l'execution du thconfig de la cavité via le fichier sql généré) 
---------------------------------------------------------------------------------------------------------------
ENT_ID				: Clé interne de l'entrée (unique, entier, génération par le script) 	
ENT_ID_CAVITE	          : Clé interne de la cavité associée (génération par le script)
ENT_NUM				: Numéro de l'entrée (exemple CD11 pour le Réseau du Mirolda... ) !!! Pas dispo dans Therion  
ENT_NAME				: Nom de l'entrée (via le fichier .sql de la cavité, valeur de -title de la survey contenant l'entrée)
ENT_SYNO_1			: Synonyme 1 de l'entrée	 !!! Pas dispo dans Therion  
ENT_SYNO_2	          : Synonyme 2 de l'entrée	 !!! Pas dispo dans Therion  
ENT_SYNO_3	          : Synonyme 3 de l'entrée	 !!! Pas dispo dans Therion  
ENT_MARQ_1			: Marquage 1 de l'entrée	 !!! Pas dispo dans Therion  
ENT_MARQ_2			: Marquage 2 de l'entrée	 !!! Pas dispo dans Therion  
ENT_MARQ_3			: Marquage 3 de l'entrée	 !!! Pas dispo dans Therion  
ENT_COORD_X			: Coordonnée X de l'entrée (via le fichier .sql de la cavité) 
ENT_COORD_Y			: Coordonnée Y de l'entrée (via le fichier .sql de la cavité) 
ENT_COORD_Z			: Coordonnée Z de l'entrée (via le fichier .sql de la cavité) 
ENT_UNIT_COORD           : Unité des coordonnées (m/km), toujours 'm'  
ENT_SYS_COORD		     : Système de coordonnée, (exemple UTM31, via le fichier .log de la cavité) 
ENT_ZONE_COORD           : Zone de Coordonnée  !!! A voir comment remplir  
ENT_METHODE_COORD	     : Méthode d'obtention de la coordonnée  !!! Pas dispo dans Therion
ENT_SOURCE_COORD 	     : Source de la coordonnée  (toujours 'Topo Therion)  !!! Pas dispo dans Therion
ENT_DATE_COORD		     : Date de la coordonnée  !!! A voir comment remplir   !!! Pas dispo dans Therion
ENT_ACCES_LIBRE          : Accès à la donnée dans Karsteau, par défaut 'N' (accès aves mdp)  
ENT_PATH                 : Interne au script pour identifier l'entrée, chemin vers la station de l'entrée (exemple : 00@Cap_Coutun)   
ENT_KEY_KARSTEAU         : Retour Karsteau, clé unique d'identification de l'entrée
ENT_DATE_UPDATE	     : Date de mise à jour de l'entrée (date d'execution du script)


Documents (Dans le dossier Outputs de la cavité, type pdf, kml et zip des données Therion)
-----------------------------------------------------------------------------------------------------------
DOCUMENT_x_ID	          : Clé interne du document (unique, entier, génération par le script) 	
DOCUMENT_x_AUTEUR        : Auteur du document (via exif du pdf, à voir pour les autres types)	
DOCUMENT_x_CAT	          : Catégorie du document suivant nomenclature Karsteau 
DOCUMENT_x_DATE	     : Date du document (via exif du pdf, à voir pour les autres types)	
DOCUMENT_x_DATE_UPDATE	: Date de mise à jour du document (date d'execution du script)
DOCUMENT_x_DESCRIPTION	: Description du document (via exif du pdf, à voir pour les autres types)
DOCUMENT_x_FILE	     : Chemin dans les dossiers pour identifier le document   
DOCUMENT_x_LIE           : Cavité ou Entrée, ensemble des documents sont liés au cavités
DOCUMENT_x_NATURE        : Nature du document : pdf, kml, zip... 
DOCUMENT_x_TEXT	     : Text du document !!! Pas dispo dans Therion  
DOCUMENT_x_TITRE	     : Titre du document (via exif du pdf, à voir pour les autres types)
DOCUMENT_x_KEY_KARSTEAU  : Retour Karsteau, clé unique d'identification du document



