"""
	!---------------------------------------------------------!
	!                                                         !
	!                    th to Therion                        !
	!                                                         !
	!           Code to transform the .th files               !
	!                                                         !
	!                  be used by Therion                     !
	!                                                         !
	!              Written by Alexandre Pont                  !
	!                                                         !
	!---------------------------------------------------------!

	 ENGLISH :
            Création Alex 2026 01 09

  
	TODOS : -....
"""

#################################################################################################
#################################################################################################
import os, re, argparse, shutil, sys, time, math, logging
from os.path import isfile, join, abspath, splitext
from pathlib import Path
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
from Lib.general_fonctions import setup_logger, Colors, safe_relpath, colored_help
from Lib.general_fonctions import load_config, select_file_tk_window, release_log_file, sanitize_filename
from Lib.general_fonctions import copy_template_if_not_exists, add_copyright_header, copy_file_with_copyright, update_template_files, load_text_file_utf8
import Lib.global_data as globalData
from Lib.pytro2th.tro2th import convert_tro   #Version local modifiée
from Lib.trox2th import analyse_xml_balises

log = logging.getLogger("Logger")


#################################################################################################
def align_points(smoothX1, smoothY1, X, Y, smoothX2, smoothY2):
    """Aligne les points en fonction de leur position l'un par rapport à l'autre.

    Args:
        smoothX1 (float): Coordonnée X du premier point lissé.
        smoothY1 (float): Coordonnée Y du premier point lissé.
        X (float): Coordonnée X du point central.
        Y (float): Coordonnée Y du point central.
        smoothX2 (float): Coordonnée X du deuxième point lissé.
        smoothY2 (float): Coordonnée Y du deuxième point lissé.

    Raises:
        ValueError: Si les deux points lissés sont confondus.

    Returns:
        tuple: Les coordonnées des points lissés alignés.
    """

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
def add_start_end_splays(df_splays_complet, df_equates):
    """Ajoute des splays de début et de fin au DataFrame des splays.

    Args:
        df_splays_complet (pd.DataFrame): Le DataFrame complet des splays.
        df_equates (pd.DataFrame): Le DataFrame des équivalences.

    Returns:
        pd.DataFrame: Le DataFrame des splays mis à jour avec les nouveaux splays.
    """

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


