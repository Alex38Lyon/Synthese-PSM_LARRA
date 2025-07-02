
# Base de données Topographiques des systèmes karstiques du massif de la Pierre Saint Martin - Larra

Ce dépôt contient les données topographiques et les dessins associés des cavités du massif de la Pierre Saint Martin - Larra.

Ce dépôt est mis à jour à chaque fois qu'une nouvelle topographie est rajoutée à l'un des systèmes décrits dans cette base de données.

Si besoin, des templates pour Therion sont disponibles sur [https://github.com/robertxa/Th-Config-Xav](https://github.com/robertxa/Th-Config-Xav).

## Description

Ce dépôt est en cours de développement et a pour objectif de sauvegarder et partager les données topographiques chiffrées et dessinées au format [Therion](https://therion.speleo.sk/).  
Ce travail est réalisé par les membres de l'ARSIP, collectif d'exploration du massif de la Pierre Saint Martin.

<p align="center">
  <a href="http://arsip.fr/">
    <img src="https://github.com/Alex38Lyon/Synthese-PSM_LARRA/blob/main/Logos/Logo-ARSIP-Synthese-Topo.jpg" alt="Logo ARSIP" width="200px">
  </a>
</p>


Une convention a aussi été mise en place pour la gestion des points d'interrogation, avec la définition des différents champs :

- **Champ "Code"** : décrit le type de terminus. Il peut prendre les valeurs :
  - `A` : il suffit d'y aller et de continuer, pas d'obstacles  
  - `D` : Désobstruction nécessaire  
  - `E` : Escalade nécessaire  
  - `P` : Puits non descendu  
  - `Q` : non renseigné sur les topographies anciennes, c'est à voir/vérifier  
  - `S` : Siphon à plonger  
  - `T` : Trémie à désobstruer

- **Champ "Cavite"** : nom de la cavité concernée  
- **Champ "Reseau"** : partie de la cavité où se situe le point d'interrogation (pour le localiser rapidement sur les topographies)  
- **Champ "CA"** : rempli s'il y a présence de courant d'air, avec éventuellement des remarques/commentaires

**Exemple** :  
```text
point 3922.0 1660.0 continuation -attr Code Q -attr Cavite "GL102" -attr Reseau "Grand Chao" -text "Rivière à topographier" -attr CA "inconnu"
```

## Licence

L'ensemble de ces données est publié sous la licence libre Creative Commons CC BY-NC-ND 4.0 (Attribution, partage à l'identique et pas d'utilisation commerciale) :  
[https://creativecommons.org/licenses/by-nc-nd/4.0/](https://creativecommons.org/licenses/by-nc-nd/4.0/)

<p align="center">
  <a href="https://creativecommons.org/licenses/by-nc-nd/4.0/">
    <img src="https://mirrors.creativecommons.org/presskit/buttons/88x31/png/by-nc-nd.png" alt="Licence CC BY-NC-ND" width="100px">
  </a>
</p>

## Auteur de la base de données

Alexandre Pont (alexandre dot pont at yahoo dot fr) pour le compte de l'ARSIP

## Contact

Pour plus d'informations, vous pouvez contacter l'ARSIP : [https://www.arsip.fr/contactez-nous](https://www.arsip.fr/contactez-nous)

## Remerciements

Cette base de données est construite sur le modèle de celle des [massifs du Folly et de Criou](https://github.com/robertxa/Topographies-Samoens_Folly), développée par Xavier Robert,  
un grand merci pour le soutien actif.
