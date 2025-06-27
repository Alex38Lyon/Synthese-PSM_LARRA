
"""
#############################################################################################
#                                                                                       	#  
# Script pour convertir des données topographiques des formats .th .mak ou .dat de compass  #
#                           au format th et th2 de Therion                              	#
#                     by Alexandre PONT (alexandre_pont@yahoo.fr)                         	#
#                                                                                          	#
# Définir les différentes variables dans fichier config.ini                                 #
#                                                                                           #
# Usage : python pyCreateTh.py                                                              #
#         Commandes : pyCreateTh.py --help                                                  #
#                                                                                       	#  
#############################################################################################

Création Alex le 2025 06 09 :
    
Version 2025 06 16 :    Création fonction create_th_folders 
                        Ajout des fonctions pour mak et dat    
                                       
En cours :
    - trouver une solution pour les teams et les clubs manquants
    - tester la nouvelle version de DAT (CORRECTION2 et suivants)
    - comparer résultats Therion - Compass (Stat, kml, etc....)
    - intégrer .tro files d'après XRo
    - ajouter codes pour lat/long
    - créer fonction wall shot  pour faire habillage des th2 files, les jointures...
        - traiter les series avec 1 ou 2 stations
        - fiabiliser !
    - PB des cartouches et des échelles pour faire des pdf automatiquement
    - gérer les différentes options --proj (All, Plan, ....) adapter

"""

Version = "2025.06.26"  

#################################################################################################
#################################################################################################
import os, re, unicodedata, argparse, shutil, sys, time, math
from os.path import isfile, join, abspath, splitext
import numpy as np
import networkx as nx
import pandas as pd
pd.set_option('future.no_silent_downcasting', True)
from datetime import datetime
from collections import defaultdict
from copy import deepcopy
from alive_progress import alive_bar              # https://github.com/rsalmei/alive-progress	
from contextlib import redirect_stdout

from Lib.survey import SurveyLoader, NoSurveysFoundException
from Lib.therion import compile_template, compile_file, get_stats_from_log
from Lib.general_fonctions import setup_logger, Colors, safe_relpath, colored_help, read_config, select_file_tk_window, release_log_file
import Lib.global_data as globalData


#################################################################################################
configIni = "config.ini"       # Default config file name
debug_log = False              # Mode debug des messages


#################################################################################################
# Renommage des tableau pdFrame de station                                                      #
#################################################################################################
@pd.api.extensions.register_series_accessor("stationName")
class StationNameAccessor:
    def __init__(self, pandas_obj):
        self._obj = pandas_obj

    def __call__(self):
        return (
            self._obj
            .str.replace('[', '_d_', regex=False)
            .str.replace(']', '_f_', regex=False)
            .str.replace('@', '_a_', regex=False)
            .str.replace(' ', '_e_', regex=False)
            .str.replace('p', '_p_', regex=False)
        )


#################################################################################################
# Mise au format des noms                                                                       #
#################################################################################################
def sanitize_filename(th_name):
    """
    Cleans a string to make it compatible with filenames on Windows, Linux, and macOS.
    Replaces special and accented characters with compatible characters.
    Replaces parentheses with underscores and enforces proper casing.

    Args:
        th_name (str): The filename to clean.

    Returns:
        str: The cleaned and compatible string.
        
    """
    # Unicode normalization to replace accented characters with their non-accented equivalents
    th_name = unicodedata.normalize('NFKD', th_name).encode('ASCII', 'ignore').decode('ASCII')

    # Replace parentheses with underscores
    th_name = th_name.replace('(', '_').replace(')', '_')

    # Replace illegal characters with an underscore
    th_name = re.sub(r'[<>:"/\\|?*\']', '_', th_name)   # Illegal on Windows
    th_name = re.sub(r'\s+', '_', th_name)             # Spaces to underscores
    th_name = re.sub(r'[^a-zA-Z0-9._-]', '_', th_name) # Keep only allowed chars

    # Convert to lowercase, then capitalize the first letter
    # th_name = th_name.lower().capitalize()
    # th_name = th_name.capitalize()
    
    # Suppression des underscores en début et fin
    th_name = th_name.strip('_')

    return th_name or "default_filename"  # Avoid empty result


#################################################################################################
def copy_template_if_not_exists(template_path, destination_path):
    # Check if the destination folder exists
    try:
        if not os.path.exists(destination_path):
            # If the destination folder does not exist, copy the template
            shutil.copytree(template_path, destination_path)  
            log.info(f"The folder '{Colors.ENDC}{template_path}{Colors.GREEN}' has been copied to '{Colors.ENDC}{safe_relpath(destination_path)}{Colors.GREEN}'")
        else:
            log.warning(f"The folder '{Colors.ENDC}{safe_relpath(destination_path)}{Colors.WARNING}' already exists. No files were copied.")
    except Exception as e:
        log.critical(f"Copy template error: {Colors.ENDC}{e}")
        exit(0)    
  
        
#################################################################################################        
def add_copyright_header(file_path, copyright_text):
    # Lire le contenu du fichier
    with open(file_path, 'r', encoding="utf-8") as file:
        content = file.readlines()
    
    # Vérifier si le copyright est déjà présent
    if not any("copyright" in line.lower() for line in content):
        # Ajouter le copyright en en-tête
        content.insert(0, f"{copyright_text}\n")
        
        # Réécrire le fichier avec le copyright ajouté
        with open(file_path, 'w', encoding="utf-8") as file:
            file.writelines(content)        

        
#################################################################################################
def copy_file_with_copyright(th_file, destination_path, copyright_text):
    
    # Vérifier si le fichier existe
    if os.path.exists(th_file):
        # Créer le dossier de destination s'il n'existe pas
        os.makedirs(destination_path, exist_ok=True)
        
        # Copier le fichier vers le dossier de destination
        dest_file = os.path.join(destination_path, os.path.basename(th_file))
        shutil.copy(th_file, dest_file)
        
        # Ajouter le copyright dans l'en-tête si nécessaire
        add_copyright_header(dest_file, copyright_text)
        
        log.debug(f"File '{Colors.ENDC}{safe_relpath(th_file)}{Colors.GREEN}' has been copied to '{Colors.ENDC}{safe_relpath(destination_path)}{Colors.GREEN}' with the copyright header added.{Colors.ENDC}")
    else:
        log.error(f"The file .th does not exist {Colors.ENDC}{safe_relpath(th_file)}")
        globalData.error_count += 1
   
        