#################################################################################################
def convert_to_line_polaire_df(df_lines):
    """Convertit un DataFrame de lignes cartésiennes (x1, y1, x2, y2, name1, name2)
    en un DataFrame avec représentation polaire (x1, y1, azimut_deg, longueur, name1, name2).

    Args:
        df_lines (pd.DataFrame): Le DataFrame contenant les lignes à convertir.

    Returns:
        pd.DataFrame: Un DataFrame avec les colonnes polaires.
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
def assign_groups_and_ranks(df_lines):
    """Assigne des groupes et des rangs aux lignes du DataFrame.

    Args:
        df_lines (pd.DataFrame): Le DataFrame contenant les lignes à traiter.

    Returns:
        pd.DataFrame: Un DataFrame avec les colonnes "group_id" et "rank_in_group" ajoutées.
    """

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

    # Noeuds ayant un degré différent de 2
    start_nodes = [n for n in G.nodes if G.degree(n) != 2]

    # Si tous les nœuds ont un degré 2 : cycle fermé
    if not start_nodes:
        start_nodes = [list(G.nodes)[0]]

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

    # Ajout de la colonne max_rank (si possible)
    if not df_result.empty and "group_id" in df_result.columns:
        max_ranks = df_result.groupby("group_id")["rank_in_group"].max().reset_index()
        max_ranks.rename(columns={"rank_in_group": "max_rank"}, inplace=True)
        max_ranks["max_rank"] = max_ranks["max_rank"].astype(int)
        df_equates = df_equates.merge(max_ranks, on="group_id", how="left")
    else:
        df_equates["max_rank"] = 0

    # Ajout de la colonne start_group (raccord logique avec un autre groupe)
    end_to_group = df_equates[["end_point", "group_id"]].copy()
    end_to_group.rename(columns={"end_point": "start_point", "group_id": "start_group"}, inplace=True)
    end_to_group["start_point"] = end_to_group["start_point"].astype(str)
    df_equates = df_equates.merge(end_to_group, on="start_point", how="left")

    # Remplacer les NaN dans start_group par 0
    df_equates["start_group"] = df_equates["start_group"].fillna(0).astype(int)

    return df_result, df_equates


#################################################################################################
def wall_construction_smoothed(df_lines, df_splays, x_min, x_max, y_min, y_max):
    """Construit les murs en utilisant les lignes et les splays fournis.

    Args:
        df_lines (pd.DataFrame): Le DataFrame des lignes.
        df_splays (pd.DataFrame): Le DataFrame des splays.
        x_min (float): La coordonnée X minimale.
        x_max (float): La coordonnée X maximale.
        y_min (float): La coordonnée Y minimale.
        y_max (float): La coordonnée Y maximale.

    Returns:
        list: Une liste de murs construits.
    """   

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
                    
            df_splays_complet.loc[idx, "bissectrice"] = match["azimut_deg"].values[0]
            df_splays_complet.loc[idx, "longueur_ref"] = match["longueur"].values[0]
            df_splays_complet.loc[idx, "group_id"] = group_id
            df_splays_complet.loc[idx, "rank_in_group"] = max_rank + 1

    df_splays_complet = add_start_end_splays(df_splays_complet, df_equates)
    
    df_splays_complet = df_splays_complet.sort_values(by=["group_id", "rank_in_group"]).reset_index(drop=True)
    
    df_splays_complet["delta_azimut"] = df_splays_complet["bissectrice"] - df_splays_complet["azimut_deg"]

    df_splays_complet["proj"] = np.sin(np.radians(df_splays_complet["bissectrice"] - df_splays_complet["azimut_deg"])) * df_splays_complet["longueur"]

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
def parse_xvi_file(thNameXvi):
    """Parse un fichier .xvi et extrait les stations et les lignes.

    Args:
        thNameXvi (str): chemin complet du fichier .xvi à lire.

    Returns:
        tuple: Un tuple contenant les stations, les lignes, et les bornes (x_min, x_max, y_min, y_max, x_ecart, y_ecart).
    """

    stations = {}
    lines = []
    splays = []

    with open(join(thNameXvi), "r", encoding="utf-8") as f:
        xvi_content = f.read()
        xviStations, xviShots = xvi_content.split("XVIshots")

        # Extraction des stations
        for line in xviStations.split("\n"):
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
        xValues = [float(value[0]) for value in stations.values()]
        yValues = [float(value[1]) for value in stations.values()]
        x_min, x_max = min(xValues), max(xValues)
        y_min, y_max = min(yValues), max(yValues)
        x_ecart = x_max - x_min
        y_ecart = y_max - y_min
                    
        for line in xviShots.split("\n"):
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
def parse_therion_surveys(file_path):
    """Découpe des surveys à partir d'un fichier Therion.

    Args:
        file_path (str): Le chemin d'accès au fichier à analyser.

    Returns:
        list: Une liste des noms des surveys trouvés dans le fichier.
    """   
    survey_names = []
    
    try:
        file, val, encodage = load_text_file_utf8(file_path, os.path.basename(file_path))       
        # lines = file.readlines()
        lines = file.splitlines()
        # with open(filepath, 'r', encoding=enc) as f:
        #         content = f.read()
        
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
# Création des fichiers et dossiers à partir d'un th file                                       #
#################################################################################################   
def create_th_folders(ENTRY_FILE, 
                    PROJECTION = "all", 
                    TARGET = "None", 
                    FORMAT = "th2", 
                    SCALE = "500", 
                    UPDATE = False, 
                    CONFIG_PATH = "",
                    totReadMeError = "",
                    args_file = "",
                    proj = "", ) :  

    """Création des dossiers et fichiers à partir d'un fichier .th
    
    Args:
        ENTRY_FILE (str): Chemin du fichier Therion d'entrée.
        PROJECTION (str): Type de projection à utiliser.
        TARGET (str): Cible de la projection.
        FORMAT (str): Format de sortie, par défaut "th2".
        SCALE (str): Échelle à utiliser, par défaut "500".
        UPDATE (bool): Indique si l'on met à jour les fichiers existants.
        CONFIG_PATH (str): Chemin vers le fichier de configuration Therion.
        totReadMeError (str): Message d'erreur pour le fichier README.
    
    Returns:
        bool: True si la création des dossiers et fichiers a réussi, False sinon.

    """
    
    threads = []
    totReadMe = ""
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
    log.info(f"Parsing therion survey entry file: {Colors.ENDC}{shortCurentFile}")

    survey_list = parse_therion_surveys(ENTRY_FILE)
    
    if TARGET == "None" :
        if len(survey_list) > 1 : 
            log.critical(f"Multiple surveys were found, not yet implemented{Colors.ENDC}")
            exit(1)  
    
    TARGET = survey_list[0]
    
    log.info(f"Parsing therion survey target: {Colors.ENDC}{TARGET}")        
    
    loader = SurveyLoader(ENTRY_FILE)
    survey = loader.get_survey_by_id(survey_list[0])
    
    if not survey:
        raise NoSurveysFoundException(f"No survey found with that selector")
    
    if UPDATE : 
        DEST_PATH = os.path.dirname(args_file)
        log.info(f"Update th2 files: {Colors.ENDC}{DEST_PATH}")
        log.debug(f"\t{Colors.BLUE}survey_file :  {Colors.ENDC} {args_file}")
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
        thFile = Path(DEST_PATH + "\\" + TH_NAME + ".th")
        thName = Path(DEST_PATH + "\\" + TH_NAME)

    else :
        thFile = Path(DEST_PATH + "\\Data\\" + TH_NAME + ".th")  
        thName = Path(DEST_PATH + "\\Data\\" + TH_NAME) 

    template_args = {
            "th_file": thFile,  
            "selector": survey.therion_id,
            "th_name": thName, 
            "XVIscale": globalData.XVIScale,
    }

    logfile, tmpdir, totReadMeError = compile_template(globalData.thconfigTemplate, template_args, totReadMeError, cleanup=False, therion_path=globalData.therionPath)
    
    shutil.rmtree(tmpdir)  
    
    if totReadMeError == "" : totReadMeError += f"\tNo errors found in {os.path.basename(thFile)}, perfect!\n"
    
    if logfile == "Therion error":
        # log.error(f"Therion error in: {Colors.ENDC}{TH_NAME}")   
        flagErrorCompile = True
        stat = {"length": 0, "depth": 0}
        log.info(f"File: {Colors.ENDC}{os.path.basename(thFile)}{Colors.INFO}, compilation error, length: {Colors.ENDC}{stat["length"]}m{Colors.INFO}, depth: {Colors.ENDC}{stat["depth"]}m")   
        totReadMe = f"\t{os.path.basename(thFile)} compilation error length: {stat["length"]} m, depth: {stat["depth"]} m\n"
    
    else : 
        flagErrorCompile = False
        stat = get_stats_from_log(logfile)
        log.info(f"File: {Colors.ENDC}{os.path.basename(thFile)}{Colors.INFO}, compilation successful, length: {Colors.ENDC}{stat["length"]}m{Colors.INFO}, depth: {Colors.ENDC}{stat["depth"]}m")   
        totReadMe = f"\t{os.path.basename(thFile)} compilation successful length: {stat["length"]} m, depth: {stat["depth"]} m\n"
         
        
    #################################################################################################    
    # Update files                                                                                  #
    #################################################################################################
    if not UPDATE: 
        
        # proj = args.proj.lower()
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
            'XVIscale' : globalData.XVIScale,
            'extended' : extended,
            'XVIscale' : globalData.XVIScale,
            'readMeList': str(totReadMe),
            'errorList' : str(totReadMeError),
            'fixPointList' : str(" "),
            'other_scraps_plan' : "",
            'file_info' : f'# File generated by pyCreateTh.py version: {globalData.Version} date: {datetime.now().strftime("%Y.%m.%d %H:%M:%S")}',
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
            thNameXvi =  DEST_PATH + "/" + TH_NAME + "-Plan.xvi" 
        else :     
            thNameXvi =  DEST_PATH + "/Data/" + TH_NAME + "-Plan.xvi" 

        log.info(f"Parsing Plan XVI file: {Colors.ENDC}{safe_relpath(thNameXvi)}")

        stations = {}
        lines = []
        
        stations, lines, splays, x_min, x_max, y_min, y_max, x_ecart, y_ecart = parse_xvi_file(thNameXvi)
        
        # df_stations = pd.DataFrame.from_dict(stations, orient='index')
        df_lines = pd.DataFrame(lines, columns=["x1", "y1", "x2", "y2", "name1", "name2"])
        df_splays = pd.DataFrame(splays, columns=["x1", "y1", "x2", "y2", "name1", "name2"]).drop_duplicates()
        
        df_splays["is_zero_length"] = (df_splays["x1"] == df_splays["x2"]) & (df_splays["y1"] == df_splays["y2"])
        

        # Identifier les groupes avec au moins un splay non nul
        non_zero_groups = df_splays.loc[~df_splays["is_zero_length"], ["name1", "name2"]]
        non_zero_group_keys = set(tuple(x) for x in non_zero_groups.to_numpy())
        
        df_splays = df_splays[(~df_splays["is_zero_length"]) | df_splays[["name1", "name2"]].apply(tuple, axis=1).isin(non_zero_group_keys) ]

        # Supprimer la colonne temporaire si elle existe
        if "is_zero_length" in df_splays.columns:
            df_splays = df_splays.drop(columns="is_zero_length")
    
        th2_walls = []

        if globalData.wallLinesInTh2 :
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
                            walls="\n".join(th2_walls) if globalData.wallLinesInTh2 else "",
                            names="\n".join(th2_names) if globalData.stationNamesInTh2 else "",
                            projection="plan",
                            projection_short="P",
                            author=globalData.Author,
                            year=datetime.now().year,
                            version = globalData.Version,
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
                                                + os.path.basename(thNameXvi) + " 0 {}",                         
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
            thNameXvi =  DEST_PATH + "/" + TH_NAME + "-Extended.xvi" 
        else :
            thNameXvi =  DEST_PATH + "/Data/" + TH_NAME + "-Extended.xvi" 

        log.info(f"Parsing extended XVI file: {Colors.ENDC}{safe_relpath(thNameXvi)}")

        # Parse the Extended XVI file
        stations = {}
        lines = []
        
        stations, lines, splays, x_min, x_max, y_min, y_max, x_ecart, y_ecart = parse_xvi_file(thNameXvi)
        
        # df_stations = pd.DataFrame.from_dict(stations, orient='index')
        df_lines = pd.DataFrame(lines, columns=["x1", "y1", "x2", "y2", "name1", "name2"])
        df_splays = pd.DataFrame(splays, columns=["x1", "y1", "x2", "y2", "name1", "name2"]).drop_duplicates()

        df_splays["is_zero_length"] = (df_splays["x1"] == df_splays["x2"]) & (df_splays["y1"] == df_splays["y2"])

        # Identifier les groupes avec au moins un splay non nul
        non_zero_groups = df_splays.loc[~df_splays["is_zero_length"], ["name1", "name2"]]
        non_zero_group_keys = set(tuple(x) for x in non_zero_groups.to_numpy())
        
        df_splays = df_splays[(~df_splays["is_zero_length"]) | df_splays[["name1", "name2"]].apply(tuple, axis=1).isin(non_zero_group_keys) ]


        # Supprimer la colonne temporaire si elle existe
        if "is_zero_length" in df_splays.columns:
            df_splays = df_splays.drop(columns="is_zero_length")
        
        th2_walls = []
        
        if globalData.wallLinesInTh2 :
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
                            walls="\n".join(th2_walls) if globalData.wallLinesInTh2 else "",
                            names="\n".join(th2_names) if globalData.stationNamesInTh2 else "",
                            projection="extended",
                            projection_short="C",
                            author=globalData.Author,
                            year=datetime.now().year,
                            version = globalData.Version,
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
                                                + os.path.basename(thNameXvi) + " 0 {}",                         
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
                        'file_info' : f"# File generated by pyCreateTh.py version {globalData.Version} date: {datetime.now().strftime("%Y.%m.%d-%H:%M:%S")}",
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

