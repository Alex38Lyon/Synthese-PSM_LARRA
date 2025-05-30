Base de données Topographiques des systèmes karstiques du massif de la Pierre Saint Martin - Larra 
==========================================================================================================

Ce dépôt contient les données topographiques et les dessins associés des cavités du massif de la Pierre Saint Martin - Larra .

Ce dépôt est mis à jour à chaque fois qu'une nouvelle topographie est rajoutée à l'un des systèmes décrit dans cette base de données.

Si besoin, des templates pour Therion sont disponibles sur https://github.com/robertxa/Th-Config-Xav .


Description
-----------

Ce dépôt est en cours de développement et a pour objectif de sauvegarder et partager les données topographiques chiffrées et dessinées au format `Therion  <https://therion.speleo.sk/>`_.
Ce travail est réalisé par les menbres de l'ARSIP, collectif d'exploration du massif de la pierre Saint Martin 

.. image:: /Logos/Logo-ARSIP-Synthese-Topo.jpg
  :target: http://arsip.fr/
  :align: center
  :width: 200px



Une convention a aussi été mise en place pour la gestion des points d'interrogation, avec la définition des différents champs :

	* le champ "Code" qui décrit le type de terminus. Il peut prendre les valeurs : 
	
		* A : il suffit d'y aller et de continuer, pas d'obstacles
		
		* D : Désobstruction nécessaire, 
		
		* E : Escalade nécessaire, 
		
		* P : Puits non descendu,
		
		* Q : non renseigné sur les topographies anciennes, c'est à voir/vérifier,
		
		* S : Siphon à plonger, 
		
		* T : Trémie à désobstruer
	
	* le champ "Cavite" qui donne le nom de la cavité en question,
	
	* le champ "Reseau" qui indique la partie de la cavité où se situe le point d'interrogation (pour pouvoir le retrouver plus rapidement sur les topographies),
	
	* le champ "CA" qui est rempli si présence de courant d'air, avec éventuellement des remarques/commentaires.
	
Exemple :  
point 3922.0 1660.0 continuation -attr code Q -attr Cavite "GL102" -attr reseau "Grand Chao"  -text "Rivière à topographier" -attr CA "inconnu"

Licence
-------

L'ensemble de ces données est publié sous la licence libre Creative Commons CC BY-NC-ND 4.0 (Attribution, partage à l'identique et pas d'utilisation commerciale) :
https://creativecommons.org/licenses/by-nc-nd/4.0/

.. image:: https://mirrors.creativecommons.org/presskit/buttons/88x31/png/by-nc-nd.png
  :align: center
  :width: 100px
  :target: https://creativecommons.org/licenses/by-nc-nd/4.0/

Auteur de la base de données
----------------------------

Alexandre PONT (alexandre dot pont at yahoo dot fr ) pour le compte de l'ARSIP 

Contact
--------

Pour plus d'informations, vous pouvez contacter L'ARSIP : https://www.arsip.fr/contactez-nous

Remerciements
-------------

Cette base de données est construite sur le modèle de celle des `massifs du Folly et de Criou <https://github.com/robertxa/Topographies-Samoens_Folly>`_, développée par Xavier Robert
), un grand merci pour le soutien actif
