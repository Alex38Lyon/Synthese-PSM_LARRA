"""
    !---------------------------------------------------------!
    !                                                         !
    !                    TroX to Therion                      !
    !                                                         !
    !           Code to transform the .troX files             !
    !            Visual Topo into files that can              !
    !                  be used by Therion                     !
    !                                                         !
    !              Written by Alexandre Pont                  !
    !                                                         !
    !---------------------------------------------------------!

     ENGLISH :
     This code is to transform the .trox file from Visualtopo (http://vtopo.free.fr/)
     into files that can be read by Therion (http://therion.speleo.sk/).
     It reads .tro file and produce one .th file (file with survey data),
     and one thconfig file (file that is used to compile and build the survey with Therion).

Création Alex 2026 01 08


    TODOS : -....
"""

import xml.etree.ElementTree as ET  # noqa: I001
from collections import defaultdict, Counter
from pathlib import Path
from Lib.general_fonctions import Colors


#################################################################################################
def analyse_xml_balises(xml_path):
    """
    Analyse un fichier XML et affiche :
      - le nombre d'occurrences de chaque balise
      - pour chaque balise, les attributs rencontrés et leurs occurrences
      - le tout classé par type logique (Version, Mesures, Param, ...)
    """

    xml_path = Path(xml_path)

    if not xml_path.exists():
        raise FileNotFoundError(f"{Colors.ERROR}Fichier introuvable : {Colors.ENDC}{xml_path}")

    # ----------------------------
    # Définition des catégories
    # ----------------------------
    TAG_CATEGORIES = {
        "Version": {"version", "header", "metadata"},
        "Mesures": {"mesure", "measure", "value", "data", "record"},
        "Param": {"param", "parameter", "config", "setting"},
    }

    DEFAULT_CATEGORY = "Autres"

    # Inverse la table pour lookup rapide
    tag_to_category = {}
    for category, tags in TAG_CATEGORIES.items():
        for tag in tags:
            tag_to_category[tag] = category

    # ----------------------------
    # Chargement XML
    # ----------------------------
    tree = ET.parse(xml_path)
    root = tree.getroot()

    tag_counter = Counter()
    attributes_counter = defaultdict(Counter)

    # ----------------------------
    # Parcours XML
    # ----------------------------
    for elem in root.iter():
        tag = elem.tag
        tag_counter[tag] += 1

        for attr_name in elem.attrib:
            attributes_counter[tag][attr_name] += 1

    # ----------------------------
    # Regroupement par catégorie
    # ----------------------------
    categorized_tags = defaultdict(list)

    for tag in tag_counter:
        # Nettoyage éventuel namespace XML
        clean_tag = tag.split("}")[-1]

        category = tag_to_category.get(clean_tag, DEFAULT_CATEGORY)
        categorized_tags[category].append(tag)

    # ----------------------------
    # Affichage
    # ----------------------------
    print(f"{Colors.INFO}" + "=" * 80)
    print(f"{Colors.INFO}Analyse du fichier : {Colors.ENDC}{xml_path.name}")
    print(f"{Colors.INFO}" + "=" * 80)

    for category in sorted(categorized_tags.keys()):
        print(f"{Colors.YELLOW}## {category}{Colors.ENDC}")
        print(f"{Colors.INFO}" + "-" * 60)

        for tag in sorted(categorized_tags[category]):
            print(f"{Colors.BLUE}Balise <{Colors.ENDC}{tag}{Colors.BLUE}>\t{Colors.CYAN}Occurrences : {Colors.ENDC}{tag_counter[tag]}")

            if attributes_counter[tag]:
                print(f"\t{Colors.MAGENTA}Attributs :{Colors.ENDC}")
                for attr, count in attributes_counter[tag].most_common():
                    print(f"\t\t{Colors.MAGENTA}- {Colors.ENDC}{attr}{Colors.MAGENTA} : {Colors.ENDC}{count}")
            # else:
            #     print(f"\t{Colors.RED}Attributs : aucun{Colors.ENDC}")

    print(f"{Colors.INFO}Analyse terminée.{Colors.ENDC}")