#################################################################################################
# Remplir les template avec les variables vers output_path                                      #                                                             #    
#################################################################################################
def update_template_files(template_path, variables, output_path):
    """
    Process a Therion template file by replacing variables.
    
    Args:
        template_path (str): Path to the original template file
        variables (dict): Dictionary of variables to replace
        output_path (str): Path for the new configuration file
        
    Returns:
        None
        
    """
    
    try:
        # Read the content of the template file
        with open(template_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Replace variables
        for var, value in variables.items():
            # Use regex to replace {variable} with its value
            pattern = r'\{' + re.escape(var) + r'\}'
            content = re.sub(pattern, str(value), content)
        
        # Write the new file
        with open(output_path, 'w', encoding='utf-8') as file:
            file.write(content)

        log.info(f"Update template successfully: {Colors.ENDC}{safe_relpath(output_path)}")

        # Delete the original template file
        os.remove(template_path)
    
    except FileNotFoundError:
        log.error(f"Template file {Colors.ENDC}{template_path}{Colors.ERROR} not found")
        globalData.error_count += 1
        
    except PermissionError:
        log.error(f"Insufficient permissions to write the file")
        globalData.error_count += 1
        
    except Exception as e:
        log.error(f"An error occurred (update_template_files): {Colors.ENDC}{e}")
        globalData.error_count += 1


#################################################################################################
def parse_therion_surveys(file_path):
    """
    Reads a Therion file and extracts survey names.
    
    Args:
        file_path (str): Path to the Therion file to parse
    
    Returns:
        list: List of survey names
        
    """
        
    survey_names = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            # Read all lines from the file
            lines = file.readlines()
            
            for line in lines:
                # Look for lines starting with survey
                line = line.strip()
                if line.startswith('survey ') and ' -title ' in line:
                    # Split the line and extract the survey name
                    start_index = line.find('survey ') + len('survey ')
                    end_index = line.find(' -title ')               
                    survey_name = line[start_index:end_index].strip()
                    survey_names.append(survey_name)
    
    except FileNotFoundError:
        log.error(f"File {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR} not found.{Colors.ENDC}")
        globalData.error_count += 1
        
    except PermissionError:
        log.error(f"Insufficient permissions to read {Colors.ENDC}{safe_relpath(file_path)}")
        globalData.error_count += 1
        
    except Exception as e:
        log.error(f"An error occurred (parse_therion_surveys): {Colors.ENDC}{e}{Colors.ERROR}, file: {Colors.ENDC}{safe_relpath(file_path)}")
        globalData.error_count += 1
        
    
    return survey_names


#################################################################################################
def str_to_bool(value):
    """
    Function to convert string to boolean
    """
    if isinstance(value, bool):
        return value
    if value.lower() in ('true', '1', 'yes', 'y'):
        return True
    elif value.lower() in ('false', '0', 'no', 'n'):
        return False
    else:
        raise argparse.ArgumentTypeError(f"{Colors.ERROR}Error: Invalid boolean value: {Colors.ENDC}{value}")

#################################################################################################
def convert_to_line_polaire_df(df_lines):
    """
    Convertit un DataFrame de lignes cartésiennes (x1, y1, x2, y2, name1, name2)
    en un DataFrame avec représentation polaire (x1, y1, azimut_deg, longueur, name1, name2).
    """
    try:
        # Forcer la conversion des colonnes numériques
        df_lines = df_lines.copy()  # évite de modifier l'original
        cols_to_float = ["x1", "y1", "x2", "y2"]
        for col in cols_to_float:
            df_lines[col] = pd.to_numeric(df_lines[col], errors="coerce")

        # Supprimer les lignes invalides (NaN après conversion)
        df_lines = df_lines.dropna(subset=cols_to_float)
        
        
        dx = df_lines["x2"] - df_lines["x1"]
        dy = df_lines["y2"] - df_lines["y1"]
        
        # Calcul de la longueur et de l'azimut
        length = np.hypot(dx, dy)
        azimut = (np.degrees(np.arctan2(dx, dy))) % 360

        if "group_id" in df_lines.columns:
            df_polaire = pd.DataFrame({
                "x1": df_lines["x1"],
                "y1": df_lines["y1"],
                "x2": df_lines["x2"],
                "y2": df_lines["y2"],
                "azimut_deg": azimut,
                "longueur": length,
                "name1": df_lines["name1"],
                "name2": df_lines["name2"],
                "group_id": df_lines["group_id"],
                "rank_in_group": df_lines["rank_in_group"],
            })
        else :    
            df_polaire = pd.DataFrame({
                "x1": df_lines["x1"],
                "y1": df_lines["y1"],
                "x2": df_lines["x2"],
                "y2": df_lines["y2"],
                "azimut_deg": azimut,
                "longueur": length,
                "name1": df_lines["name1"],
                "name2": df_lines["name2"],
            })

        return df_polaire

    except Exception as e:
        log.error(f"Issue in polar conversion: {Colors.ENDC}{e}")
        globalData.error_count += 1
        return pd.DataFrame()


#################################################################################################
def parse_xvi_file(th_name_xvi):
    """
    Parse un fichier .xvi et extrait les stations et les lignes.

    Args:
        th_name_xvi (str): chemin complet du fichier .xvi à lire.

    Returns:
        tuple:
            - stations (dict): dictionnaire des stations indexées par "x.y".
            - lines (list): liste des lignes [x1, y1, x2, y2, station1, station2].
            - x_bounds (tuple): (x_min, x_max)
            - y_bounds (tuple): (y_min, y_max)
            - ecarts (tuple): (x_ecart, y_ecart)
    """
    stations = {}
    lines = []
    splays = []

    with open(join(th_name_xvi), "r", encoding="utf-8") as f:
        xvi_content = f.read()
        xvi_stations, xvi_shots = xvi_content.split("XVIshots")

        # Extraction des stations
        for line in xvi_stations.split("\n"):
            match = re.search(r"{\s*(-?\d+\.\d+)\s*(-?\d+\.\d+)\s([^@]+)(?:@([^\s}]*))?\s*}", line)
            if match:
                x, y, station_number, namespace = match.groups()
                namespace_array = namespace.split(".") if namespace else []
                station = station_number
                if len(namespace_array) > 1:
                    station = "{}@{}".format(station_number, ".".join(namespace_array[0:-1]))
                if station != "." and station != "-":
                    stations[f"{x}.{y}"] = [x, y, station]

        # Calcul des bornes x et y
        x_values = [float(value[0]) for value in stations.values()]
        y_values = [float(value[1]) for value in stations.values()]
        x_min, x_max = min(x_values), max(x_values)
        y_min, y_max = min(y_values), max(y_values)
        x_ecart = x_max - x_min
        y_ecart = y_max - y_min
                    
        for line in xvi_shots.split("\n"):
            match = re.search(r"^\s*{\s*(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)(.*)}", line)
            if match:
                x1, y1, x2, y2, rest = match.groups()
                key1 = f"{x1}.{y1}"
                key2 = f"{x2}.{y2}"
                station1 = stations[key1][2] if key1 in stations else None
                station2 = stations[key2][2] if key2 in stations else None

                # Ajout de la ligne principale si les stations sont valides
                if station1 not in [".", "-", None] and station2 not in [".", "-", None]:
                    lines.append([x1, y1, x2, y2, station1, station2])
                else:
                    splays.append([x1, y1, x2, y2, station1, station2])

                # Vérifie s'il y a au moins 8 autres champs pour les splays
                additional_coords = re.findall(r"-?\d+\.\d+", rest)
                if len(additional_coords) >= 8:
                        splays.append([x1, y1, additional_coords[0],  additional_coords[1], station1, "-"])
                        # splays.append([x2, y2, additional_coords[2],  additional_coords[3], station2, "-"])
                        # splays.append([x2, y2, additional_coords[4],  additional_coords[5], station2, "-"])
                        splays.append([x1, y1, additional_coords[6],  additional_coords[7], station1, "-"])
    
    return stations, lines, splays, x_min, x_max, y_min, y_max, x_ecart, y_ecart

#################################################################################################
def assign_groups_and_ranks(df_lines):
    G = nx.Graph()
    for _, row in df_lines.iterrows():
        G.add_edge(row["name1"], row["name2"])

    used_edges = set()
    results = []
    equates = []  # Liste des (group_id, start_point, end_point)
    group_id = 0

    def walk_path(u, prev=None):
        path = []
        current = u
        while True:
            neighbors = [n for n in G.neighbors(current) if n != prev]
            if len(neighbors) != 1:
                break
            next_node = neighbors[0]
            edge = tuple(sorted((current, next_node)))
            if edge in used_edges:
                break
            used_edges.add(edge)
            path.append(edge)
            prev = current
            current = next_node
        return path

    start_nodes = [n for n in G.nodes if G.degree(n) != 2]

    for node in start_nodes:
        for neighbor in G.neighbors(node):
            edge = tuple(sorted((node, neighbor)))
            if edge in used_edges:
                continue
            used_edges.add(edge)
            path = [(node, neighbor)] + walk_path(neighbor, node)
            
            for rank, (n1, n2) in enumerate(path):
                match = df_lines[(df_lines["name1"] == n1) & (df_lines["name2"] == n2)]
                if match.empty:
                    match = df_lines[(df_lines["name1"] == n2) & (df_lines["name2"] == n1)]
                if not match.empty:
                    row = match.iloc[0].copy()
                    row["group_id"] = group_id
                    row["rank_in_group"] = rank
                    results.append(row)
                    if rank == 0:
                        start_point = n1
            end_point = path[-1][1] if path else start_point
            equates.append((group_id, str(start_point), str(end_point)))
            group_id += 1

    # Création du DataFrame principal
    df_result = pd.DataFrame(results)

    # Création du DataFrame equates
    df_equates = pd.DataFrame(equates, columns=["group_id", "start_point", "end_point"])
    df_equates["group_id"] = df_equates["group_id"].astype(int)
    df_equates["start_point"] = df_equates["start_point"].astype(str)
    df_equates["end_point"] = df_equates["end_point"].astype(str)

    # Ajout de la colonne max_rank
    max_ranks = df_result.groupby("group_id")["rank_in_group"].max().reset_index()
    max_ranks.rename(columns={"rank_in_group": "max_rank"}, inplace=True)
    max_ranks["max_rank"] = max_ranks["max_rank"].astype(int)
    df_equates = df_equates.merge(max_ranks, on="group_id", how="left")

    # Ajout de la colonne start_group (raccord entre start_point <-> end_point d'un autre groupe)
    end_to_group = df_equates[["end_point", "group_id"]].copy()
    end_to_group.rename(columns={"end_point": "start_point", "group_id": "start_group"}, inplace=True)
    end_to_group["start_point"] = end_to_group["start_point"].astype(str)
    df_equates = df_equates.merge(end_to_group, on="start_point", how="left")

    # Remplacer les NaN dans start_group par 0 (entier)
    df_equates["start_group"] = df_equates["start_group"].fillna(0).astype(int)

    return df_result, df_equates


#################################################################################################
def add_start_end_splays(df_splays_complet, df_equates):
    df_splays_new = df_splays_complet.copy()

    for _, row in df_equates.iterrows():
        group_id = row["group_id"]
        end_point = row["end_point"]
        start_point = row["start_point"]
        start_group = row["start_group"]

        # Vérifie si le end_point est déjà dans les splays
        mask = (df_splays_complet["name1"] == end_point) & (df_splays_complet["group_id"] == group_id)

        if not mask.any():
            # Trouver un splay existant du même groupe pour copier la structure
            splay_example = df_splays_complet[df_splays_complet["name1"] == end_point].copy()
            if not splay_example.empty:
                splay_example["group_id"] = group_id
                splay_example["rank_in_group"] = row["max_rank"] + 1
                ref_row = df_splays_complet[
                    (df_splays_complet["group_id"] == group_id) &
                    (df_splays_complet["rank_in_group"] == row["max_rank"] - 1)
                ]
                if not ref_row.empty:
                    splay_example["longueur_ref"] = ref_row.iloc[0]["longueur_ref"]
                    splay_example["bissectrice"] = ref_row.iloc[0]["bissectrice"]
                splay_example = splay_example.drop_duplicates()                    
                df_splays_new = pd.concat([df_splays_new, splay_example], ignore_index=True)
                # print(f"\n splay_example end add: {len(splay_example)}")   
                # print(splay_example)
                
        # Vérifie si le end_point est déjà dans les splays
        mask = (df_splays_complet["name1"] == start_point) & (df_splays_complet["group_id"] == start_group)
        if not mask.any():
            # Trouver un splay existant du même groupe pour copier la structure
            splay_example = df_splays_complet[df_splays_complet["name1"] == start_point].copy()
            if not splay_example.empty:
                splay_example["group_id"] = group_id
                splay_example["rank_in_group"] = 0
                ref_row = df_splays_complet[
                    (df_splays_complet["group_id"] == start_group) &
                    (df_splays_complet["rank_in_group"] == 0)
                ]
                if not ref_row.empty:
                    splay_example["longueur_ref"] = ref_row.iloc[0]["longueur_ref"]
                    splay_example["bissectrice"] = ref_row.iloc[0]["bissectrice"]
                splay_example = splay_example.drop_duplicates()                    
                df_splays_new = pd.concat([df_splays_new, splay_example], ignore_index=True)
                # print(f"\n splay_example start add : {len(splay_example)}")   
                # print(splay_example)
                
            # else:
                # Aucun splay existant pour ce group_id : on ignore ou on crée un modèle vide
                # print(f"Aucun modèle de splay pour group_id {group_id} — point {end_point} ignoré.")
                
    return df_splays_new



def align_points(smoothX1, smoothY1, X, Y, smoothX2, smoothY2):
    # Vecteurs d'origine vers smooth1 et smooth2
    dx1, dy1 = smoothX1 - X, smoothY1 - Y
    dx2, dy2 = smoothX2 - X, smoothY2 - Y

    # Vecteur directeur initial entre smooth1 et smooth2
    dir_x, dir_y = smoothX2 - smoothX1, smoothY2 - smoothY1

    # Normalisation du vecteur directeur
    length = math.hypot(dir_x, dir_y)
    if length == 0:
        raise ValueError("Les deux points smooth sont confondus, la direction est indéfinie.")

    dir_x /= length
    dir_y /= length

    # Calcul des distances originales depuis le centre
    dist1 = math.hypot(dx1, dy1)
    dist2 = math.hypot(dx2, dy2)

    # Recalcule des points alignés, en gardant les distances depuis le point central
    _smoothX1 = X + dir_x * dist1 * globalData.kSmooth
    _smoothY1 = Y + dir_y * dist1 * globalData.kSmooth

    _smoothX2 = X - dir_x * dist2 * globalData.kSmooth
    _smoothY2 = Y - dir_y * dist2 * globalData.kSmooth

    return (_smoothX1, _smoothY1), (_smoothX2, _smoothY2)



#################################################################################################
def wall_construction_smoothed(df_lines, df_splays, x_min, x_max, y_min, y_max):

   
    th2_walls=[]
    _list = ""
    
    # pd.set_option('display.max_rows', None)
    # pd.set_option('display.max_columns', None)
    # pd.set_option('display.width', None)
    # pd.set_option('display.max_colwidth', None)
    # print(f"\n df_lines: {len(df_lines)} :\n{df_lines}")   
    # print(f"\n df_splays: {len(df_splays)} :\n{df_splays}")   

    
    if len(df_lines) <= 2 or len(df_splays) <= 2:
        return th2_walls, 0, 0, 0, 0


    df_lines, df_equates = assign_groups_and_ranks(df_lines)
   
    # Conversion en polaire
    df_lines_polaire = convert_to_line_polaire_df(df_lines)
    df_splays_polaire = convert_to_line_polaire_df(df_splays)
    
    df_temp = df_lines_polaire.copy()
    df_temp['rank_in_group_prev'] = df_temp['rank_in_group'] + 1

    # Fusionner pour récupérer l'azimut précédent
    df_lines_polaire = df_lines_polaire.merge(
        df_temp[['group_id', 'rank_in_group_prev', 'azimut_deg']],
        left_on=['group_id', 'rank_in_group'],
        right_on=['group_id', 'rank_in_group_prev'],
        how='left',
        suffixes=('', '_prev')
    )

    # Renommer et nettoyer
    df_lines_polaire['azimut_prev_deg'] = df_lines_polaire['azimut_deg_prev']
    df_lines_polaire = df_lines_polaire.drop(['rank_in_group_prev', 'azimut_deg_prev'], axis=1)
    df_lines_polaire['azimut_prev_deg'] = df_lines_polaire['azimut_prev_deg'].fillna(df_lines_polaire['azimut_deg'])
    df_lines_polaire['bissectrice'] = (df_lines_polaire['azimut_deg'] + df_lines_polaire['azimut_prev_deg']) / 2
    
    
    # print(f"\n df_lines_polaire: {len(df_lines_polaire)} :\n{df_lines_polaire}")   
    # print(f"\n df_equates: {len(df_equates)} :\n{df_equates}")   

    # Index des lignes polaires par station name1
    index_by_station = df_lines_polaire.set_index("name1")[["bissectrice", "longueur"]]

    # Jointure pour récupérer azimut_ref et longueur_ref
    _df_splays_complet = df_splays_polaire.copy()
    _df_splays_complet = _df_splays_complet.join(index_by_station, on="name1", rsuffix="_ref")
    
    # Remplacer les valeurs manquantes par défaut : azimut_ref = 0, longueur_ref = 0
    _df_splays_complet["bissectrice"] = _df_splays_complet["bissectrice"].fillna(0)
    _df_splays_complet["longueur_ref"] = _df_splays_complet["longueur_ref"].fillna(0)
    
    df_splays_complet = _df_splays_complet.merge(
        df_lines[["name1", "group_id", "rank_in_group"]],
        on="name1",
        how="left"
    )
    
    missing_mask = df_splays_complet["group_id"].isna()
    
    for idx, row in df_splays_complet[missing_mask].iterrows():
        name1 = row["name1"]
        match = df_lines_polaire[df_lines_polaire["name2"] == name1]
        if not match.empty:   
            group_id = match["group_id"].values[0]
            max_rank = df_lines_polaire[df_lines_polaire["group_id"] == group_id]["rank_in_group"].max()
                    
            df_splays_complet.at[idx, "bissectrice"] = match["azimut_deg"].values[0]
            df_splays_complet.at[idx, "longueur_ref"] = match["longueur"].values[0]
            df_splays_complet.at[idx, "group_id"] = group_id
            df_splays_complet.at[idx, "rank_in_group"] = max_rank + 1

    df_splays_complet = add_start_end_splays(df_splays_complet, df_equates)
    
    df_splays_complet = df_splays_complet.sort_values(by=["group_id", "rank_in_group"]).reset_index(drop=True)
    
    df_splays_complet["delta_azimut"] = df_splays_complet["bissectrice"] - df_splays_complet["azimut_deg"]


    # Calcul de la projection : sin(delta azimut) * longueur_ref
    def calc_projection(row):
        try:
            delta = math.radians(row["bissectrice"] - row["azimut_deg"])
            return math.sin(delta) * row["longueur"]
        
        except:
            return None

    df_splays_complet["proj"] = df_splays_complet.apply(calc_projection, axis=1)
    df_splays_complet["group_id"] = df_splays_complet["group_id"].astype(int)
    df_splays_complet["rank_in_group"] = df_splays_complet["rank_in_group"].astype(int)
    
    # print(f"\n df_splays_complet: {len(df_splays_complet)} :\n{df_splays_complet}")   

    # Filtrage des extrêmes min/max par station name1
    df_valid_proj = df_splays_complet.dropna(subset=["proj"])
    
    # print(f"\n df_splays_complet: {len(df_splays_complet)} :\n{df_splays_complet}")   
   
    idx_max = df_valid_proj.groupby(["group_id", "rank_in_group"])["proj"].idxmax()
    df_result01 = df_valid_proj.loc[idx_max].reset_index(drop=True)   
    # idx_max = df_valid_proj.groupby("name1")["proj"].idxmax()
    df_result01 = pd.concat([df_valid_proj.loc[idx_max]]).drop_duplicates() 
    df_sorted01 = df_result01.sort_values(by=["group_id", "rank_in_group"]).reset_index(drop=True)
    
    idx_min = df_valid_proj.groupby(["group_id", "rank_in_group"])["proj"].idxmin()
    df_result02 = df_valid_proj.loc[idx_min].reset_index(drop=True)  
    # idx_min = df_valid_proj.groupby("name1")["proj"].idxmin()
    df_result02 = pd.concat([df_valid_proj.loc[idx_min]]).drop_duplicates()    
    df_sorted02 = df_result02.sort_values(by=["group_id", "rank_in_group"]).reset_index(drop=True)
    
    # Affichage de contrôle
    # print(f"\n df_sorted01: {len(df_sorted01)} :\n{df_sorted01}")   
    # print(f"\n df_sorted02: {len(df_sorted02)} :\n{df_sorted02}")  
    # print(f"\n idx_min: {len(idx_min)} :\n{idx_min}")    
    
    smooth02 = []
    smooth01 = []
    
    for gid in sorted(df_sorted01["group_id"].unique()):
        df_group = df_sorted02[df_sorted02["group_id"] == gid]
    
        # _list += f"line wall\n" 
        _linex2 = 0.0   
        _liney2 = 0.0
         
        for line in df_group.itertuples(index=False):
            X = line.x2 + (- line.x2 + _linex2) / 2      
            Y = line.y2 + (- line.y2 + _liney2) / 2      
            if _linex2 == 0.0  and _liney2 == 0.0:
                row = {
                    'smoothX1': None,
                    'smoothY1': None,
                    'smoothX2': None,
                    'smoothY2': None,
                    'X': line.x2,
                    'Y': line.y2,
                    'Jump': False,
                }
            else :
                row = {
                    'smoothX1': X,
                    'smoothY1': Y,
                    'smoothX2': X,
                    'smoothY2': Y,
                    'X': line.x2,
                    'Y': line.y2,
                    'Jump': False,
                }
                
            _linex2 = line.x2   
            _liney2 = line.y2
            smooth02.append(row)
            if line.x2 > x_max: x_max = line.x2
            if line.x2 < x_min: x_min = line.x2
            if line.y2 > y_max: y_max = line.y2
            if line.y2 < y_min: y_min = line.y2
        row = {
            'smoothX1': None,
            'smoothY1': None,
            'smoothX2': None,
            'smoothY2': None,
            'X': None,
            'Jump': True,
        }
        smooth02.append(row)
        
        _linex2 = 0.0   
        _liney2 = 0.0
        
        df_group = df_sorted01[df_sorted01["group_id"] == gid]
            
        for line in df_group.itertuples(index=False):
            X = line.x2 + (- line.x2 + _linex2) / 2      
            Y = line.y2 + (- line.y2 + _liney2) / 2      
            if _linex2 == 0.0  and _liney2 == 0.0:
                row = {
                    'smoothX1': None,
                    'smoothY1': None,
                    'smoothX2': None,
                    'smoothY2': None,
                    'X': line.x2,
                    'Y': line.y2,
                    'Jump': False,
                }
            else :
                row = {
                    'smoothX1': X,
                    'smoothY1': Y,
                    'smoothX2': X,
                    'smoothY2': Y,
                    'X': line.x2,
                    'Y': line.y2,
                    'Jump': False,
                }
                
            _linex2 = line.x2   
            _liney2 = line.y2
            smooth01.append(row)
            if line.x2 > x_max: x_max = line.x2
            if line.x2 < x_min: x_min = line.x2
            if line.y2 > y_max: y_max = line.y2
            if line.y2 < y_min: y_min = line.y2
        
        row = {
            'smoothX1': None,
            'smoothY1': None,
            'smoothX2': None,
            'smoothY2': None,
            'X': None,
            'Jump': True,
        }
        smooth01.append(row)
           
    df_smooth01 = pd.DataFrame(smooth01)
    df_smooth02 = pd.DataFrame(smooth02)
    
    # print(f"\n df_sorted01: {len(df_sorted01)} :\n{df_sorted01}")   
    # print(f"\n df_smooth01: {len(df_smooth01)} :\n{df_smooth01}")  
    
    if len(df_smooth01) > 1:
        _list = "line wall -reverse on\n"
    
        for i in range(len(df_smooth01) - 1):
            row_current = df_smooth01.iloc[i]
            row_next = df_smooth01.iloc[i + 1]
            
            if row_current['Jump'] == True :
                _list +="\tsmooth off\nendline\n\nline wall -reverse on\n"
                continue
            if pd.isna(row_current[['smoothX2', 'smoothY2', 'X', 'Y']]).any() or pd.isna(row_next[['smoothX1', 'smoothY1']]).any():
                _list += f"\t{row_current['X']} {row_current['Y']}\n"
                continue

            result = align_points( 
                smoothX1=row_next['smoothX1'],
                smoothY1=row_next['smoothY1'],
                X=row_current['X'],
                Y=row_current['Y'],
                smoothX2=row_current['smoothX2'],
                smoothY2=row_current['smoothY2']
            )

            if result:
                (_sx1, _sy1), (_sx2, _sy2) = result
                df_smooth01.at[i+1, 'smoothX1'] = _sx2
                df_smooth01.at[i+1, 'smoothY1'] = _sy2
                df_smooth01.at[i, 'smoothX2'] = _sx1
                df_smooth01.at[i, 'smoothY2'] = _sy1
            
            _list += f"\t{row_current['smoothX1']:.2f} {row_current['smoothY1']:.2f} {row_current['smoothX2']:.2f} {row_current['smoothY2']:.2f} {row_current['X']} {row_current['Y']}\n"
        
        _list += "\tsmooth off\nendline\n\nline wall\n"
            
        
        for i in range(len(df_smooth02) - 1):
            row_current = df_smooth02.iloc[i]
            row_next = df_smooth02.iloc[i + 1]

            # Vérifie qu'aucune valeur utilisée n'est NaN
            if row_current['Jump'] == True :
                _list +="\tsmooth off\nendline\n\nline wall\n"
                continue
            if pd.isna(row_current[['smoothX2', 'smoothY2', 'X', 'Y']]).any() or pd.isna(row_next[['smoothX1', 'smoothY1']]).any():
                _list += f"\t{row_current['X']} {row_current['Y']}\n"
                continue

            result = align_points( 
                smoothX1=row_next['smoothX1'],
                smoothY1=row_next['smoothY1'],
                X=row_current['X'],
                Y=row_current['Y'],
                smoothX2=row_current['smoothX2'],
                smoothY2=row_current['smoothY2']
            )

            if result:
                (_sx1, _sy1), (_sx2, _sy2) = result
                df_smooth02.at[i+1, 'smoothX1'] = _sx2
                df_smooth02.at[i+1, 'smoothY1'] = _sy2
                df_smooth02.at[i, 'smoothX2'] = _sx1
                df_smooth02.at[i, 'smoothY2'] = _sy1
            
            _list += f"\t{row_current['smoothX1']:.2f} {row_current['smoothY1']:.2f} {row_current['smoothX2']:.2f} {row_current['smoothY2']:.2f} {row_current['X']} {row_current['Y']}\n"
        
        _list += "\tsmooth off\nendline\n"
    
    th2_walls.append(globalData.th2wall.format(list = _list))
        
    return th2_walls, x_min, x_max, y_min, y_max


#################################################################################################



################################################################################################# 
# Création des dossiers à partir d'un th file                                                   #
#################################################################################################   
def create_th_folders(ENTRY_FILE, 
                    PROJECTION = "all", 
                    TARGET = "None", 
                    FORMAT = "th2", 
                    SCALE = "500", 
                    UPDATE = False, 
                    CONFIG_PATH = "",
                    totReadMeError = "") :  
    """
    Création des dossiers et fichiers à partir d'un fichier .th
    
    Args:
        ENTRY_FILE (str): Le chemin vers le fichier .th d'entrée.
        PROJECTION (str): Le type de projection (Plan, Extended, All).
        TARGET (str): Le nom de la cible (scrap) si différent du nom du fichier d'entrée.
        FORMAT (str): Le format de sortie (th2 ou plt).
        SCALE (str): L'échelle pour les exports th2.
        UPDATE (bool): Le mode de mise à jour.
        CONFIG_PATH (str): Le chemin vers le fichier de configuration.
        
    Returns:    
        True or False
        
    """

    threads = []
    TH_NAME = sanitize_filename(os.path.splitext(os.path.basename(ENTRY_FILE))[0])
    DEST_PATH = os.path.dirname(ENTRY_FILE) + "/" + TH_NAME
    ABS_PATH = os.path.dirname(ENTRY_FILE)
    shortCurentFile = safe_relpath(ENTRY_FILE)
    
    log.debug(f"ENTRY_FILE: {ENTRY_FILE}") 
    log.debug(f"PROJECTION: {PROJECTION}") 
    log.debug(f"TARGET: {TARGET}") 
    log.debug(f"FORMAT: {FORMAT}")     
    log.debug(f"SCALE: {SCALE}")
    log.debug(f"TH_NAME: {TH_NAME}")
    log.debug(f"DEST_PATH: {DEST_PATH}")
    log.debug(f"ABS_PATH: {ABS_PATH}")  
          
    # if PROJECTION.lower() != "plan" and PROJECTION.lower() != "extended" and PROJECTION.lower() != "all":
    #     log.critical(f"Sorry, projection '{Colors.ENDC}{PROJECTION}{Colors.ERROR}' not yet implemented{Colors.ENDC}")
    #     # exit(1)
    
    if not os.path.isfile(ENTRY_FILE):
        log.critical(f"The Therion file didn't exist: {Colors.ENDC}{shortCurentFile}")
        exit(1)

    if FORMAT not in ["th2", "plt"]:
        log.critical(f"Please choose a supported format: th2, plt{Colors.ENDC}")
        exit(1)

    # Normalise name, namespace, key, file path
    log.info(f"Parsing survey entry file: {Colors.ENDC}{shortCurentFile}")

    survey_list = parse_therion_surveys(ENTRY_FILE)
    
    if TARGET == "None" :
        if len(survey_list) > 1 : 
            log.critical(f"Multiple surveys were found, not yet implemented{Colors.ENDC}")
            exit(1)  
    
    TARGET = survey_list[0]
    
    log.info(f"Parsing survey target: {Colors.ENDC}{TARGET}")        
    
    loader = SurveyLoader(ENTRY_FILE)
    survey = loader.get_survey_by_id(survey_list[0])
    
    if not survey:
        raise NoSurveysFoundException(f"No survey found with that selector")
    
   
    if UPDATE : 
        DEST_PATH = os.path.dirname(args.file)
        log.info(f"Update th2 files: {Colors.ENDC}{DEST_PATH}")
        log.debug(f"\t{Colors.BLUE}survey_file :  {Colors.ENDC} {args.file}")
        log.debug(f"\t{Colors.BLUE}ENTRY_FILE:    {Colors.ENDC} {ENTRY_FILE}") 
        log.debug(f"\t{Colors.BLUE}PROJECTION:    {Colors.ENDC} {PROJECTION}") 
        log.debug(f"\t{Colors.BLUE}TARGET:        {Colors.ENDC} {TARGET}") 
        # log.info(f"\t{Colors.BLUE}OUTPUT:        {Colors.ENDC} {OUTPUT}") 
        log.debug(f"\t{Colors.BLUE}FORMAT:        {Colors.ENDC} {FORMAT}")     
        log.debug(f"\t{Colors.BLUE}SCALE:         {Colors.ENDC} {SCALE}")
        log.debug(f"\t{Colors.BLUE}TH_NAME:       {Colors.ENDC} {TH_NAME}")
        log.debug(f"\t{Colors.BLUE}DEST_PATH:     {Colors.ENDC} {DEST_PATH}")
        log.debug(f"\t{Colors.BLUE}ABS_PATH:      {Colors.ENDC} {ABS_PATH}")
    
    
    #################################################################################################    
    # Copy template folders                                                                         #
    #################################################################################################
    if not UPDATE: 
        log.debug(f"Copy template folder and adapte it")
        copy_template_if_not_exists(globalData.templatePath, DEST_PATH)
        copy_file_with_copyright(ENTRY_FILE, DEST_PATH + "/Data", globalData.Copyright)
    
        
    #################################################################################################                   
    # Produce the parsable XVI file                                                                 #
    #################################################################################################      
    log.info(f"Compiling 2D XVI file: {Colors.ENDC}{TH_NAME}")
    
    if UPDATE: 
        template_args = {
            "th_file": DEST_PATH + "/" + TH_NAME + ".th",  
            "selector": survey.therion_id,
            "th_name": DEST_PATH + "/" + TH_NAME, 
            "scale": int(int(SCALE)/10),
        }

    else :
        template_args = {
            "th_file": DEST_PATH + "/Data/" + TH_NAME + ".th",  
            "selector": survey.therion_id,
            "th_name": DEST_PATH + "/Data/" + TH_NAME, 
            "XVIscale": globalData.XVIScale,
        }

    logfile, tmpdir, totReadMeError = compile_template(globalData.thconfigTemplate, template_args, totReadMeError, cleanup=False, therion_path=globalData.therionPath)
    
    shutil.rmtree(tmpdir)  
    
    if logfile == "Therion error":
        # log.error(f"Therion error in: {Colors.ENDC}{TH_NAME}")   
        flagErrorCompile = True
        stat = {"length": 0, "depth": 0}
    else : 
        flagErrorCompile = False
        stat = get_stats_from_log(logfile)
     
         
    #################################################################################################    
    # Update files                                                                                  #
    #################################################################################################
    if not UPDATE: 
        
        proj = args.proj.lower()
        values = {
            "none":     ("# ", "# ", "# "),
            "plan":     ("",  "",  "# "),
            "extended": ("",  "# ", ""),
        }

        maps, plan, extended = values.get(proj, ("", "", ""))
        
        totdata = globalData.totfile.format(
            TH_NAME = TH_NAME, 
            ERR = "# " if flagErrorCompile else "",
            Plan = plan,
            Extended = extended,
            Maps = maps)
        
        # Adapte templates 
        config_vars = {
            'fileName': TH_NAME,
            'caveName': TH_NAME.replace("_", " "),
            'Author': globalData.Author,
            'Copyright': globalData.Copyright,
            'Scale' : SCALE,
            'Target' : TARGET,
            'mapComment' : globalData.mapComment,
            'club' : globalData.club,
            'thanksto' : globalData.thanksto.replace("_", r"\_"),
            'datat' : globalData.datat.replace("_", r"\_"),
            'wpage' : globalData.wpage.replace("_", r"\_"), 
            'cs' : globalData.cs,
            'configPath' : CONFIG_PATH,
            'totData' : totdata,
            'maps' : maps,
            'plan': plan,
            'XVIscale':globalData.XVIScale,
            'extended': extended,
            'XVIscale':globalData.XVIScale,
            'other_scraps_plan' : "",
            'file_info' : f'# File generated by pyCreateTh.py version: {Version} date: {datetime.now().strftime("%Y.%m.%d %H:%M:%S")}',
        }
        
        update_template_files(DEST_PATH + '/template.thconfig', config_vars, DEST_PATH + '/' +  TH_NAME + '.thconfig')
        update_template_files(DEST_PATH + '/template-tot.th', config_vars, DEST_PATH + '/' +  TH_NAME + '-tot.th')
        update_template_files(DEST_PATH + '/template-readme.md', config_vars, DEST_PATH + '/' +  TH_NAME + '-readme.md')   
   
    #################################################################################################    
    # Parse the Plan XVI file                                                                       #
    #################################################################################################
    other_scraps_plan = ""
    if PROJECTION.lower() == "plan" or PROJECTION.lower() == "all" and not flagErrorCompile :
        if UPDATE: 
            th_name_xvi =  DEST_PATH + "/" + TH_NAME + "-Plan.xvi" 
        else :     
            th_name_xvi =  DEST_PATH + "/Data/" + TH_NAME + "-Plan.xvi" 

        log.info(f"Parsing Plan XVI file: {Colors.ENDC}{safe_relpath(th_name_xvi)}")

        stations = {}
        lines = []
        
        stations, lines, splays, x_min, x_max, y_min, y_max, x_ecart, y_ecart = parse_xvi_file(th_name_xvi)
        
        # df_stations = pd.DataFrame.from_dict(stations, orient='index')
        df_lines = pd.DataFrame(lines, columns=["x1", "y1", "x2", "y2", "name1", "name2"])
        df_splays = pd.DataFrame(splays, columns=["x1", "y1", "x2", "y2", "name1", "name2"]).drop_duplicates()
        
        df_splays["is_zero_length"] = (df_splays["x1"] == df_splays["x2"]) & (df_splays["y1"] == df_splays["y2"])
        

        # Identifier les groupes avec au moins un splay non nul
        non_zero_groups = df_splays.loc[~df_splays["is_zero_length"], ["name1", "name2"]]
        non_zero_group_keys = set(tuple(x) for x in non_zero_groups.to_numpy())
       
        def keep_row2(row):
            if not row["is_zero_length"]:
                return True
            return (row["name1"], row["name2"]) in non_zero_group_keys


        df_splays = df_splays[df_splays.apply(keep_row2, axis=1)]

        # Supprimer la colonne temporaire si elle existe
        if "is_zero_length" in df_splays.columns:
            df_splays = df_splays.drop(columns="is_zero_length")
    
        th2_walls = []
        
        if globalData.wallLineInTh2 :
            th2_walls,  x_min, x_max, y_min, y_max = wall_construction_smoothed(df_lines, df_splays, x_min, x_max, y_min, y_max)
            
        
        if UPDATE: 
            th2_name = DEST_PATH + "/" + TH_NAME
        else : 
            th2_name = DEST_PATH + "/Data/" + TH_NAME
            
        output_path = f'{th2_name}-Plan.{FORMAT}'
        
        scrap_to_add = int(len(stations)/globalData.stationByScrap)-1

        # log.debug(stations)

        log.info(f"Writing output to: {Colors.ENDC}{safe_relpath(output_path)}")

        # Write TH2
        if FORMAT == "th2":
            seen = set()
            th2_lines = []
            th2_points = []
            th2_names = []
            other_scraps_plan = f"\tSP-{TARGET}_01\n\tbreak\n"
              
            for line in lines:
                th2_lines.append(globalData.th2Line.format(x1=line[0], y1=line[1], x2=line[2], y2=line[3]))
                coords1 = "{}.{}".format(line[0], line[1])
                
                if coords1 not in seen:
                    seen.add(coords1)
                    th2_points.append(globalData.th2Point.format(x=line[0], y=line[1], station=line[4]))
                    th2_names.append(globalData.th2Name.format(x=line[0], y=line[1], station=line[4]))
                coords2 = "{}.{}".format(line[2], line[3])
                
                if "{}.{}".format(line[2], line[3]) not in seen:
                    seen.add(coords2)
                    if line[5] != None:
                        th2_points.append(globalData.th2Point.format(x=line[2], y=line[3], station=line[5]))
                        th2_names.append(globalData.th2Name.format(x=line[2], y=line[3], station=line[5]))


            if isfile(output_path):
                log.warning(f"{Colors.ENDC}{os.path.basename(output_path)}{Colors.WARNING} file already exists - overwrite")

            if True :
                # name = TARGET, 
                log.debug(f"Therion output path: {Colors.ENDC}{safe_relpath(output_path)}")

                with open(str(output_path), "w+") as f:
                    f.write(globalData.th2FileHeader)
                    f.write(globalData.th2File.format(
                            name = TARGET,
                            Copyright = globalData.Copyright,
                            Copyright_Short = globalData.CopyrightShort,
                            points="\n".join(th2_points),
                            lines="\n".join(th2_lines) if globalData.linesInTh2 else "",
                            walls="\n".join(th2_walls) if globalData.wallLineInTh2 else "",
                            names="\n".join(th2_names) if globalData.stationNamesInTh2 else "",
                            projection="plan",
                            projection_short="P",
                            author=globalData.Author,
                            year=datetime.now().year,
                            version = Version,
                            date=datetime.now().strftime("%Y.%m.%d-%H:%M:%S"),
                            X_Min=x_min*1.2, 
                            X_Max=x_max*1.2, 
                            Y_Min=y_min*1.2, 
                            Y_Max=y_max*1.2,
                            X_Max_X_Min =x_ecart,
                            Y_Max_Y_Min =y_ecart,
                            insert_XVI = "{" + stations[next(iter(stations))][0] + "1 1.0} {" 
                                                + stations[next(iter(stations))][1] + " "
                                                + stations[next(iter(stations))][2] +"} "
                                                + os.path.basename(th_name_xvi) + " 0 {}",                         
                            )
                    )
                    if scrap_to_add >= 1 :     
                        for i in range(scrap_to_add):
                            f.write(globalData.th2Scrap.format(
                                name=TARGET,
                                projection="plan",
                                projection_short="P",
                                author=globalData.Author,
                                year=datetime.now().year,
                                Copyright_Short = globalData.CopyrightShort,
                                num=f"{i+2:02}",                         
                                )
                            )
                            

    #################################################################################################    
    # Parse the Extended XVI file                                                                   #
    #################################################################################################
    other_scraps_extended = ""
    if PROJECTION.lower() == "extended" or PROJECTION.lower() == "all" and not flagErrorCompile :
        if UPDATE: 
            th_name_xvi =  DEST_PATH + "/" + TH_NAME + "-Extended.xvi" 
        else :
            th_name_xvi =  DEST_PATH + "/Data/" + TH_NAME + "-Extended.xvi" 

        log.info(f"Parsing extended XVI file:\t{Colors.ENDC}{safe_relpath(th_name_xvi)}")

        # Parse the Extended XVI file
        stations = {}
        lines = []
        
        stations, lines, splays, x_min, x_max, y_min, y_max, x_ecart, y_ecart = parse_xvi_file(th_name_xvi)
        
        # df_stations = pd.DataFrame.from_dict(stations, orient='index')
        df_lines = pd.DataFrame(lines, columns=["x1", "y1", "x2", "y2", "name1", "name2"])
        df_splays = pd.DataFrame(splays, columns=["x1", "y1", "x2", "y2", "name1", "name2"]).drop_duplicates()

        df_splays["is_zero_length"] = (df_splays["x1"] == df_splays["x2"]) & (df_splays["y1"] == df_splays["y2"])

        # Identifier les groupes avec au moins un splay non nul
        non_zero_groups = df_splays.loc[~df_splays["is_zero_length"], ["name1", "name2"]]
        non_zero_group_keys = set(tuple(x) for x in non_zero_groups.to_numpy())
       
        def keep_row(row):
            if not row["is_zero_length"]:
                return True
            return (row["name1"], row["name2"]) in non_zero_group_keys

        df_splays = df_splays[df_splays.apply(keep_row, axis=1)]

        # Supprimer la colonne temporaire si elle existe
        if "is_zero_length" in df_splays.columns:
            df_splays = df_splays.drop(columns="is_zero_length")
        
        th2_walls = []
        
        if globalData.wallLineInTh2 :
            th2_walls, x_min, x_max, y_min, y_max, = wall_construction_smoothed(df_lines, df_splays, x_min, x_max, y_min, y_max)
            

        if UPDATE:
            th2_name = DEST_PATH + "/" + TH_NAME
        else :
            th2_name = DEST_PATH + "/Data/" + TH_NAME
            
        output_path = f'{th2_name}-Extended.{FORMAT}'

        scrap_to_add = int(len(stations)/globalData.stationByScrap)-1
        
        log.info(f"Writing output to: {Colors.ENDC}{safe_relpath(output_path)}")

        # Write TH2
        if FORMAT == "th2":

            seen = set()
            th2_lines = []
            th2_points = []
            th2_names = []
            
            other_scraps_extended = f"\tSC-{TARGET}_01\n\tbreak\n"
            
            for line in lines:
                th2_lines.append(globalData.th2Line.format(x1=line[0], y1=line[1], x2=line[2], y2=line[3]))
                coords1 = "{}.{}".format(line[0], line[1])
                
                if coords1 not in seen:
                    seen.add(coords1)
                    th2_points.append(globalData.th2Point.format(x=line[0], y=line[1], station=line[4]))
                    th2_names.append(globalData.th2Name.format(x=line[0], y=line[1], station=line[4]))
                coords2 = "{}.{}".format(line[2], line[3])
                
                if "{}.{}".format(line[2], line[3]) not in seen:
                    seen.add(coords2)
                    if line[5] != None:
                        th2_points.append(globalData.th2Point.format(x=line[2], y=line[3], station=line[5]))
                        th2_names.append(globalData.th2Name.format(x=line[2], y=line[3], station=line[5]))


            if isfile(output_path):
                log.warning(f"{Colors.ENDC}{os.path.basename(output_path)}{Colors.WARNING} file already exists - overwrite")
            
            if True :
                log.debug(f"Therion output path :\t{Colors.ENDC}{output_path}")
                    
                with open(str(output_path), "w+") as f:
                    f.write(globalData.th2FileHeader)
                    f.write(globalData.th2File.format(
                            name = TARGET,
                            Copyright = globalData.Copyright,
                            Copyright_Short = globalData.CopyrightShort,
                            points="\n".join(th2_points),
                            lines="\n".join(th2_lines) if globalData.linesInTh2 else "",
                            walls="\n".join(th2_walls) if globalData.wallLineInTh2 else "",
                            names="\n".join(th2_names) if globalData.stationNamesInTh2 else "",
                            projection="extended",
                            projection_short="C",
                            author=globalData.Author,
                            year=datetime.now().year,
                            version = Version,
                            date=datetime.now().strftime("%Y.%m.%d-%H:%M:%S"),
                            X_Min=x_min*1.2, 
                            X_Max=x_max*1.2, 
                            Y_Min=y_min*1.2, 
                            Y_Max=y_max*1.2,
                            X_Max_X_Min =x_ecart,
                            Y_Max_Y_Min =y_ecart,
                            insert_XVI = "{" + stations[next(iter(stations))][0] + "1 1.0} {" 
                                                + stations[next(iter(stations))][1] + " "
                                                + stations[next(iter(stations))][2] +"} "
                                                + os.path.basename(th_name_xvi) + " 0 {}",                         
                        )
                    )
                    if scrap_to_add >= 1 :     
                        for i in range(scrap_to_add):
                            # other_scraps_extended = other_scraps_extended + f"\tSC-{TARGET[0]}_{i+2:02}\n\tbreak\n"
                            f.write(globalData.th2Scrap.format(
                                name=TARGET,
                                projection="extended",
                                projection_short="C",
                                author=globalData.Author,
                                Copyright_Short=globalData.CopyrightShort,
                                year=datetime.now().year,
                                num=f"{i+2:02}",                         
                                )
                            )
    
    
    #################################################################################################     
    #  Update  -maps files                                                                            #
    #################################################################################################      
    if not UPDATE:
                              
        config_vars = {
                        'fileName': TH_NAME,
                        'caveName': TH_NAME.replace("_", " "),
                        'Author': globalData.Author,
                        'Copyright': globalData.Copyright,
                        'Scale' : SCALE,
                        'Target' : TARGET,
                        'mapComment' : globalData.mapComment,
                        'club' : globalData.club,
                        'thanksto' : globalData.thanksto,
                        'datat' : globalData.datat,
                        'wpage' : globalData.wpage, 
                        'cs' : globalData.cs,
                        'maps' : maps,
                        'plan': plan,
                        'extended': extended,
                        'configPath' : CONFIG_PATH,
                        'other_scraps_plan' : other_scraps_plan,
                        'other_scraps_extended' : other_scraps_extended,
                        'file_info' : f"# File generated by pyCreateTh.py version {Version} date: {datetime.now().strftime("%Y.%m.%d-%H:%M:%S")}",
                }
                

        update_template_files(DEST_PATH + '/template-maps.th', config_vars, DEST_PATH + '/' +  TH_NAME + '-maps.th')
    
        
    #################################################################################################     
    # Final therion compilation                                                                     #
    #################################################################################################
    if not UPDATE:   
        if globalData.finalTherionExe == True:
            FILE = os.path.dirname(ENTRY_FILE) + "/" + TH_NAME + "/" + TH_NAME + ".thconfig"      
            # log.info(f"Final therion compilation: {Colors.ENDC}{safe_relpath(FILE)}")     
            if not flagErrorCompile :
                t = compile_file(FILE, therion_path=globalData.therionPath)
                threads.append(t) 
    
    return flagErrorCompile, stat, totReadMeError, threads


################################################################################################# 
# lecture d'un fichier .mak                                                                     #
#################################################################################################    
def mak_to_th_file(ENTRY_FILE) :
    """
    Convertit un fichier .mak en fichier .th.

    Args:
        ENTRY_FILE (str): Le chemin vers le fichier .mak d'entrée.
        
    Returns:
  
    """
    
    # Liste des threads lancés
    threads = []
    
    _ConfigPath = "./../../"
    shortCurentFile = safe_relpath(ENTRY_FILE)
    
    totReadMeList = ""
    totReadMeError = ""
    totReadMeFixPoint = ""
    
    
    
    datFiles = []
    patternDat = re.compile(r'^#.*?\.dat[,;]$', re.IGNORECASE)  # Motif insensible à la casse
    
    fixPoints = []
    patternFixPoints = re.compile(r'^([\w-]+)\[(m|f)\s*[, ]\s*(-?\d+\.?\d*)\s*[, ]\s*(-?\d+\.?\d*)\s*[, ]\s*(-?\d+\.?\d*)\]\s*[,;]?\s*(?:/.*)?$',re.IGNORECASE)

    UTM = []
    
    Datums = set()  # Pour stocker les valeurs uniques trouvées
        
    try:
        with open(ENTRY_FILE, 'r') as file:
            for line in file:
                line = line.strip()  # Supprime les espaces et sauts de ligne
                if patternDat.match(line):
                    # Supprime le '#' au début et '.dat,' ou '.dat;' à la fin (insensible à la casse)
                    cleaned_entry = re.sub(r'^#|\.dat[,;]$', '', line, flags=re.IGNORECASE)
                    datFiles.append(cleaned_entry + ".DAT")
            
                match = patternFixPoints.match(line)
                
                if match:
                    name_point, mf, x, y, z = match.groups()
                    fixPoints.append([name_point, mf.lower(), float(x), float(y), float(z)])
                    
                if line.startswith('@') and line.endswith(';'):
                    parts = line[1:-1].split(',')  # Supprime "@" et ";", puis découpe
                    if len(parts) >= 4:
                        UTM.append(int(parts[3]) if parts[3].isdigit() else parts[3])
                        
                if line.startswith('&') and line.endswith(';'):
                # Extrait la valeur entre & et ;
                    Datum = line[1:-1].strip()  # Supprime '&' et ';'
                    Datums.add(Datum)     
                    
    except FileNotFoundError:
        log.error(f"The mak file {Colors.ENDC}{ENTRY_FILE}{Colors.ERROR} dit not exist")
        globalData.error_count += 1
        
    except Exception as e:
        log.error(f"An error occurred (readMakFile): {Colors.ENDC}{e}")
        globalData.error_count += 1
        
    
    # Vérification des valeurs
    if len(Datums) > 1:
        log.critical(f"Several different Datums found in {Colors.ENDC}{shortCurentFile}{Colors.CRITICAL}, case not handled! : {Colors.ENDC}{Datums}")
        exit(0)
    elif not Datums :
        log.critical(f"no datum found in mak file : {Colors.ENDC}{shortCurentFile}")
        exit(0)
    elif not datFiles :
        log.critical(f"No dat file found in mak file : {Colors.ENDC}{shortCurentFile}")
        exit(0)
    elif not fixPoints :
        log.critical(f"No fix points found in mak file : {Colors.ENDC}{shortCurentFile}")
        exit(0)

    datum_lower = next(iter(Datums)).strip().lower().replace(" ","")
    
    if datum_lower not in globalData.datumToEPSG:
        log.critical(f"Unknown Datum : {datum_lower}")
        exit(0)
    
    # Extraction du numéro de zone UTM et de l'hémisphère (N/S)
    if int(UTM[0]) >= 0 : 
        zone_num = int(UTM[0])
        hemisphere = "N" 
    else :
        zone_num = -int(UTM[0])
        hemisphere = "S"  
    
    # print(zone_num)       
    
    # Vérification de la validité de la zone UTM (1-60)
    if not 1 <= zone_num <= 60:
        log.critical("The UTM zone must be between 1 and 60")
        exit(0)
    
    # Construction du code EPSG
    epsg_prefix = globalData.datumToEPSG[datum_lower]
    epsg_code = f"{epsg_prefix}{zone_num}" if hemisphere == "N" else f"{epsg_prefix}{zone_num + 100}"
    
    # Génération du CRS QGIS (format WKT)
    crs_wkt = f'EPSG:{epsg_code}'
    
    
    log.info(f"Reading mak file: {Colors.ENDC}{shortCurentFile}{Colors.GREEN}, fixed station: {Colors.ENDC}{len(fixPoints)}{Colors.GREEN}, files: {Colors.ENDC}{len(datFiles)}{Colors.GREEN}, UTM Zone: {Colors.ENDC}{UTM[0]}{Colors.GREEN}, Datum: {Colors.ENDC}{next(iter(Datums))}{Colors.GREEN}, SCR: {Colors.ENDC}{crs_wkt}")
    totReadMeFixPoint = f"* Source mak file: {os.path.basename(ENTRY_FILE)}, fixed station: {len(fixPoints)}, files: {len(datFiles)}, UTM Zone: {UTM[0]}, Datum: {next(iter(Datums))}, SCR: {crs_wkt}\n" 
     
    QtySections = 0
    
    for file in datFiles :       
        ABS_file = os.path.dirname(abspath(args.file)) + "\\"+ file
        content, val = load_text_file_utf8(ABS_file, os.path.basename(ABS_file))
        section = content.split('\x0c')
        QtySections += len(section)

      
    SurveyTitleMak =  sanitize_filename(os.path.basename(abspath(args.file))[:-4])
        
    folderDest = os.path.dirname(abspath(args.file)) + "/" + SurveyTitleMak
        
    copy_template_if_not_exists(globalData.templatePath,folderDest)
    
    
    ##############################################################################################     
    # Boucle pour lire les dat                                                                   #
    ##############################################################################################
    
    
    stationList = pd.DataFrame(columns=['StationName', 'Survey_Name_01', 'Survey_Name_02'])
    totdata = f"\t## Input list:\n"
    totMapsPlan = ""
    totMapsExtended = ""
    
    proj = args.proj.lower()
    values = {
        "none":     ("# ", "# ", "# "),
        "plan":     ("",  "",  "# "),
        "extended": ("",  "# ", ""),
    }

    maps, plan, extended = values.get(proj, ("", "", ""))
    
    with alive_bar(QtySections, 
                    title=f"{Colors.GREEN}Surveys progress: {Colors.BLUE}",
                    length = 20, 
                    enrich_print=False,
                    stats=True,  # Désactive les stats par défaut pour plus de lisibilité
                    elapsed=True,  # Optionnel : masque le temps écoulé
                    monitor=True,  # Optionnel : masque les métriques (ex: "eta")
                    bar="smooth"  # Style de la barre (autres options: "smooth", "classic", "blocks")
                   ) as bar:
        
        with redirect_stdout(sys.__stdout__):
            for file in datFiles:
                
                if globalData.error_count > 0:
                    bar.text(f"{Colors.INFO}, file: {Colors.ENDC}{file[:-4]}{Colors.ERROR}, error: {Colors.ENDC}{globalData.error_count}")
                else :
                    bar.text(f"{Colors.INFO}, file: {Colors.ENDC}{file[:-4]}")
                
                _file = os.path.dirname(abspath(args.file)) + "\\" + file
                shutil.copy(_file, folderDest + "\\Data\\")
                ABS_file = folderDest + "\\Data\\" + file

                totReadMeError += f"* file: {file}\n"
                totReadMeList += f"file: {file}\n"

                Station, SurveyTitle, totReadMeError, thread2 = dat_to_th_files(ABS_file, fixPoints, crs_wkt, _ConfigPath, totReadMeError, bar)
                
                threads += thread2

                totdata += f"\tinput Data/{SurveyTitle}/{SurveyTitle}-tot.th\n"
                totMapsPlan += f"\t{plan}MP-{SurveyTitle}-Plan-tot@{SurveyTitle}\n\t{plan}break\n"
                totMapsExtended += f"\t{extended}MC-{SurveyTitle}-Extended-tot@{SurveyTitle}\n\t{extended}break\n"

                if not Station.empty:
                    __stationList = pd.concat([stationList, Station], ignore_index=True)
                    __stationList.sort_values(by='Survey_Name_02', inplace=True, ignore_index=True)
                    stationList = __stationList.copy()

                destination = os.path.join(folderDest, "Sources", os.path.basename(ABS_file))
                if os.path.exists(destination):
                    os.remove(destination)

                shutil.move(ABS_file, destination)

                bar() 
    
    
    ################################################################################################# 
    # Gestion des equates 
    #################################################################################################
        
    totdata +=f"\n" 
    
    _stationList = stationList.copy()
    
    _stationList["Survey_Name_01"] = _stationList["Survey_Name_01"] + "."+ _stationList["Survey_Name_01"]+ "." + _stationList["Survey_Name_02"]
    # On numérote les doublons de Survey_Name pour chaque StationName
    _stationList['Survey_Number'] = _stationList.groupby('StationName').cumcount() + 1

    # print(_stationList)

    # On pivote le tableau pour que chaque Survey_Name devienne une colonne
    tableau_pivot = _stationList.pivot(index='StationName', columns='Survey_Number', values='Survey_Name_01')
    
    tableau_pivot.columns = [f'Survey_Name_{i}' for i in tableau_pivot.columns]
    
    # print(f"tableau_pivot : {Colors.ENDC}{tableau_pivot}{Colors.INFO} in {Colors.ENDC}{args.file}")
    
    totdata +=f"\n\t## Equates list:\n"
    
    if 'Survey_Name_2' in tableau_pivot.columns:
        # On réinitialise l'index pour avoir StationName comme colonne normale
        tableau_pivot = tableau_pivot.reset_index()
        tableau_equate = tableau_pivot[tableau_pivot['Survey_Name_2'].notna()]

        log.info(f"Total des 'equates' in mak file: {Colors.ENDC}{len(tableau_equate)}{Colors.INFO} in {Colors.ENDC}{safe_relpath(args.file)}")
        # print(tableau_equate)
        # print(f"fixPoints: {Colors.ENDC}{fixPoints}{Colors.INFO} in {Colors.ENDC}{args.file}")
        
        # Pour chaque ligne du tableau
        for _, row in tableau_equate.iterrows():
            station = row['StationName']
            
            # On récupère tous les Survey_Name non vides (NaN exclus)
            surveys = [row[col] for col in tableau_equate.columns if col.startswith('Survey_Name') and pd.notna(row[col])]
            
            # Pour chaque paire unique (i < j), on écrit la ligne 'equate'
            for i in range(len(surveys)):
                for j in range(i + 1, len(surveys)):
                     if surveys[i].split('.')[2] != surveys[j].split('.')[2]:
                        totdata +=f"\tequate {station}@{surveys[i]} {station}@{surveys[j]}\n"
                        # print(f"\tequate {station}@{surveys[i]} {station}@{surveys[j]}")
    else:
        log.info(f"No 'equats' found in {Colors.ENDC}{args.file}")
            
    totdata +=f"\n\t## Maps list:\n\t{maps}input {SurveyTitleMak}-maps.th\n"
        
    config_vars = {
                    'fileName': SurveyTitleMak,
                    'caveName': SurveyTitleMak.replace("_", " "),
                    'Author': globalData.Author,
                    'Copyright': globalData.Copyright,
                    'Scale' : args.scale,
                    'Target' : "TARGET",
                    'mapComment' : globalData.mapComment,
                    'club' : globalData.club,
                    'thanksto' : globalData.thanksto,
                    'datat' : globalData.datat,
                    'wpage' : globalData.wpage, 
                    'cs' : crs_wkt,
                    'configPath' : " ",
                    'totData' : totdata,
                    'maps' : maps,
                    'plan': plan,
                    'extended': extended,
                    'XVIscale':globalData.XVIScale,
                    'other_scraps_plan' : totMapsPlan,
                    'other_scraps_extended' : totMapsExtended,
                    'readMeList' : totReadMeList,
                    'errorList' : totReadMeError,
                    'fixPointList' : totReadMeFixPoint,
                    'file_info' : f"# File generated by pyCreateTh.py version: {Version} date: {datetime.now().strftime("%Y.%m.%d-%H:%M:%S")}",
            }

    DEST_PATH = os.path.dirname(args.file) + '/' +  SurveyTitleMak

    update_template_files(DEST_PATH + '/template.thconfig', config_vars, DEST_PATH + '/' +  SurveyTitleMak + '.thconfig')
    update_template_files(DEST_PATH + '/template-tot.th', config_vars, DEST_PATH + '/' + SurveyTitleMak + '-tot.th')
    update_template_files(DEST_PATH + '/template-maps.th', config_vars, DEST_PATH + '/' +  SurveyTitleMak + '-maps.th')
    update_template_files(DEST_PATH + '/template-readme.md', config_vars, DEST_PATH + '/' +  SurveyTitleMak + '-readme.md')
    
    #################################################################################################     
    # Final therion compilation                                                                     #
    #################################################################################################
 
    if globalData.finalTherionExe == True:
        FILE = DEST_PATH + '/' +  SurveyTitleMak + '.thconfig'      
        t =  compile_file(FILE, therion_path=globalData.therionPath) 
        threads.append(t)
    
    return SurveyTitleMak, threads


#################################################################################################
def station_list(data, list, fixPoints, currentSurveyName) :  
    """
    Crée une liste de stations à partir des données fournies.

    Args:
        data (DataFrame): Les données d'entrée contenant les informations sur les stations.
        list (DataFrame): La liste des stations existantes.
        fixPoints (list): Les points de fixation à considérer.

    Returns:
        DataFrame: La liste mise à jour des stations.
    """
    
    # Création d'un DataFrame à partir des données  
    rows1 = [line.split() for line in data['DATA']]
    dfDATA = pd.DataFrame(rows1)
    
    # stations = pd.concat([dfDATA.iloc[1:, 0], dfDATA.iloc[1:, 1]]).drop_duplicates().str.replace('[', '%').str.replace(']', '%%').str.replace('@', '_._')
    
    stations = pd.concat([dfDATA.iloc[1:, 0], dfDATA.iloc[1:, 1]]).drop_duplicates().stationName() 
    
    fixed_names = {point[0] for point in fixPoints}
    stations = stations[~stations.isin(fixed_names)]
    
    new_entries = pd.DataFrame({
        'StationName': stations,
        'Survey_Name_01': currentSurveyName
    })
    
    list = pd.concat([list, new_entries], ignore_index=True)
    
    return list, dfDATA


#################################################################################################
def formated_station_list(df, dataFormat, unit = "meter", shortCurentFile ="None") :
    """
    Formate la liste des stations selon le format spécifié.

    Args:
        df (DataFrame): Le DataFrame contenant les données des stations.
        dataFormat (str): Le format de données souhaité.
        unit (str, optional): L'unité de mesure (par défaut "meter").
        ENTRY_FILE (str, optional): Le chemin du fichier d'entrée (par défaut None).

    Returns:
        DataFrame: Le DataFrame formaté.
    """
    
    # Remplacer les None/NaN par des espaces
    df = df.fillna(" ")

    # Conserver la première ligne (en-têtes) séparément
    header_row = df.iloc[0]

    # Traiter uniquement les lignes à partir de la deuxième (index 1)
    df_data = df.iloc[1:].copy()
                
    columns = dataFormat.split()

    Koef = 0.3048 if unit == "length meter" else 1.0
        
    if "length" in columns:
        col_name = df_data.columns[columns.index("length") - 2]
        df_data.iloc[:, col_name] = (df_data.iloc[:, col_name].astype(float) * Koef).apply(lambda x: f"{x:.2f}")

    if "up" in columns:
        col_name = df_data.columns[columns.index("up") - 2]
        df_data[col_name] = pd.to_numeric(df_data[col_name], errors='coerce') * Koef
        df_data[col_name] = df_data[col_name].apply(lambda x: "-" if pd.notna(x) and x < 0 else f"{x:.2f}" if pd.notna(x) else "")

    if "down" in columns:
        col_name = df_data.columns[columns.index("down") - 2]
        df_data[col_name] = pd.to_numeric(df_data[col_name], errors='coerce') * Koef
        df_data[col_name] = df_data[col_name].apply(lambda x: "-" if pd.notna(x) and x < 0 else f"{x:.2f}" if pd.notna(x) else "")

    if "right" in columns:
        col_name = df_data.columns[columns.index("right") - 2]
        df_data[col_name] = pd.to_numeric(df_data[col_name], errors='coerce') * Koef
        df_data[col_name] = df_data[col_name].apply(lambda x: "-" if pd.notna(x) and x < 0 else f"{x:.2f}" if pd.notna(x) else "")
    
    if "left" in columns:
        col_name = df_data.columns[columns.index("left") - 2]
        df_data[col_name] = pd.to_numeric(df_data[col_name], errors='coerce') * Koef
        df_data[col_name] = df_data[col_name].apply(lambda x: "-" if pd.notna(x) and x < 0 else f"{x:.2f}" if pd.notna(x) else "")

    if "compass" in columns:
        df_data.iloc[:, columns.index("compass")-2] = (df_data.iloc[:, columns.index("compass")-2].astype(float)).apply(lambda x: f"{x:.1f}")
    
    if "clino" in columns:
        df_data.iloc[:, columns.index("clino")-2] = (df_data.iloc[:, columns.index("clino")-2].astype(float)).apply(lambda x: f"{x:.1f}")
        
    if "from" in columns: 
        df_data.iloc[:, columns.index("from")-2] = (df_data.iloc[:, columns.index("from")-2].astype(str).stationName())
    
    if "to" in columns: 
        df_data.iloc[:, columns.index("to")-2] = (df_data.iloc[:, columns.index("to")-2].astype(str).stationName())  
        
    # Remplacer les NaN par des espaces après transformation
    df_data = df_data.fillna(" ")
    
    # Ajouter un '# ' au début de la colonne 9 (si non vide)
    df_data.iloc[:, 9] = df_data.iloc[:, 9].apply(lambda x: f"# {x}" if str(x).strip() and str(x) != " " else x)

    # Ajouter "_hab" à la colonne 2 si FROM == TO
    df_data.iloc[:, 1] = df_data.apply(
        lambda row: f"{row.iloc[1]}_hab" if str(row.iloc[0]).strip() == str(row.iloc[1]).strip() else row.iloc[1],
        axis=1
    )
    
    # Gestion des flags surface et not surface
    new_rows = []

    for idx, row in df_data.iterrows():
        col10 = str(row.iloc[9])

        # Si la colonne 10 contient #|L#    Exclude from Length
        if "#|L#" in col10:
            surface_row = [" "] * len(row)
            surface_row[0] = "flags surface"
            new_rows.append(surface_row)

            new_rows.append(row.tolist())

            not_surface_row = [" "] * len(row)
            not_surface_row[0] = "flags not surface"
            new_rows.append(not_surface_row)
        
        # Si la colonne 10 contient #|S#    type Spay (habillages)     
        elif "#|S#" in col10:        
            surface_row = [" "] * len(row)
            surface_row[0] = "flags splay"
            new_rows.append(surface_row)

            new_rows.append(row.tolist())

            not_surface_row = [" "] * len(row)
            not_surface_row[0] = "flags not splay"
            new_rows.append(not_surface_row)
            
        # Si la colonne 10 contient #|X#    total exclusion     
        elif "#|X#" in col10 or "#|XL#" in col10:  
            surface_row = [" "] * len(row)
            surface_row[0] = "flags duplicate"
            new_rows.append(surface_row)

            new_rows.append(row.tolist())

            not_surface_row = [" "] * len(row)
            not_surface_row[0] = "flags not duplicate"
            new_rows.append(not_surface_row)
            log.warning(f"Flags '{Colors.ENDC}{col10}{Colors.WARNING}' not implemented in therion, line {Colors.ENDC}{idx+1}{Colors.WARNING} in {Colors.ENDC}{shortCurentFile}")

        # Si la colonne 10 contient #|P#    exclude from plotting
        elif "#|P#" in col10:
            surface_row = [" "] * len(row)
            surface_row[0] = "# flags exclude from plot no implemented"
            new_rows.append(surface_row)

            new_rows.append(row.tolist())

            not_surface_row = [" "] * len(row)
            not_surface_row[0] = "# flags not exclude from plot no implemented"
            new_rows.append(not_surface_row)
            log.warning(f"Flags exclude from plot #|P# not implemented in therion, line {Colors.ENDC}{idx+1}{Colors.WARNING} in {Colors.ENDC}{shortCurentFile}")

        # Si la colonne 10 contient #|C#    exclude from closure
        elif "#|C#" in col10:
            surface_row = [" "] * len(row)
            surface_row[0] = "# flags exclude from closure no implemented"
            new_rows.append(surface_row)

            new_rows.append(row.tolist())

            not_surface_row = [" "] * len(row)
            not_surface_row[0] = "# flags not exclude from closure no implemented"
            new_rows.append(not_surface_row)
            log.warning(f"Flags #|C# exclude from closure not implemented in therion, line {Colors.ENDC}{idx+1}{Colors.WARNING} in {Colors.ENDC}{shortCurentFile}")

        # Si la colonne 10 contient #|PL#    exclude from plotting and Length
        elif "#|PL#" in col10 or "#|LP#" in col10:
            surface_row = [" "] * len(row)
            surface_row[0] = "flags duplicate"
            new_rows.append(surface_row)

            new_rows.append(row.tolist())

            not_surface_row = [" "] * len(row)
            not_surface_row[0] = "flags not duplicate"
            new_rows.append(not_surface_row)
            log.warning(f"Flags '{Colors.ENDC}{col10}{Colors.WARNING}' not implemented in therion, line {Colors.ENDC}{idx+1}{Colors.WARNING} in {Colors.ENDC}{shortCurentFile}")

        # Si la colonne 10 contient #|LC#    exclude from Length and Closure
        elif "#|LC#" in col10 or "#|CL#" in col10:
            surface_row = [" "] * len(row)
            surface_row[0] = "flags duplicate"
            new_rows.append(surface_row)

            new_rows.append(row.tolist())

            not_surface_row = [" "] * len(row)
            not_surface_row[0] = "flags not duplicate"
            new_rows.append(not_surface_row)
            log.warning(f"Flags '{Colors.ENDC}{col10}{Colors.WARNING}' not implemented in therion, line {Colors.ENDC}{idx+1}{Colors.WARNING} in {Colors.ENDC}{shortCurentFile}")

        # Si la colonne 10 contient #|PLC#    exclude from plotting, closure and length
        elif "#|PLC#" in col10:
            surface_row = [" "] * len(row)
            surface_row[0] = "flags duplicate"
            new_rows.append(surface_row)

            new_rows.append(row.tolist())

            not_surface_row = [" "] * len(row)
            not_surface_row[0] = "flags not duplicate"
            new_rows.append(not_surface_row)
        
        elif "#|" in col10:
            surface_row = [" "] * len(row)
            surface_row[0] = "# flags unknown no implemented"
            new_rows.append(surface_row)

            new_rows.append(row.tolist())

            not_surface_row = [" "] * len(row)
            not_surface_row[0] = "# flags not unknown no implemented"
            new_rows.append(not_surface_row)
            log.error(f"Flags unknown '{Colors.ENDC}{col10}{Colors.WARNING}' not implemented, line {Colors.ENDC}{idx+1}{Colors.WARNING} in {Colors.ENDC}{shortCurentFile}")
            globalData.error_count += 1
            
        else:
            new_rows.append(row.tolist())

        prev_row = row  # Garder trace de la ligne précédente

        cleaned_rows = []
        i = 0
        while i < len(new_rows):
            current = new_rows[i]
            if (i + 1 < len(new_rows) and
                str(current[0]).strip() == "flags not surface" and
                str(new_rows[i + 1][0]).strip() == "flags surface"):
                i += 2
            elif (i + 1 < len(new_rows) and
                str(current[0]).strip() == "flags not splay" and
                str(new_rows[i + 1][0]).strip() == "flags splay"):
                i += 2
            elif (i + 1 < len(new_rows) and
                str(current[0]).strip() == "flags not duplicate" and
                str(new_rows[i + 1][0]).strip() == "flags duplicate"):
                i += 2
            elif (i + 1 < len(new_rows) and
                str(current[0]).strip() == "# flags not exclude from closure no implemented" and
                str(new_rows[i + 1][0]).strip() == "# flags exclude from closure no implemented"):
                i += 2
            elif (i + 1 < len(new_rows) and
                str(current[0]).strip() == "# flags not exclude from plot no implemented" and
                str(new_rows[i + 1][0]).strip() == "# flags exclude from plot no implemented"):
                i += 2
            elif (i + 1 < len(new_rows) and
                str(current[0]).strip() == "# flags not unknown no implemented" and
                str(new_rows[i + 1][0]).strip() == "# flags unknown no implemented"):
                i += 2
            else:
                cleaned_rows.append(current)
                i += 1

    # Convertir les lignes en chaines formatées
    output = []

    # Ajouter la première ligne (en-têtes) telle quelle
    header_str = "\t\t" + "\t".join(map(str, header_row))
    output.append(header_str)

    # Ajouter les autres lignes traitées
    for row in cleaned_rows:
        row_str = "\t\t" 
        flag = False
        for i in row :
            if str(i) == " " :
                row_str += "" 
            elif str(i).startswith("#") or flag == True :
                row_str += f" {str(i)}"
                flag = True
            else:
               row_str += f"\t{str(i)}"
        output.append(row_str)
        
    return "\n".join(output)
    
    
#################################################################################################          
def find_duplicates_by_date_and_team(data):
    grouped = defaultdict(list)

    # Étape 1 : regroupement par (SURVEY_DATE, SURVEY_TEAM)
    for entry in data:
        key = (entry['SURVEY_DATE'], entry['SURVEY_TEAM'])    
        grouped[key].append(entry)

    duplicates = []

    for key, entries in grouped.items():
        if len(entries) < 2:
            continue

        # Construire un mapping ID -> stations
        id_to_entry = {entry['ID']: entry for entry in entries}
        id_to_stations = {entry['ID']: set(entry['STATION'].iloc[:, 0]) for entry in entries}

        # Construire les connexions directes (graphe implicite)
        adjacency = defaultdict(set)
        ids = list(id_to_entry.keys())

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                id_i, id_j = ids[i], ids[j]
                if id_to_stations[id_i] & id_to_stations[id_j]:  # intersection non vide
                    adjacency[id_i].add(id_j)
                    adjacency[id_j].add(id_i)

        # Trouver les composantes connexes (DFS)
        visited = set()

        def dfs(node, component):
            visited.add(node)
            component.append(node)
            for neighbor in adjacency[node]:
                if neighbor not in visited:
                    dfs(neighbor, component)

        for id_ in ids:
            if id_ not in visited:
                component = []
                dfs(id_, component)
                if len(component) > 1:
                    # Calcul des stations communes (fusion de toutes)
                    stations_union = set()
                    for i in range(len(component)):
                        for j in range(i + 1, len(component)):
                            common = id_to_stations[component[i]] & id_to_stations[component[j]]
                            stations_union.update(common)

                    duplicates.append({
                        'SURVEY_DATE': key[0],
                        'SURVEY_TEAM': key[1],
                        'IDS': sorted(component),
                        'COMMON_STATIONS': sorted(stations_union)
                    })

    return duplicates


def find_duplicates_by_date(data):
    grouped = defaultdict(list)

    # Étape 1 : regroupement uniquement par SURVEY_DATE
    for entry in data:
        key = entry['SURVEY_DATE']
        grouped[key].append(entry)

    duplicates = []

    for survey_date, entries in grouped.items():
        if len(entries) < 2:
            continue

        # Construire un mapping ID -> stations
        id_to_entry = {entry['ID']: entry for entry in entries}
        id_to_stations = {entry['ID']: set(entry['STATION'].iloc[:, 0]) for entry in entries}

        # Construire les connexions directes (graphe implicite)
        adjacency = defaultdict(set)
        ids = list(id_to_entry.keys())

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                id_i, id_j = ids[i], ids[j]
                if id_to_stations[id_i] & id_to_stations[id_j]:  # intersection non vide
                    adjacency[id_i].add(id_j)
                    adjacency[id_j].add(id_i)

        # Trouver les composantes connexes (DFS)
        visited = set()

        def dfs(node, component):
            visited.add(node)
            component.append(node)
            for neighbor in adjacency[node]:
                if neighbor not in visited:
                    dfs(neighbor, component)

        for id_ in ids:
            if id_ not in visited:
                component = []
                dfs(id_, component)
                if len(component) > 1:
                    # Calcul des stations communes (fusion de toutes)
                    stations_union = set()
                    for i in range(len(component)):
                        for j in range(i + 1, len(component)):
                            common = id_to_stations[component[i]] & id_to_stations[component[j]]
                            stations_union.update(common)

                    # Utiliser le SURVEY_TEAM de la première occurrence
                    first_entry = id_to_entry[component[0]]

                    duplicates.append({
                        'SURVEY_DATE': survey_date,
                        'SURVEY_TEAM': first_entry['SURVEY_TEAM'],
                        'IDS': sorted(component),
                        'COMMON_STATIONS': sorted(stations_union)
                    })

    return duplicates



#################################################################################################    
def points_uniques(data, crs_wkt):
    # Création d'un DataFrame à partir des lignes de données
    rows = [line.split() for line in data['DATA']]
    dfDATA = pd.DataFrame(rows)

    # Extraction des colonnes 0 et 1, en ignorant la première ligne (souvent en-tête)
    col0 = dfDATA.iloc[1:, 0]
    col1 = dfDATA.iloc[1:, 1]

    # Nettoyage des noms (remplacement des crochets)
    col0_clean = col0.stationName()
    col1_clean = col1.stationName()

    # Exclure les points présents dans la colonne 1
    uniques_col0 = col0_clean[~col0_clean.isin(col1_clean)]

    # Supprimer les doublons
    uniques_col0 = uniques_col0.drop_duplicates()

    # Exclure les points présents dans la liste crs_wkt
    if isinstance(crs_wkt, (set, list)):
        uniques_col0 = uniques_col0[~uniques_col0.isin(crs_wkt)]

    return uniques_col0.reset_index(drop=True).tolist()
    
     
#################################################################################################     
def merge_duplicate_surveys(data, duplicates, id_offset=10000):
    id_to_entry = {entry['ID']: entry for entry in data}
    merged_data = []
    used_ids = set()

    for i, group in enumerate(duplicates):
        ids = group['IDS']
        merged_entry = {
            'ID': id_offset + i,
            'SURVEY_TITLE': data[ids[0]]['SURVEY_TITLE'],
            'SURVEY_NAME': None,
            'SURVEY_DATE': group['SURVEY_DATE'],
            'COMMENT': data[ids[0]]['COMMENT'],
            'SURVEY_TEAM': group['SURVEY_TEAM'],
            'DECLINATION': data[ids[0]]['DECLINATION'],
            'FORMAT': data[ids[0]]['FORMAT'],
            'CORRECTIONS': data[ids[0]]['CORRECTIONS'],
            "CORRECTIONS2": data[ids[0]]['CORRECTIONS2'],
            "DISCOVERY": data[ids[0]]['DISCOVERY'],
            "PREFIX": data[ids[0]]['PREFIX'],
            'DATA': [],
            'STATION': [],
            'SOURCE': []
        }

        # Liste des champs texte simples à hériter (on peut affiner selon stratégie souhaitée)
        text_fields = ['SURVEY_TITLE', 'COMMENT', 'DECLINATION', 'FORMAT', 'CORRECTIONS']

        # Regrouper les valeurs pour tous les champs à fusionner
        text_values = {field: set() for field in text_fields}
        survey_name_list = set()
        source_set = set()
        station_frames = []
        
        first_data_line = True

        for id_ in ids:
            entry = id_to_entry[id_]
            used_ids.add(id_)

            for field in text_fields:
                value = entry.get(field)
                if value not in [None, '']:
                    text_values[field].add(value)
            
            name = entry.get('SURVEY_NAME')
            if name not in [None, '']:
                survey_name_list.add(name)
            
            data_lines = entry.get('DATA', [])
            if data_lines:
                if first_data_line:
                    merged_entry['DATA'].extend(data_lines)
                    first_data_line = False
                else:
                    merged_entry['DATA'].extend(data_lines[1:])  # ignorer l'entête

            sources = entry.get('SOURCE', [])
            if isinstance(sources, str):
                source_set.add(sources)
            elif isinstance(sources, list):
                source_set.update(sources)

            if isinstance(entry['STATION'], pd.DataFrame):
                station_frames.append(entry['STATION'])

        # Affecter les valeurs texte (si une seule unique valeur, sinon None)
        for field in text_fields:
            if len(text_values[field]) == 1:
                merged_entry[field] = next(iter(text_values[field]))
                
        # Nouveau nom concaténé avec "_"
        if survey_name_list:
            sorted_names = sorted(survey_name_list)
            full_name = "_".join(sorted_names)
            if len(full_name) <= 40:
                merged_entry['SURVEY_NAME'] = full_name
            else:
                # Tronquer au milieu
                prefix = sorted_names[0]
                suffix = sorted_names[-1]
                connector = "_-_"
                max_prefix_suffix_len = 50 - len(connector)
                # On répartit équitablement entre début et fin (si possible)
                half_len = max_prefix_suffix_len // 2
                prefix = prefix[:half_len]
                suffix = suffix[-(max_prefix_suffix_len - len(prefix)):]
                merged_entry['SURVEY_NAME'] = prefix + connector + suffix
    
        # Fusionner les DataFrames STATION
        if station_frames:
            merged_entry['STATION'] = pd.concat(station_frames, ignore_index=True)

        merged_entry['SOURCE'] = "\n".join(sorted(source_set))
        merged_data.append(merged_entry)

    # Ajouter les entrées qui ne faisaient pas partie des doublons
    for entry in data:
        if entry['ID'] not in used_ids:
            merged_data.append(deepcopy(entry))

    return merged_data     
     
        
#################################################################################################        
def dat_survey_format_extract(section_data, currentSurveyName, fichier, totReadMeError) :
    
    if section_data['FORMAT'] is None or len(section_data['FORMAT']) < 11 or len(section_data['FORMAT']) > 15 :
        log.error(f"Error in format code {Colors.ENDC}{section_data['FORMAT']}{Colors.ERROR} in {Colors.ENDC}{currentSurveyName}")
        log.debug(f"Error in format code SURVEY_NAME {Colors.ENDC}{section_data['SURVEY_NAME']}")
        log.debug(f"Error in format code SURVEY_DATE {Colors.ENDC}{section_data['SURVEY_DATE']}")
        log.debug(f"SURVEY TITLE: {Colors.ENDC}{section_data['SURVEY_TITLE']}")
        log.debug(f"COMMENT: {Colors.ENDC}{section_data['COMMENT']}")
        log.debug(f"SURVEY TEAM: {Colors.ENDC}{section_data['SURVEY_TEAM']}")
        log.debug(f"DECLINATION: {Colors.ENDC}{section_data['DECLINATION']}")
        log.debug(f"FORMAT: {Colors.ENDC}{section_data['FORMAT']}")
        log.debug(f"CORRECTIONS: {Colors.ENDC}{section_data['CORRECTIONS']}")
        log.debug(f"DATA: {Colors.ENDC}{(section_data['DATA'])}")
        log.debug(f"DATA Qté: {Colors.ENDC}{len(section_data['DATA'])}")
        log.debug(f"STATION: {Colors.ENDC}{(section_data['STATION'])}")
        log.debug(f"SOURCE: {Colors.ENDC}{section_data['SOURCE']}\n")
        globalData.error_count += 1
        totReadMeError += f"\tError in format code {section_data['FORMAT']} in {currentSurveyName}\n"
    
    def Dimension(string="") :
        directions = {'U': " up", 'D': " down", 'R': " right", 'L': " left"}
        if string in directions:
            return directions[string]
        else:
            log.error(f"Error in format str {Colors.ENDC}{string}{Colors.ERROR} code {Colors.ENDC}{section_data['FORMAT']}{Colors.ERROR} in {Colors.ENDC}{fichier}{Colors.ERROR} in {Colors.ENDC}{currentSurveyName}")
            totReadMeError += f"\tError in format str {string} code {section_data['FORMAT']} in {fichier} in {currentSurveyName}\n"
            globalData.error_count += 1
            return ""
             
    def LRUD_association(string="") :
        # In Therion the standard LRUD association is the shot and not the station
        # LRUD Association: F=From Station, T=To Station
        if  string == 'F' : return ""
        elif  string == 'T' : return ""
        else : 
            log.error(f"Error in format str {Colors.ENDC}{string}{Colors.ERROR} code {Colors.ENDC}{section_data['FORMAT']}{Colors.ERROR} in {Colors.ENDC}{fichier}{Colors.ERROR} in {Colors.ENDC}{currentSurveyName}")
            totReadMeError += f"\tError in format str {string} code {section_data['FORMAT']} in {fichier} in {currentSurveyName}\n"
            globalData.error_count += 1
            return ""

    def Backsight(string="") :           # Backsight: B=Redundant, N or empty=No Redundant Backsights.
        if  string == 'B' : 
            log.error(f"Backsight unit not yet implemented {Colors.ENDC}{section_data['FORMAT']}{Colors.ERROR} in {Colors.ENDC}{currentSurveyName}")  
            totReadMeError += f"\tBacksight unit not yet implemented {Colors.ENDC}{section_data['FORMAT']}{Colors.ERROR} in {Colors.ENDC}{currentSurveyName}\n"
            globalData.error_count += 1 
            return ""
        elif string == 'N' : return ""
        else : 
            log.error(f"Error in format str {Colors.ENDC}{string}{Colors.ERROR} code {Colors.ENDC}{section_data['FORMAT']}{Colors.ERROR} in {Colors.ENDC}{fichier}{Colors.ERROR} in {Colors.ENDC}{currentSurveyName}")
            totReadMeError += f"\tError in format str {string} code {section_data['FORMAT']} in {fichier} in {currentSurveyName}\n"
            globalData.error_count += 1
            return ""       

    def ShotOrder(string="") :
        if  string == 'L' : return " length"
        elif  string == 'A' : return " compass"
        elif  string == 'D' : 
            if clino == 'depth feet' : return " depthchange"
            else : return " clino"
        elif  string == 'a' : return "  backcompass"
        elif  string == 'd' : return "  backclino"
        else : 
            log.error(f"Error in format str {Colors.ENDC}{string}{Colors.ERROR} code {Colors.ENDC}{section_data['FORMAT']}{Colors.ERROR} in {Colors.ENDC}{fichier}{Colors.ERROR} in {Colors.ENDC}{currentSurveyName}")
            totReadMeError += f"\tError in format str {string} code {section_data['FORMAT']} in {fichier} in {currentSurveyName}\n"
            globalData.error_count += 1
            return ""

    type_Data = "normal"
    
    ################################################ Section Units 0-3 ###############################################
    if section_data['FORMAT'][0] == 'D' : compass = 'compass degree'
    elif section_data['FORMAT'][0] == 'R' : compass = 'compass grads'
    else : 
        compass = 'Compass_error'
        log.error(f"Compass bearing unit 'quads' not yet implemented in {Colors.ENDC}{currentSurveyName}")
        globalData.error_count += 1
        totReadMeError += f"\tCompass bearing unit 'quads' not yet implemented in survey {currentSurveyName}\n"
    
    if section_data['FORMAT'][1] == 'D' : length = 'length feet'
    elif section_data['FORMAT'][1] == 'M' : length = 'length meter'
    else : 
        length = 'Length_error'
        log.error(f"Length unit 'Feet and Inches' not yet implemented in {Colors.ENDC}{currentSurveyName}") 
        globalData.error_count += 1
        totReadMeError += f"\tLength unit 'Feet and Inches' not yet implemented in {currentSurveyName}\n"

    
    if section_data['FORMAT'][3] == 'D' : clino = 'clino degree'
    elif section_data['FORMAT'][3] == 'R' : clino = 'clino grads'
    # elif section_data['FORMAT'][3] == 'G' : clino = 'percent'   # %Grades à vérifier?  
    # elif section_data['FORMAT'][3] == 'M' : clino = 'grads'     # Degrees and Minutes
    elif section_data['FORMAT'][3] == 'W' : 
        clino = 'clino degree'   # Depth Gauge
        type_Data = "normal"   # Depth Gauge
    else : 
        clino = 'Inclination_error'
        log.error(f"Inclination unit not yet implemented in {Colors.ENDC}{currentSurveyName}")   
        globalData.error_count += 1
        totReadMeError += f"\tInclination unit not yet implemented in {currentSurveyName}\n"
        
    ################################################ Section dimensions 4-7 ###############################################    
    dataFormat = Dimension(section_data['FORMAT'][4])
    dataFormat += Dimension(section_data['FORMAT'][5])
    dataFormat += Dimension(section_data['FORMAT'][6])
    dataFormat += Dimension(section_data['FORMAT'][7])    
    
    ################################################ Section Shot 8-11 ou 13 ###############################################
    if len(section_data['FORMAT']) == 11 or len(section_data['FORMAT']) == 12 or len(section_data['FORMAT']) == 13:
        if  len(section_data['FORMAT']) == 13 :   # UUUUDDDDSSSBL
            dataFormat = LRUD_association(section_data['FORMAT'][12]) + dataFormat
            dataFormat = Backsight(section_data['FORMAT'][11]) + dataFormat # UUUUDDDDSSSB 
        elif  len(section_data['FORMAT']) == 12 :  dataFormat = Backsight(section_data['FORMAT'][11]) + dataFormat             
        dataFormat = ShotOrder(section_data['FORMAT'][10]) + dataFormat
        dataFormat = ShotOrder(section_data['FORMAT'][9]) + dataFormat
        dataFormat = ShotOrder(section_data['FORMAT'][8]) + dataFormat

    elif len(section_data['FORMAT']) == 15 :    #  UUUUDDDDSSSSSBL 
        dataFormat = LRUD_association(section_data['FORMAT'][14]) + dataFormat
        dataFormat = Backsight(section_data['FORMAT'][13]) + dataFormat             
        dataFormat = ShotOrder(section_data['FORMAT'][11]) + dataFormat
        dataFormat = ShotOrder(section_data['FORMAT'][9]) + dataFormat
        dataFormat = ShotOrder(section_data['FORMAT'][8]) + dataFormat
        
    ################################################ Section Shot 8-11 ou 13 ###############################################
    
    
    dataFormat = "data " + type_Data + " from to" + dataFormat + " # comment"
    
    return dataFormat, length, compass, clino, totReadMeError       
        
#
# ################################################################################################     
def load_text_file_utf8(filepath, short_filename):
    encodings_to_try = [
        'utf-8-sig',       # UTF-8 avec BOM
        'utf-8',           # UTF-8 standard
        'windows-1252',    # ANSI Windows Europe de l’Ouest
        'iso-8859-15',     # ISO-8859-15 (latin9), remplace iso-8859-1 (latin1)
        'iso-8859-1',
    ]

    for enc in encodings_to_try:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.read()
            log.info(f"Source file: {Colors.ENDC}{short_filename}{Colors.GREEN}, encoding: {Colors.ENDC}{enc}{Colors.GREEN}, conversion to UTF-8")
            message = f"* Source file: {short_filename}, encoding: {enc}, conversion to UTF-8\n"
            return content, message
        
        except UnicodeDecodeError as e:
            log.debug(f"Failed {Colors.ENDC}{enc}{Colors.DEBUG} for {Colors.ENDC}{short_filename}{Colors.DEBUG}: {Colors.ENDC}{e}")
            continue
        
        except Exception as e:
            log.critical(f"Unexpected error while reading {Colors.ENDC}{short_filename}{Colors.CRITICAL}: {e}")
            exit(0)
            return None, ""

    # Dernier recours : lecture binaire + forçage
    try:
        with open(filepath, 'rb') as f:
            raw = f.read()
            content = raw.decode('windows-1252', errors='replace')
        log.warning(f"Force-reading {Colors.ENDC}{short_filename}{Colors.WARNING} with character replacement (windows-1252)")
        message = f"* Force-reading source file: {short_filename} with character replacement (windows-1252)\n"  
        return content, message
    
    except Exception as e:
        log.critical(f"Failed to read file {Colors.ENDC}{short_filename}{Colors.CRITICAL}: {Colors.ENDC}{e}")  
        exit(0)
        return None, ""


################################################################################################# 
# Création des dossiers Th à partir d'un dat                                                    #
#################################################################################################  
def dat_to_th_files (ENTRY_FILE, fixPoints = [], crs_wkt = "", CONFIG_PATH = "", totReadMeError = "", bar=None) :
    """
    Convertit un fichier .dat en fichiers .th.

    Args:
        ENTRY_FILE (str): Le chemin vers le fichier .dat d'entrée.
        fixPoints (list, optional): Liste des points de fixation. Defaults to [].
        crs_wkt (str, optional): Le système de référence spatiale en WKT. Defaults to "".
        CONFIG_PATH (str, optional): Le chemin vers le fichier de configuration. Defaults to "".
    
    Returns:
        tuple: Un tuple contenant un DataFrame des stations et le nom du survey.
        
    """
    
    
    # Détecter la fin de section (FF CR LF qui correspond à \x0c\r\n)
    section_separator = '\x0c'
    shortCurentFile = os.path.basename(ENTRY_FILE)

    
    #################################################################################################     
    # 1 : Lecture du fichier dat                                                                    #
    ################################################################################################# 
        
    content, totReadMe = load_text_file_utf8(ENTRY_FILE, shortCurentFile)
    
    #################################################################################################     
    # Séparer les sections                                                                          #
    #################################################################################################
    sections = content.split(section_separator)
    
    # Listes pour stocker les données
    data = []
    unique_id = 1
    totdata = f"\t## Input list:\n"
    totMapsPlan = ""
    totMapsExtended = ""
    totReadMeErrorDat = ""
    totReadMeFixPoint = f"cs {crs_wkt}\n"
    threads = []
    
    # Tableau global pour stocker toutes les stations
    stationList = pd.DataFrame(columns=['StationName', 'Survey_Name_01', 'Survey_Name_02'])
    
    section0 = True; 
    
    #################################################################################################     
    # 2 : Boucle pour lire les surveys au format dat                                                #
    #################################################################################################
    for section in sections:
        
        listStationSection = pd.DataFrame(columns=['StationName', 'Survey_Name'])
        
        if not section.strip():
            continue  # ignorer les sections vides
        
        # Dictionnaire pour stocker les infos de la section courante
        section_data = {
            'ID': unique_id, 
            'SURVEY_TITLE': None,
            'SURVEY_NAME': None,
            'SURVEY_DATE': None,
            'COMMENT' : None,
            'SURVEY_TEAM': None,
            'DECLINATION': None,
            'FORMAT': None,
            'CORRECTIONS' : None,
            "CORRECTIONS2": None,
            "DISCOVERY": None,
            "PREFIX": None,
            'DATA' : [],  
            'STATION': [],
            'SOURCE' : []
        }
        
        regex_patterns = {
            "DECLINATION": r"DECLINATION:\s*([\d\.\-]+)",
            "FORMAT": r"FORMAT:\s*([A-Za-z]+)",
            "CORRECTIONS": r"CORRECTIONS:\s*([\d\.\-]+\s+[\d\.\-]+\s+[\d\.\-]+)",
            "CORRECTIONS2": r"CORRECTIONS2:\s*([\d\.\-]+\s+[\d\.\-]+)",
            "DISCOVERY": r"DISCOVERY:\s*(\d+\s+\d+\s+\d+)",
            "PREFIX": r"PREFIX:\s*(\S+)"
        }
        
        # Parcourir les lignes de la section
        lines = section.split('\n')
        
        section_data['SOURCE'] = section
        
        NextLineSurveyTeam = False
        
        if lines:
            if section0 :
                section_data['SURVEY_TITLE'] = lines[0].strip()
                lines = lines[1:]  # Supprimer la première ligne
                section0 = False
            else :
                lines = lines[1:]
                section_data['SURVEY_TITLE'] = lines[0].strip()
                lines = lines[1:]  # Supprimer la première ligne
            
        jumpLine = False
            
        for line in lines:
            line = line.strip()
            if jumpLine == True :
                jumpLine = False
                line = line.strip()  
            elif line.startswith('SURVEY NAME:'):
                section_data['SURVEY_NAME'] = sanitize_filename(line.split(':', 1)[1].strip())
            elif line.startswith('SURVEY DATE:'):
                # current_field = 'DATE'
                # Séparer la date et le commentaire
                date_parts = line.split(':', 1)[1].strip().split('COMMENT:', 1)
                date = date_parts[0].strip()
                mois, jour, annee = date.split()
                date_convertie = f"{int(annee):04d} {int(mois):02d} {int(jour):02d}"
                section_data['SURVEY_DATE'] = date_convertie
                if section_data['SURVEY_DATE'] == None or section_data['SURVEY_DATE'] == '' :
                    section_data['SURVEY_DATE'] = "2000 01 01"
                    log.warning(f"Survey {Colors.ENDC}{section_data['SURVEY_NAME']}{Colors.WARNING} with no date, add default date 2000 01 01 ")
                if len(date_parts) > 1:
                    section_data['COMMENT'] = date_parts[1].strip()
            elif line.startswith('SURVEY TEAM:'):   
                NextLineSurveyTeam = True
                line.strip()
            elif NextLineSurveyTeam == True : 
                NextLineSurveyTeam = False
                section_data['SURVEY_TEAM'] = line.strip()
            elif line.startswith('DECLINATION:'):         
                for champ, pattern in regex_patterns.items():
                    match = re.search(pattern, line)
                    if match:
                        section_data[champ] = match.group(1).strip()
                jumpLine = True # Sauter une ligne après la ligne DECLINATION
                    
                        
            else :
                if line.strip() != '' :       
                    section_data['DATA'].append(line.strip())
                else :
                    line.strip()
        
        # Ajouter les données de la section à la liste
        if len(section_data['DATA']) > 0 :
            listStationSection, dfDATA = station_list(section_data, listStationSection, fixPoints, section_data['SURVEY_NAME'])
            section_data['STATION'] = listStationSection
            data.append(section_data)    
            unique_id += 1 
            

            #################################################################################################     
            # Détecter les surveys avec plusieurs points de départ                                          #
            #################################################################################################    
  
            # points = points_uniques(section_data, crs_wkt)

            # if len(points) > 1 :
            #     log.warning(f"Points {Colors.ENDC}{points}{Colors.WARNING} uniques dans la section {Colors.ENDC}{section_data['SURVEY_NAME']}")
            #     # globalData.error_count += 1
                
            # else :
            #     log.debug(f"Points {Colors.ENDC}{points}{Colors.DEBUG} uniques dans la section {section_data['SURVEY_NAME']}")
                
    
    #################################################################################################
    # Grouper les sections ayant même date team et un point commun                                  #
    #################################################################################################
    val1 = len(data)
    
    # duplicates = find_duplicates_by_date_and_team(data)     
    duplicates = find_duplicates_by_date(data)     
    
    data = merge_duplicate_surveys(data, duplicates)
    
    val2 = val1 - len(data)
    
    if val2 != 0 :
        log.info(f"Read dat file: {Colors.ENDC}{shortCurentFile}{Colors.INFO} with {Colors.ENDC}{len(data)}{Colors.GREEN}{Colors.INFO} survey(s) and merged {Colors.ENDC}{val2}")
        bar(val2)
    else :
        log.info(f"Read dat file: {Colors.ENDC}{shortCurentFile}{Colors.INFO} with {Colors.ENDC}{len(data)}{Colors.INFO} survey(s)")
    

    #################################################################################################     
    # Créer le dossier pour les fichiers convertis                                                  #
    #################################################################################################
    
    if data[0]['SURVEY_TITLE'] !="" :
        SurveyTitle = sanitize_filename(data[0]['SURVEY_TITLE'])  
        folderDest = os.path.dirname(ENTRY_FILE) + "\\" + SurveyTitle
        if os.path.isdir(folderDest): 
           SurveyTitle = sanitize_filename(os.path.basename(ENTRY_FILE[:-4]))
    else :
        SurveyTitle = sanitize_filename(os.path.basename(ENTRY_FILE[:-4]))

    folderDest = os.path.dirname(ENTRY_FILE) + "\\" + SurveyTitle
    
    copy_template_if_not_exists(globalData.templatePath,folderDest)
    
    if  args.file[-3:].lower() != "dat" :
        _destination =  folderDest + "\\config.thc"
        # print(f"destination_path : {_destination}")
        os.remove(_destination)
    
    # Trie des données par date        
    data = sorted(data, key=lambda x: x['SURVEY_DATE'] or "")
    
    #################################################################################################     
    # 3 : Boucle pour créer les surveys au format th                                                #
    #################################################################################################

    surveyCount = 1
    
    # totReadMe += f"* Source file: {os.path.basename(ENTRY_FILE)}\n"
    
    proj = args.proj.lower()
    values = {
        "none":     ("# ", "# ", "# "),
        "plan":     ("",  "",  "# "),
        "extended": ("",  "# ", ""),
    }

    maps, plan, extended = values.get(proj, ("", "", ""))
    
    for _line in data :    
        
        # currentSurveyName = f"{globalData.typeSurveyName}{surveyCount:02d}"
        # currentSurveyName = f"{globalData.typeSurveyName}{surveyCount:02d}_{sanitize_filename(_line['SURVEY_NAME'])}"
        currentSurveyName = f"{globalData.SurveyPrefixName}{surveyCount:02d}_{sanitize_filename(_line['SURVEY_DATE'])}"
   
        output_file = f"{folderDest}\\Data\\{currentSurveyName}.th"
        
        #################################################################################################     
        # gestion des CORRECTIONS                                                                       #
        #################################################################################################
        
        _CorrectionValues =  [float(val) for val in _line['CORRECTIONS'].strip().split()] 
        
        if all(val == 0.0 for val in _CorrectionValues) :
            _corrections = ""
        else :
            _corrections = f"\t\t# Corrections: {_CorrectionValues[0]} {_CorrectionValues[1]} {_CorrectionValues[2]}, not yet implemented\n"
            log.error(f"Corrections: {Colors.ENDC}{_CorrectionValues[0]} {_CorrectionValues[1]} {_CorrectionValues[2]}{Colors.ERROR}, not yet implemented in {Colors.ENDC}{currentSurveyName}")  
            totReadMeError += f"\tCorrections: {_CorrectionValues[0]} {_CorrectionValues[1]} {_CorrectionValues[2]}, not yet implemented in {currentSurveyName}\n" 
            globalData.error_count += 1
        
        if  _line['CORRECTIONS2'] != None :
            _CorrectionValues3 =  [float(val) for val in _line['CORRECTIONS2'].strip().split()] 
            if all(val == 0.0 for val in _CorrectionValues) :
                _CorrectionValues3 = ""
            else :
                log.error(f"Corrections2: {Colors.ENDC}{_CorrectionValues[0]} {_CorrectionValues[1]} {_CorrectionValues[2]}{Colors.ERROR}, not yet implemented in {Colors.ENDC}{currentSurveyName}")  
                totReadMeError += f"\tCorrections2: {_CorrectionValues[0]} {_CorrectionValues[1]} {_CorrectionValues[2]}, not yet implemented in {currentSurveyName}\n" 
                globalData.error_count += 1
        
        if  _line['DISCOVERY'] != None :
            date = _line['DISCOVERY'].strip()
            mois, jour, annee = date.split()
            discovery = f"{int(annee):04d} {int(mois):02d} {int(jour):02d}"
        else : 
            discovery = f"{_line['SURVEY_DATE']} # '????'"
        
        if  _line['PREFIX'] != None :
                log.error(f"PREFIX: {Colors.ENDC}{_line['PREFIX']}, not yet implemented in {Colors.ENDC}{currentSurveyName}")  
                totReadMeError += f"\tPREFIX: {_line['PREFIX']}, not yet implemented in {currentSurveyName}\n" 
                globalData.error_count += 1

        SurveyNameCount = {
            'surveyCount' :f"{currentSurveyName}", 
            'SURVEY_NAME': _line['SURVEY_NAME']
        }

        
    
        #################################################################################################     
        # gestion des DATA                                                                              #
        #################################################################################################

        stationList, dfDATA = station_list(_line, stationList, fixPoints, currentSurveyName)

        ################################################################################################# 
        # Recherche des points fixes (entrées)
        ################################################################################################# 
        
        fixPoint =""
        
        # Extraire les noms des stations depuis dfDATA
        stations_from = set(dfDATA.iloc[:, 0])  # Colonne 'FROM'
        stations_to = set(dfDATA.iloc[:, 1])    # Colonne 'TO'
        all_stations = stations_from.union(stations_to)

        # Filtrer fixPoints pour garder seulement ceux présents dans dfDATA
        list_common_points = [point for point in fixPoints if point[0] in all_stations]

        # Afficher le résultat
        # print(list_common_points)
        
        if len(list_common_points) >= 1 :
            fixPoint += f"\t\tcs {crs_wkt}\n"             
            for point in list_common_points :
                totReadMeFixPoint += f"\tFix point: {point[0]} [{point[2]:.3f} m, {point[3]:.3f} m, {point[4]:.3f} m], in {currentSurveyName}\n"
                if point[1] == 'm' :
                    fixPoint +=  f"\t\tfix {point[0]} {point[2]:.3f} {point[3]:.3f}	{point[4]:.3f}\n" 
                elif point[1] == 'f' :
                   fixPoint += f"\t\tfix {point[0]} {point[2]*0.3048:.3f} {point[3]*0.3048:.3f} {point[4]*0.3048:.3f} # Conversion feet - meter\n"
        
         
        ################################################################################################# 
        # Gestion des formats
        ################################################################################################# 
        
        dataFormat, length, compass, clino, totReadMeErrorDat = dat_survey_format_extract(_line, currentSurveyName, shortCurentFile, totReadMeErrorDat)
        
        if "grads" in compass:
            _compass = "grads" 
        else: 
            _compass = "degree"
        
        ################################################################################################# 
        # Gestion des formats
        ################################################################################################# 
        
        with open(str(output_file), "w+", encoding="utf-8") as f:
            f.write(globalData.thFileDat.format(
                    VERSION = Version,
                    DATE=datetime.now().strftime("%Y.%m.%d-%H:%M:%S"),
                    # SURVEY_NAME = sanitize_filename(_line['SURVEY_NAME']),  
                    SURVEY_NAME = f"{currentSurveyName}", 
                    SURVEY_TITLE = _line['SURVEY_NAME'].replace("_", " "),
                    SURVEY_DATE = _line['SURVEY_DATE'], 
                    SURVEY_TEAM = _line['SURVEY_TEAM'], 
                    FORMAT = _line['FORMAT'], 
                    COMPASS = compass,
                    LENGTH = length, 
                    CLINO = clino,    
                    DATA_FORMAT = dataFormat,
                    CORRECTIONS =_corrections, 
                    DECLINATION = f"\t\tdeclination {_line['DECLINATION']} {_compass}\n" if (crs_wkt == "" and _line['DECLINATION'] != 0.0) else "", 
                    DATA = formated_station_list(dfDATA, dataFormat, length, shortCurentFile),
                    COMMENT = sanitize_filename(_line['SURVEY_NAME'] + " " + _line['COMMENT']).replace('"', "'").replace('_', " "),
                    FIX_POINTS = fixPoint,
                    EXPLO_DATE = discovery,
                    EXPLO_TEAM = f"{_line['SURVEY_TEAM']} # '????'",
                    SOURCE = '\n'.join('# ' + line for line in _line['SOURCE'].splitlines()),                    
                    )
            )
        
        totdata +=f"\tinput Data/{currentSurveyName}/{currentSurveyName}-tot.th\n" 

        log.info(f"Therion file : {Colors.ENDC}{safe_relpath(output_file)}{Colors.GREEN} created from {Colors.ENDC}{os.path.basename(ENTRY_FILE)}")

        ################################################################################################# 
        # Création des dossiers
        ################################################################################################# 
        
        _Config_PATH = CONFIG_PATH + "../../"
        
        StatCreateFolder, stat, totReadMeErrorDat, thread2 = create_th_folders(
                                        ENTRY_FILE = output_file, 
                                        PROJECTION = args.proj,
                                        SCALE = args.scale, 
                                        UPDATE = args.update, 
                                        CONFIG_PATH = _Config_PATH, 
                                        totReadMeError = totReadMeErrorDat
                                        )
        threads += thread2 
     
        log.info(f"File: {Colors.ENDC}{currentSurveyName}{Colors.INFO},  compilation successful, length: {Colors.ENDC}{stat["length"]}m{Colors.INFO}, depth: {Colors.ENDC}{stat["depth"]}m")   
        totReadMe += f"\t{currentSurveyName} compilation successful length: {stat["length"]} m, depth: {stat["depth"]} m\n"
         
        _destination = output_file[:-3] + "\\Sources"
        destination_path = os.path.join(_destination, os.path.basename(output_file))
        shutil.move(output_file, destination_path)      
        
        if args.file[-3:].lower() != "dat" :
            _destination =  output_file[:-3] + "\\config.thc"
            destination_path = os.path.join(_destination, os.path.basename(output_file))
            # print(f"destination_path : {_destination}")
            os.remove(_destination)
        
        if not StatCreateFolder :
            totMapsPlan += f"\t{plan}MP-{currentSurveyName}-Plan-tot@{currentSurveyName}\n\t{plan}break\n"
            totMapsExtended += f"\t{extended}MC-{currentSurveyName}-Extended-tot@{currentSurveyName}\n\t{extended}break\n"
        surveyCount += 1
        
        if globalData.error_count > 0:
            bar.text(f"{Colors.INFO}, file: {Colors.ENDC}{os.path.basename(ENTRY_FILE)[:-4]}{Colors.INFO}, survey: {Colors.ENDC}{currentSurveyName}{Colors.ERROR}, error: {Colors.ENDC}{globalData.error_count}")
        else :
            bar.text(f"{Colors.INFO}, file: {Colors.ENDC}{os.path.basename(ENTRY_FILE)[:-4]}{Colors.INFO}, survey: {Colors.ENDC}{currentSurveyName}")
        bar()

#################################################################################################     
# 4 : Finalisation (remplissage des -tot.th et maps.th                                          #
#################################################################################################

    ################################################################################################# 
    # Gestion des equates 
    #################################################################################################
        
    totdata +=f"\n" 

        
    
     
    _stationList = stationList.copy()
    
    # On numérote les doublons de Survey_Name pour chaque StationName
    _stationList['Survey_Number'] = _stationList.groupby('StationName').cumcount() + 1
    
    # print(_stationList)
    
    # On pivote le tableau pour que chaque Survey_Name devienne une colonne
    tableau_pivot = _stationList.pivot(index='StationName', columns='Survey_Number', values='Survey_Name_01')
    
    tableau_pivot.columns = [f'Survey_Name_{i}' for i in tableau_pivot.columns]
    
    # print(f"tableau_pivot: {Colors.ENDC}{tableau_pivot}{Colors.INFO} in {Colors.ENDC}{ENTRY_FILE}")
    
    totdata +=f"\n\t## equates list:\n"
    
    if 'Survey_Name_2' in tableau_pivot.columns:
        # On réinitialise l'index pour avoir StationName comme colonne normale
        tableau_pivot = tableau_pivot.reset_index()
        tableau_equate = tableau_pivot[tableau_pivot['Survey_Name_2'].notna()]

        log.info(f"Total 'equates' founds: {Colors.ENDC}{len(tableau_equate)}{Colors.INFO} in {Colors.ENDC}{shortCurentFile}")
        # print(tableau_equate)
        # print(f"fixePoints : {Colors.ENDC}{fixed_names}{Colors.INFO} in {Colors.ENDC}{ENTRY_FILE}")
        
        # Pour chaque ligne du tableau
        for _, row in tableau_equate.iterrows():
            station = row['StationName']
            
            # On récupère tous les Survey_Name non vides (NaN exclus)
            surveys = [row[col] for col in tableau_equate.columns if col.startswith('Survey_Name') and pd.notna(row[col])]
            
            # Pour chaque paire unique (i < j), on écrit la ligne 'equate'
            for i in range(len(surveys)):
                for j in range(i + 1, len(surveys)):
                    totdata +=f"\tequate {station}@{surveys[i]}.{surveys[i]} {station}@{surveys[j]}.{surveys[j]}\n"
    else:
        log.info(f"No 'equates' found in {Colors.ENDC}{ENTRY_FILE}")
             
    totdata +=f"\n\t## Maps list:\n\t{maps}input {SurveyTitle}-maps.th\n"
    
    if totReadMeErrorDat == "" : totReadMeErrorDat += "\tAny error in this file, that's perfect !\n"
        
    config_vars = {
                    'fileName': SurveyTitle,
                    'caveName': SurveyTitle.replace("_", " "),
                    'Author': globalData.Author,
                    'Copyright': globalData.Copyright,
                    'Scale' : args.scale,
                    'Target' : "TARGET",
                    'mapComment' : globalData.mapComment,
                    'club' : globalData.club,
                    'thanksto' : globalData.thanksto,
                    'datat' : globalData.datat,
                    'wpage' : globalData.wpage, 
                    'cs' : crs_wkt if crs_wkt != "" else globalData.cs,
                    'totData' : totdata,
                    'maps' : maps,
                    'plan': plan,
                    'XVIscale':globalData.XVIScale,
                    'extended': extended,
                    'configPath' : CONFIG_PATH,
                    'other_scraps_plan' : totMapsPlan,
                    'readMeList' : totReadMe,
                    'errorList' : totReadMeErrorDat,
                    'fixPointList' : totReadMeFixPoint,
                    'other_scraps_extended' : totMapsExtended,
                    'file_info' : f"# File generated by pyCreateTh.py version: {Version} date: {datetime.now().strftime("%Y.%m.%d-%H:%M:%S")}",
            }

    DEST_PATH = os.path.dirname(ENTRY_FILE) + '/' +  SurveyTitle

    update_template_files(DEST_PATH + '/template.thconfig', config_vars, DEST_PATH + '/' +  SurveyTitle + '.thconfig')
    update_template_files(DEST_PATH + '/template-tot.th', config_vars, DEST_PATH + '/' + SurveyTitle + '-tot.th')
    update_template_files(DEST_PATH + '/template-maps.th', config_vars, DEST_PATH + '/' +  SurveyTitle + '-maps.th')
    update_template_files(DEST_PATH + '/template-readme.md', config_vars, DEST_PATH +'/' + SurveyTitle + '-readme.md')
    
    #################################################################################################     
    # Final therion compilation                                                                     #
    #################################################################################################
 
    if globalData.finalTherionExe == True:
        FILE = DEST_PATH + '/' +  SurveyTitle + '.thconfig'      
        t = compile_file(FILE, therion_path=globalData.therionPath) 
        threads.append(t)
        
    stationList["Survey_Name_02"] = SurveyTitle

    totReadMeError += totReadMeErrorDat
    
    return stationList, SurveyTitle, totReadMeError, threads


#################################################################################################
def wait_until_file_is_released(filepath, timeout=30):
    start = time.time()
    while True:
        try:
            with open(filepath, "rb"):
                return True
        except PermissionError:
            if time.time() - start > timeout:
                log.Error(f"Timeout: The file remains locked after {Colors.ENDC}{timeout}{Colors.ERROR} secondes: {Colors.ENDC}{filepath}")
            time.sleep(0.1)  # attend 100 ms


#################################################################################################
#  main function                                                                                #
#################################################################################################
if __name__ == u'__main__':	
    
    start_time  = datetime.now()
    threads = []
    fileTitle = ""
    
    #################################################################################################
    # Parse arguments                                                                               #
    #################################################################################################
    parser = argparse.ArgumentParser(
        description=f"{Colors.BLUE}Create a skeleton folder and th, th2 files with scraps from *.mak, *.dat, *.th Therion files, version: {Colors.ENDC}{Version}\n",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.print_help = colored_help.__get__(parser)
    parser.add_argument("--file", help="the file (*.th, *.mak, *.dat,) to perform e.g. './Therion_file.th'", default="")
    # parser.add_argument("--survey_name", help="Scrap name (if different from 'survey_file' name)", default="None")
    parser.add_argument("--proj", choices=['All', 'Plan', 'Extended', 'None'], help="the th2 files scrap projection to produce, default: All", default="All")
    #parser.add_argument("--format", choices=['th2', 'plt'], help="Output format. Either th2 for producing skeleton for drawing or plt for visualizing in aven/loch", default="th2")
    # parser.add_argument("--output", default="./", help="Output folder path")
    # parser.add_argument("--therion-path", help="Path to therion binary", default="therion")
    parser.add_argument("--scale", help="scale for the pdf layout exports, default value: 1000 (i.e. xvi files scale is 100)", default="1000")
    # parser.add_argument("--lines", type=str_to_bool, help="Shot lines in th2 files", default=-1)
    # parser.add_argument("--names", type=str_to_bool, help="Stations names in th2 files", default=-1)
    # parser.add_argument("--update", help="Mode update, option th2", default="")
    parser.add_argument("--update", help="th2 files update mode (only for th input files, no folders created)", action="store_true", default=False)
                        
    parser.epilog = (
        f"{Colors.GREEN}Please, complete {Colors.BLUE}config.ini{Colors.GREEN} in {Colors.BLUE}FILE{Colors.GREEN} folder or in script folder for personal configuration{Colors.ENDC}\n"
        f"{Colors.GREEN}If no argument: {Colors.BLUE} files selection by a windows\n{Colors.ENDC}\n"
        f"{Colors.BLUE}Examples:{Colors.ENDC}\n"
        f"\t> python pyCreateTh.py ./Tests/Entree.th --scale 1000\n"
        f"\t> python pyCreateTh.py Entree.th\n"
        f"\t> python pyCreateTh.py\n\n")
    args = parser.parse_args()
    
    if args.file == "":
        args.file = select_file_tk_window()
        # print(f"Selected file : {args.file}")    
        
    output_log = splitext(abspath(args.file))[0]+".log"    
    log = setup_logger(output_log, debug_log)
    
    # log.debug("Ceci est un message de debug")
    # log.info("Tout va bien")
    # log.warning("Attention, possible souci")
    # log.error("Une erreur est survenue")
    # log.critical("Erreur critique !")
         
    if os.name == 'posix':  os.system('clear') # Linux, MacOS
    elif os.name == 'nt':  os.system('cls')# Windows
    else: print("\n" * 100)
    
    #################################################################################################
    # Reading config.ini                                                                            #
    #################################################################################################
    try:
        config_file =  os.path.dirname(args.file) + "\\" + configIni
        if os.path.isfile(config_file):
            read_config(config_file)
        else :
            config_file = configIni
            read_config(configIni) 
        
    except ValueError as e:
        log.critical(f"Reading {configIni} file error: {Colors.ENDC}{e}")
        exit(0)
    
    
    #################################################################################################
    # titre                                                                                         #
    #################################################################################################
    _titre =[f'********************************************************************************************************************************************\033[0m', 
            f'* Conversion Th, Dat, Mak files to Therion files and folders',
            f'*       Script pyCreateTh by : {Colors.ENDC}alexandre.pont@yahoo.fr',
            f'*       Version :              {Colors.ENDC}{Version}',
            f'*       Input file :           {Colors.ENDC}{safe_relpath(args.file)}',           
            f'*       Output folder :        {Colors.ENDC}{safe_relpath(splitext(abspath(args.file))[0])}',
            f'*       Log file :             {Colors.ENDC}{os.path.basename(output_log)}',
            f'*       Config file:           {Colors.ENDC}{safe_relpath(config_file)}',
            f'*       ',
            f'*       ',
            f'********************************************************************************************************************************************\033[0m']     

    for i in range(11): log.info(_titre[i])     



        
    #################################################################################################
    # Fichier TH                                                                                    #
    ################################################################################################# 
    if args.file[-2:].lower() == "th" :
        flagErrorCompile, stat, totReadMeError, thread2 = create_th_folders(
                                                                ENTRY_FILE = abspath(args.file), 
                                                                TARGET = None, 
                                                                PROJECTION= args.proj,
                                                                SCALE = args.scale, 
                                                                UPDATE = args.update,
                                                                CONFIG_PATH = "")
        threads += thread2
        fileTitle = sanitize_filename(os.path.basename(args.file))[:-3]
        
        
    #################################################################################################
    # Fichier MAK                                                                                   #
    #################################################################################################    
    elif args.file[-3:].lower() == "mak" :
        
        SurveyTitleMak =  sanitize_filename(os.path.basename(abspath(args.file))[:-4])
        DEST_PATH = os.path.dirname(args.file) + '/' +  SurveyTitleMak
        
        if os.path.isdir(DEST_PATH):
            log.critical(f"The folder {Colors.ENDC}{SurveyTitleMak}{Colors.ERROR}{Colors.BOLD},  all ready exist : update mode is not possible for mak files")
            exit(0)
        
        fileTitle, thread2 = mak_to_th_file(abspath(args.file))    
        threads += thread2
        
        
    #################################################################################################
    # Fichier DAT                                                                                   #
    #################################################################################################    
    elif args.file[-3:].lower() == "dat" :
        _ConfigPath = "./"
        
        QtySections = 0
         
        ABS_file = abspath(args.file)
        
        content, val = load_text_file_utf8(ABS_file, os.path.basename(ABS_file))
        section = content.split('\x0c')
        QtySections += len(section)
        
        lines = section[0].split('\n')
        
        if lines[0] !="" :
            SurveyTitleDat =  sanitize_filename(lines[0]) 
            folderDest = os.path.dirname(args.file) + "\\" + SurveyTitleDat
        else :
            SurveyTitleDat = sanitize_filename(os.path.basename(args.file)[:-4])
            folderDest = os.path.dirname(args.file) + "\\" + SurveyTitleDat

        if os.path.isdir(folderDest):
                log.critical(f"The folder {Colors.ENDC}{SurveyTitleDat}{Colors.ERROR}{Colors.BOLD},  all ready exist : update mode is not possible for mak files")
                exit(0)
        
        with alive_bar(
                QtySections, 
                title=f"{Colors.GREEN}Surveys progress: {Colors.BLUE}",  
                length = 20, 
                enrich_print=False,
                stats=True,  # Désactive les stats par défaut pour plus de lisibilité
                elapsed=True,  # Optionnel : masque le temps écoulé
                monitor=True,  # Optionnel : masque les métriques (ex: "eta")
                bar="smooth"  # Style de la barre (autres options: "smooth", "classic", "blocks")
                ) as bar:
            with redirect_stdout(sys.__stdout__):
                for i in range(1): 
                    if globalData.error_count > 0:
                        bar.text(f"{Colors.INFO}, file: {Colors.ENDC}{os.path.basename(ABS_file)[:-4]}{Colors.ERROR}, error: {Colors.ENDC}{globalData.error_count}")
                    else :
                        bar.text(f"{Colors.INFO}, file: {Colors.ENDC}{os.path.basename(ABS_file)[:-4]}")
                    stationList, fileTitle, totReadMeError, thread2 = dat_to_th_files (ABS_file , fixPoints = [], crs_wkt = "", CONFIG_PATH = _ConfigPath, totReadMeError = "", bar = bar)
                    threads += thread2
                    bar()
        
    else :
        log.error(f"file {Colors.ENDC}{safe_relpath(args.file)}{Colors.ERROR} not yet supported")
        globalData.error_count += 1

    duration = (datetime.now() - start_time).total_seconds()
    
    for t in threads:
        t.join()

    destination_path = os.path.dirname(output_log) + "\\" + fileTitle 
    file_name = os.path.basename(output_log)
    destination_file = os.path.join(destination_path, file_name)
    
    wait_until_file_is_released(output_log)
    
    if globalData.error_count == 0 :    
        log.info(f"All files processed successfully in {Colors.ENDC}{duration:.2f}{Colors.INFO} secondes, without errors")
    else :
        log.error(f"There were {Colors.ENDC}{globalData.error_count}{Colors.ERROR} errors during {Colors.ENDC}{duration:.2f}{Colors.ERROR} secondes, check the log file: {Colors.ENDC}{os.path.basename(output_log)}")

    wait_until_file_is_released(output_log)
    release_log_file(log)
    
    
    # Supprimer le fichier cible s’il existe déjà
    if os.path.isfile(destination_file):
        os.remove(destination_file)

    shutil.move(output_log, destination_path)
    
        
    