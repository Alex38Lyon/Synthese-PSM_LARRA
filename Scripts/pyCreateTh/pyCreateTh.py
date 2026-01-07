
"""
#############################################################################################
#                                                                                       	#  
#              Script pour convertir des données topographiques des formats                 #
#                          .th de Therion (brut, sans les dossiers)                         #
#                               .mak ou .dat de compass                                     #
#                                  .tro de visual topo                                      #
#                                                                                           #   
#                           au format th et th2 de Therion                              	#
#                     by Alexandre PONT (alexandre_pont@yahoo.fr)                         	#
#                                                                                          	#
# Définir les différentes variables dans fichier config.ini                                 #
#                                                                                           #
# Usage : python pyCreateTh.py                                                              #
#         Commandes : pyCreateTh.py --help                                                  #
#                                                                                       	#  
#############################################################################################

Merci à :
        - Tanguy Racine pour les scripts                        https://github.com/tr1813
        - Xavier Robert pour les principes de base              https://github.com/robertxa
        - Xavier Robert pour les scripts de conversion .tro     https://github.com/robertxa/pytherion
        - Benoit Urruty                                         https://github.com/BenoitURRUTY
        
Sources documentaires : 
        - Format des fichiers compass : https://fountainware.com/compass/Documents/FileFormats/FileFormats.htm


Création Alex le 2025 06 09
                                        
En cours :
    - Exports Tro :
        - Pas possible de gérer les fichiers tro avec plusieurs entrées / points fixes car pas sauvegardé dans le format tro
        - gérer les déclinaison si une date est présente et si une coordonnées
        - gérer pour ne pas avoir de copie de config.ini
        - gérer "# explo-team"
    - Exports TroX
        - A créer pour avoir notamment les réseaux à plusieurs entrées 
    - Exports DAT/MARK
        - gérer Flags '# #|LP#' not implemented in therion
    - tester avec les dernières option de la version de DAT (CORRECTION2 et suivants)
    - améliorer fonction wall shot pour faire habillage des th2 files, les jointures...
        - traiter les series avec 1 ou 2 stations
    - PB des cartouches et des échelles pour faire des pdf automatiquement

"""
 
#################################################################################################
#################################################################################################
import os, re, argparse, shutil, sys, time, math
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
from Lib.general_fonctions import load_config, select_file_tk_window, release_log_file, sanitize_filename, load_text_file_utf8
from Lib.general_fonctions import copy_template_if_not_exists, add_copyright_header, copy_file_with_copyright, update_template_files
import Lib.global_data as globalData
from Lib.pytro2th.tro2th import convert_tro   #Version local modifiée
from Lib.trox2th import analyse_xml_balises
from Lib.th2th import create_th_folders


#################################################################################################
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
def parse_therion_centerline(file_data):
    """Découpe des centerline Therion et extrait :
       - DATA   : lignes de tirs
       - date   : date du levé
       - type   : liste des stations
       - lines  : bloc complet
    """
    centerline_list = []

    try:
        lines = file_data.splitlines()

        current_block = []
        current_data = []
        current_date = None
        current_stations = set()
        in_centerline = False

        for line in lines:
            stripped = line.strip()
            low = stripped.lower()

            # Début centerline
            if low.startswith("centerline"):
                in_centerline = True
                current_block = [line]
                current_data = []
                current_date = None
                current_stations = set()
                continue

            if not in_centerline:
                continue

            current_block.append(line)

            # Commentaire ou vide
            if not stripped or stripped.startswith("#"):
                continue

            # Date
            m = re.match(r"^[ \t]*date\s+(.+)$", line, re.IGNORECASE)
            if m:
                current_date = m.group(1).strip()
                continue

            parts = stripped.split()

            # Ligne DATA (tir)
            if len(parts) >= 2 and parts[0].lower() not in globalData.THERION_KEYWORDS:
                current_data.append(line)

                for p in parts[:2]:
                    if (
                        p.lower() not in globalData.THERION_KEYWORDS
                        and not re.match(r"^[0-9.+-]+$", p)
                    ):
                        current_stations.add(p)

            # Fin centerline
            if low.startswith("endcenterline"):
                centerline_list.append({
                    "lines": current_block,
                    "DATA": current_data,    
                    "date": current_date,
                    "type": sorted(current_stations)
                })

                in_centerline = False
                current_block = []
                current_data = []
                current_date = None
                current_stations = set()

    except Exception as e:
        log.error(f"An error occurred (parse_therion_centerline): {Colors.ENDC}{e}")
        globalData.error_count += 1

    return centerline_list


#################################################################################################
def regroupe_date(centerline_list):
    """Regroupe les centerlines par date et concatène les champs.

    Args:
        centerline_list (list): liste de dicts contenant :
            - lines (list)
            - DATA  (list)
            - date  (str|None)
            - type  (list)

    Returns:
        list: liste de dicts regroupés par date
    """
    grouped = {}

    try:
        for idx, cl in enumerate(centerline_list):

            # Sécurité : cl doit être un dict
            if not isinstance(cl, dict):
                log.warning(f"regroupe_date: entrée ignorée (index {idx}, type invalide)")
                continue

            date = cl.get("date")

            if date not in grouped:
                grouped[date] = {
                    "date": date,
                    "lines": [],
                    "DATA": [],
                    "type": set()
                }

            # Concaténations sécurisées
            if isinstance(cl.get("lines"), list):
                grouped[date]["lines"].extend(cl["lines"])

            if isinstance(cl.get("DATA"), list):
                grouped[date]["DATA"].extend(cl["DATA"])

            if isinstance(cl.get("type"), (list, set)):
                grouped[date]["type"].update(cl["type"])

        # Finalisation (conversion set → list)
        result = []
        for g in grouped.values():
            g["type"] = sorted(g["type"])
            result.append(g)

        return result

    except Exception as e:
        log.error(f"An error occurred (regroupe_date): {Colors.ENDC}{e}")
        globalData.error_count += 1
        return []


################################################################################################# 
# lecture d'un fichier .mak                                                                     #
#################################################################################################    
def mak_to_th_file(ENTRY_FILE) :
    """Convertit un fichier .mak en fichier .th.

    Args:
        ENTRY_FILE (str): Le chemin vers le fichier .mak d'entrée.

    Returns:
        bool: True si la conversion a réussi, False sinon.
        
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
    
    
    log.info(f"Reading mak file: {Colors.ENDC}{shortCurentFile}{Colors.GREEN}, fixed station: {Colors.ENDC}{len(fixPoints)}{Colors.GREEN}, files : {Colors.ENDC}{len(datFiles)}{Colors.GREEN}, UTM Zone : {Colors.ENDC}{UTM[0]}{Colors.GREEN}, Datum : {Colors.ENDC}{next(iter(Datums))}{Colors.GREEN}, SCR : {Colors.ENDC}{crs_wkt}")
    totReadMeFixPoint = f"\t* Source mak file : {os.path.basename(ENTRY_FILE)}, fixed station: {len(fixPoints)}, files : {len(datFiles)}, UTM Zone : {UTM[0]}, Datum : {next(iter(Datums))}, SCR : {crs_wkt}\n" 
     
    QtySections = 0
    
    for file in datFiles :       
        ABS_file = os.path.dirname(abspath(args.file)) + "\\"+ file
        content, val, encodage = load_text_file_utf8(ABS_file, os.path.basename(ABS_file))
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
                    bar.text(f"{Colors.INFO}file: {Colors.ENDC}{file[:-4]}{Colors.ERROR}, error: {Colors.ENDC}{globalData.error_count}")
                else :
                    bar.text(f"{Colors.INFO}file: {Colors.ENDC}{file[:-4]}")
                
                _file = os.path.dirname(abspath(args.file)) + "\\" + file
                shutil.copy(_file, folderDest + "\\Data\\")
                ABS_file = folderDest + "\\Data\\" + file

                totReadMeError += f"\t* file: {file}\n"
                totReadMeList += f"\tfile: {file}\n"

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

        log.info(f"Total des '{Colors.ENDC}equates{Colors.INFO}' in mak file: {Colors.ENDC}{len(tableau_equate)}{Colors.INFO} in {Colors.ENDC}{safe_relpath(args.file)}")
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
                    'file_info' : f"# File generated by pyCreateTh.py version: {globalData.Version} date: {datetime.now().strftime("%Y.%m.%d-%H:%M:%S")}",
            }

    DEST_PATH = os.path.dirname(args.file) + '/' +  SurveyTitleMak

    update_template_files(DEST_PATH + '/template.thconfig', config_vars, DEST_PATH + '/' +  SurveyTitleMak + '.thconfig')
    update_template_files(DEST_PATH + '/template-tot.th', config_vars, DEST_PATH + '/' + SurveyTitleMak + '-tot.th')
    update_template_files(DEST_PATH + '/template-maps.th', config_vars, DEST_PATH + '/' +  SurveyTitleMak + '-maps.th')
    
    #################################################################################################     
    # Final therion compilation                                                                     #
    #################################################################################################
 
    if globalData.finalTherionExe == True:
        FILE = DEST_PATH + '/' +  SurveyTitleMak + '.thconfig'      
        t =  compile_file(FILE, therion_path=globalData.therionPath) 
        threads.append(t)
        
        for thread in threads:  # Attendre que tous les threads se terminent
            thread.join()
            
        logfile = (DEST_PATH + '/therion.log').replace("\\", "/")   
        
        with open(logfile, 'r') as f:
            content = f.read()
            # print(content)
        
        stat = get_stats_from_log(content)
        
        if stat["length"] != 0.0 and stat["depth"] != 0.0 :
            totReadMeList += f"\tFinal compilation successful length: {stat["length"]} m, depth: {stat["depth"]} m\n"
            log.info(f"Final compilation successful length: {Colors.ENDC}{stat["length"]}{Colors.INFO} m, depth: {Colors.ENDC}{stat["depth"]}{Colors.INFO} m")
        else :
            totReadMeList += f"\tFinal compilation error, check log file\n"
            log.error(f"Final compilation error, check log file")
                    
    config_vars['readMeList'] = totReadMeList

    update_template_files(DEST_PATH + '/template-readme.md', config_vars, DEST_PATH +'/' + SurveyTitle + '-readme.md')
    
    
    return SurveyTitleMak, threads


#################################################################################################
def station_list_dat(data, list, fixPoints, currentSurveyName) :  
    """Crée une liste de stations à partir des données fournies issues d'un fichier dat.

    Args:
        data (DataFrame): Les données d'entrée contenant les informations sur les stations.
        list (DataFrame): La liste des stations existantes.
        fixPoints (list): Les points de fixation à considérer.
        currentSurveyName (str): Le nom de l'enquête en cours.

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
def station_list_th(data, list, fixPoints, currentSurveyName) :  
    """Crée une liste de stations à partir des données fournies  issues d'un fichier tro.

    Args:
        data (DataFrame): Les données d'entrée contenant les informations sur les stations.
        list (DataFrame): La liste des stations existantes.
        fixPoints (list): Les points de fixation à considérer.
        currentSurveyName (str): Le nom de l'enquête en cours.

    Returns:
        DataFrame: La liste mise à jour des stations.
        
    """
    
    # Création d'un DataFrame à partir des données  
    rows1 = [line.split() for line in data['DATA']]
    dfDATA = pd.DataFrame(rows1)
    
    # stations = pd.concat([dfDATA.iloc[1:, 0], dfDATA.iloc[1:, 1]]).drop_duplicates().str.replace('[', '%').str.replace(']', '%%').str.replace('@', '_._')
    # stations = pd.concat([dfDATA.iloc[1:, 0], dfDATA.iloc[1:, 1]]).drop_duplicates().stationName() 
    # stations = pd.concat([dfDATA.iloc[:, 0], dfDATA.iloc[:, 1]]).drop_duplicates().reset_index(drop=True)
    
    stations = pd.concat([dfDATA.iloc[:, 0], dfDATA.iloc[:, 1]]).dropna().astype(str).loc[lambda s: ~s.isin(["-", "*"])].drop_duplicates().reset_index(drop=True)
    
    # print(stations)
    
    fixed_names = {point[0] for point in fixPoints}
    stations = stations[~stations.isin(fixed_names)]
    
    new_entries = pd.DataFrame({
        'StationName': stations,
        'Survey_Name_01': currentSurveyName
    })
    
    list = pd.concat([list, new_entries], ignore_index=True)
    
    # print(new_entries)
    
    return list, dfDATA


#################################################################################################
def formated_station_list(df, dataFormat, unit = "meter", shortCurentFile ="None") :
    """Formate une liste de stations à partir d'un DataFrame.
    Args:
        df (DataFrame): Le DataFrame contenant les données des stations.
        dataFormat (str): Le format des données à utiliser pour le traitement.
        unit (str): L'unité de mesure à utiliser (par défaut "meter").
        shortCurentFile (str): Le nom du fichier en cours de traitement (pour les logs).
        
    Returns:
        DataFrame: Le DataFrame formaté avec les colonnes appropriées.
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

        # Si la colonne 10 contient #|PL#    exclude from plotting and Length i.e splay
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
    """Finds duplicates in the data based on SURVEY_DATE and SURVEY_TEAM.
    
    Args: 
        data (list): A list of dictionaries containing survey data.   

    Returns:
        list: A list of dictionaries containing information about duplicates found.
        
    """
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


#################################################################################################
def find_duplicates_by_date(data):
    """Finds duplicates in the data based on SURVEY_DATE.

    Args:
        data (list): A list of dictionaries containing survey data.

    Returns:
        list: A list of dictionaries containing information about duplicates found.
    """
    
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
    """Extrait les points uniques de la colonne 0 du DataFrame 'data' et les compare avec la colonne 1.
    Exclut les points présents dans 'crs_wkt' si fourni.

    Args:
        data (DataFrame): Le DataFrame contenant les données.
        crs_wkt (list, optional): Une liste de points à exclure.

    Returns:
        list: Une liste de points uniques.
    """

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
    """Merges duplicate survey entries into a single entry.

    Args:
        data (list): A list of dictionaries containing survey data.
        duplicates (list): A list of dictionaries containing information about duplicates found.
        id_offset (int, optional): An offset to apply to the IDs of merged entries. Defaults to 10000.

    Returns:
        list: A list of merged survey entries.
        
    """
    
    
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
def dat_survey_format_extract(section_data, headerData, currentSurveyName, fichier, totReadMeError):
    """Extracts and validates the format code from the section data.

    Args:
        section_data (dict): The section data containing survey information.
        headerData (dict): The header data for the survey.
        currentSurveyName (str): The name of the current survey.
        fichier (str): The file being processed.
        totReadMeError (str): A string to accumulate error messages.

    Returns:
        dataFormat (str), length (int), compass (str), clino (str), totReadMeError (str)

    """
    
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
    dataFormat =  " " + headerData[5].lower()
    dataFormat += " " + headerData[6].lower()
    dataFormat += " " + headerData[7].lower()
    dataFormat += " " + headerData[8].lower()   
    
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
        

################################################################################################# 
# Convertit un fichier .tro en fichiers .th                                                     #
#################################################################################################  
def tro_to_th_files(ENTRY_FILE, centerlines = [], 
                    entrance = "", 
                    fileTitle = "", 
                    coordinates = [], 
                    coordsyst = "", 
                    fle_th_fnme = "", 
                    CONFIG_PATH = "", 
                    totReadMeError = "", 
                    bar=None) :
    """
    Convertit un fichier .tro en fichiers .th

    Args:
        ENTRY_FILE (str): Le chemin vers le fichier .dat d'entrée.
        fixPoints (list, optional): Liste des points de fixation. Defaults to [].
        crs_wkt (str, optional): Le système de référence spatiale en WKT. Defaults to "".
        CONFIG_PATH (str, optional): Le chemin vers le fichier de configuration. Defaults to "".
    
    Returns:
        tuple: Un tuple contenant un DataFrame des stations et le nom du survey.
        
    """    

    #################################################################################################     
    # 1 : Initialisations                                                                           #
    ################################################################################################# 
    data = []
    unique_id = 1
    totdata = f"\t## Input list:\n"
    totMapsPlan = ""
    totMapsExtended = ""
    totReadMeErrorDat = ""
    maps = ""
    plan = ""
    extended = ""
    totReadMe = ""
    surveyCount = 0    
    totReadMeFixPoint = f"\tcs {coordsyst}\n"
    totReadMeFixPoint += f"\tFix point: {entrance} [{coordinates[0]} km, {coordinates[1]} km, {coordinates[2]} m]\n"
    listStationSection = pd.DataFrame(columns=['StationName', 'Survey_Name'])
    threads = []    
    fixPoints = []
    fixPoints.append([entrance, " ", coordinates[0], coordinates[1], coordinates[2]])
    
    log.debug(f"{Colors.INFO}------------------------------------------------------------------------------------------------------------------{Colors.ENDC}")
    
    SurveyTitle = sanitize_filename(os.path.basename(ENTRY_FILE)[:-4])
    folderDest =  os.path.dirname(ENTRY_FILE) + "\\" + SurveyTitle
    
    copy_template_if_not_exists(globalData.templatePath,folderDest)
    
    #################################################################################################     
    # 2 : Boucle pour convertir les centerlines                                                     #
    #################################################################################################
    
    for i, cl in enumerate( sorted(centerlines, key=lambda x: (x['date'] is None, x['date'])), start=1 ):
    
        currentSurveyName = f"{globalData.SurveyPrefixName}{i:02d}_{sanitize_filename(cl['date'])}"
        fileName = folderDest + "\\Data\\" + currentSurveyName + ".th"
    
        log.debug(f"{Colors.INFO}Centerline # {Colors.ENDC}{i}")
        log.debug(f"{Colors.INFO}Date : {Colors.ENDC}{cl['date']}")
        log.debug(f"{Colors.INFO}Stations: {Colors.ENDC}{cl['DATA']}")
        log.debug(f"{Colors.INFO}Lignes :{Colors.ENDC}")
        
        add_lines = "\nencoding utf-8\n" 
        add_lines+= f"# File generated by pyCreateTh.py version: {globalData.Version} date: {datetime.now().strftime("%Y.%m.%d %H:%M:%S")}\n"
        add_lines+= f'\nsurvey {globalData.SurveyPrefixName}{i:02d}_{sanitize_filename(cl['date'])} -title "{fileTitle} Explo num {i:02d}"'
        
        cl['lines'] = [add_lines] + cl['lines'] + ["endsurvey"]
        
        with open(str(fileName), "w+", encoding="utf-8") as f:
            for line in cl['lines']:
                log.debug(line)
                f.write(f"{line}\n")
                
            f.write(f"\n\n#############################################################################################")
            f.write(f"\n# Originals data file : {args.file}")
            if globalData.error_count == 0 :   
                f.write(f"\n# Conversion with pyCreateTh version {globalData.Version}, the {datetime.now().strftime("%Y.%m.%d %H:%M:%S")}, without error")
            else :
                f.write(f"\n# Conversion with pyCreateTh version {globalData.Version}, the {datetime.now().strftime("%Y.%m.%d %H:%M:%S")}, with {globalData.error_count} error(s)")

            f.write(f"\n#############################################################################################\n\n")
            for line in source_content.splitlines():
                f.write(f"# {line}\n")  
            
            log.debug(f"{Colors.INFO}------------------------------------------------------------------------------------------------------------------{Colors.ENDC}")

        # Ajouter les données de la section à la liste
        if len(cl['DATA']) > 0 :
            listStationSection, dfDATA = station_list_th(cl, listStationSection, fixPoints, currentSurveyName)
            # print(f"Explo {i}, dfDATA : {dfDATA}")
            # print(listStationSection)
            
        StatCreateFolder, stat, totReadMeErrorDat, thread2 = create_th_folders(
                                                            fileName, 
                                                            TARGET = None, 
                                                            PROJECTION= args.proj, 
                                                            SCALE = args.scale, 
                                                            UPDATE = args.update, 
                                                            CONFIG_PATH = "", 
                                                            totReadMeError = totReadMeErrorDat,
                                                            args_file = args.file,
                                                            proj = args.proj.lower())
        threads += thread2
        
        log.info(f"File: {Colors.ENDC}{currentSurveyName}{Colors.INFO},  compilation successful, length: {Colors.ENDC}{stat["length"]}m{Colors.INFO}, depth: {Colors.ENDC}{stat["depth"]}m")   
        totReadMe += f"\t{currentSurveyName} compilation successful length: {stat["length"]} m, depth: {stat["depth"]} m\n"
         
        if not StatCreateFolder :
            totMapsPlan += f"\t{plan}MP-{currentSurveyName}-Plan-tot@{currentSurveyName}\n\t{plan}break\n"
            totMapsExtended += f"\t{extended}MC-{currentSurveyName}-Extended-tot@{currentSurveyName}\n\t{extended}break\n"
        surveyCount += 1
        
        
        totdata +=f"\tinput Data/{currentSurveyName}/{currentSurveyName}-tot.th\n" 
        
        _destination = fileName[:-3] + "\\Sources"
        destination_path = os.path.join(_destination, os.path.basename(fileName))
        shutil.move(fileName, destination_path)
        
        bar(1)     
        
    # pd.set_option("display.max_rows", None)
    # pd.set_option("display.max_columns", None)
    # pd.set_option("display.width", None)
        
    # print(f"{Colors.DEBUG}listStationSection : {Colors.ENDC}{listStationSection}")
    
    ################################################################################################# 
    # Gestion des equates 
    #################################################################################################
        
    totdata +=f"\n" 

    _stationList = listStationSection.copy()
    
    # On numérote les doublons de Survey_Name pour chaque StationName
    _stationList['Survey_Number'] = _stationList.groupby('StationName').cumcount() + 1
    
    # print(f"{Colors.DEBUG}_stationList : {Colors.ENDC}{_stationList}")
    
    # On pivote le tableau pour que chaque Survey_Name devienne une colonne
    tableau_pivot = _stationList.pivot(index='StationName', columns='Survey_Number', values='Survey_Name_01')
    
    tableau_pivot.columns = [f'Survey_Name_{i}' for i in tableau_pivot.columns]
    
    # print(f"{Colors.DEBUG}tableau_pivot : {Colors.ENDC}{tableau_pivot}{Colors.DEBUG} in {Colors.ENDC}{currentSurveyName}")
    
    totdata +=f"\n\t## equates list:\n"
    
    if 'Survey_Name_2' in tableau_pivot.columns:
        # On réinitialise l'index pour avoir StationName comme colonne normale
        tableau_pivot = tableau_pivot.reset_index()
        tableau_equate = tableau_pivot[tableau_pivot['Survey_Name_2'].notna()]

        log.info(f"Total 'equates' founds: {Colors.ENDC}{len(tableau_equate)}{Colors.INFO} in {Colors.ENDC}{currentSurveyName}")
        
        # print(f"{Colors.DEBUG}tableau_equate : {Colors.ENDC}{tableau_equate}")
        # print(f"{Colors.DEBUG}fixePoints : {Colors.ENDC}{fixPoints}{Colors.DEBUG} in {Colors.ENDC}{currentSurveyName}")
        
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
        log.info(f"No 'equates' found in {Colors.ENDC}{currentSurveyName}")
        
    totdata +=f"\n\t## Maps list:\n\t{maps}input {SurveyTitle}-maps.th\n"
    
    if totReadMeErrorDat == "" : totReadMeErrorDat += "\tThis file has no errors, perfect!\n"
        
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
                    'cs' : coordsyst if coordsyst != "" else globalData.cs,
                    'totData' : totdata,
                    'maps' :maps,
                    'plan': plan,
                    'XVIscale': globalData.XVIScale,
                    'extended': extended,
                    'configPath' : "",
                    'other_scraps_plan' : totMapsPlan,
                    'readMeList' : totReadMe,
                    'errorList' : totReadMeErrorDat,
                    'fixPointList' : totReadMeFixPoint,
                    'other_scraps_extended' : totMapsExtended,
                    'file_info' : f"# File generated by pyCreateTh.py version: {globalData.Version} date: {datetime.now().strftime("%Y.%m.%d-%H:%M:%S")}",
            }

    DEST_PATH = os.path.dirname(ENTRY_FILE) + '/' +  SurveyTitle

    update_template_files(DEST_PATH + '/template.thconfig', config_vars, DEST_PATH + '/' +  SurveyTitle + '.thconfig')
    update_template_files(DEST_PATH + '/template-tot.th', config_vars, DEST_PATH + '/' + SurveyTitle + '-tot.th')
    update_template_files(DEST_PATH + '/template-maps.th', config_vars, DEST_PATH + '/' +  SurveyTitle + '-maps.th')
   
    
    #################################################################################################     
    # Final therion compilation                                                                     #
    #################################################################################################

    if globalData.finalTherionExe == True:
        FILE = DEST_PATH + '/' +  SurveyTitle + '.thconfig'      
        t = compile_file(FILE, therion_path=globalData.therionPath) 
        threads.append(t)
        
        for thread in threads:  # Attendre que tous les threads se terminent
            thread.join()
            
        logfile = (DEST_PATH + '/therion.log').replace("\\", "/")   
        
        with open(logfile, 'r') as f:
            content = f.read()
            # print(content)
        
        stat = get_stats_from_log(content)
        
        if stat["length"] != 0.0 and stat["depth"] != 0.0 :
            totReadMe += f"\tFinal compilation successful length: {stat["length"]} m, depth: {stat["depth"]} m\n"
            log.info(f"Final compilation successful length: {Colors.ENDC}{stat["length"]}{Colors.INFO} m, depth: {Colors.ENDC}{stat["depth"]}{Colors.INFO} m")
        else :
            totReadMe += f"\tFinal compilation error, check log file\n"
            log.error(f"Final compilation error, check log file")
                    
    config_vars['readMeList'] = totReadMe

    update_template_files(DEST_PATH + '/template-readme.md', config_vars, DEST_PATH +'/' + SurveyTitle + '-readme.md')
    
    return _stationList, SurveyTitle, totReadMeError, threads
        
    
################################################################################################# 
# Convertit un fichier .dat en fichiers .th                                                     #
#################################################################################################  
def dat_to_th_files (ENTRY_FILE, fixPoints = [], crs_wkt = "", CONFIG_PATH = "", totReadMeError = "", bar=None) :
    """
    Convertit un fichier .dat en fichiers .th

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
        
    content, totReadMe, enc = load_text_file_utf8(ENTRY_FILE, shortCurentFile)
    
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
            listStationSection, dfDATA = station_list_dat(section_data, listStationSection, fixPoints, section_data['SURVEY_NAME'])
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

        stationList, dfDATA = station_list_dat(_line, stationList, fixPoints, currentSurveyName)

        headerData = dfDATA.iloc[0].tolist()
              
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
                fixPoint +=  f'\t\tstation	{point[0]} "{point[0]}" entrance\n' 
        
         
        ################################################################################################# 
        # Gestion des formats
        ################################################################################################# 
        
        dataFormat, length, compass, clino, totReadMeErrorDat = dat_survey_format_extract(_line, headerData, currentSurveyName, shortCurentFile, totReadMeErrorDat)
        
        if "grads" in compass:
            _compass = "grads" 
        else: 
            _compass = "degree"
        
        ################################################################################################# 
        # Gestion des formats
        ################################################################################################# 
        
        with open(str(output_file), "w+", encoding="utf-8") as f:
            f.write(globalData.thFileDat.format(
                    VERSION = globalData.Version,
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
                                        totReadMeError = totReadMeErrorDat,
                                        args_file = args.file,
                                        proj = args.proj.lower()
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
            bar.text(f"{Colors.INFO}file: {Colors.ENDC}{os.path.basename(ENTRY_FILE)[:-4]}{Colors.INFO}, survey: {Colors.ENDC}{currentSurveyName}{Colors.ERROR}, error: {Colors.ENDC}{globalData.error_count}")
        else :
            bar.text(f"{Colors.INFO}file: {Colors.ENDC}{os.path.basename(ENTRY_FILE)[:-4]}{Colors.INFO}, survey: {Colors.ENDC}{currentSurveyName}")
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

        log.info(f"Total '{Colors.ENDC}equates{Colors.INFO}' founds : {Colors.ENDC}{len(tableau_equate)}{Colors.INFO} in {Colors.ENDC}{shortCurentFile}")
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
        log.info(f"No '{Colors.ENDC}equates{Colors.INFO}' found in {Colors.ENDC}{ENTRY_FILE}")
             
    totdata +=f"\n\t## Maps list:\n\t{maps}input {SurveyTitle}-maps.th\n"
    
    if totReadMeErrorDat == "" : totReadMeErrorDat += "\tNo errors in the file, that's excellent !\n"
        
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
                    'file_info' : f"# File generated by pyCreateTh.py version: {globalData.Version} date: {datetime.now().strftime("%Y.%m.%d-%H:%M:%S")}",
            }

    DEST_PATH = os.path.dirname(ENTRY_FILE) + '/' +  SurveyTitle

    update_template_files(DEST_PATH + '/template.thconfig', config_vars, DEST_PATH + '/' +  SurveyTitle + '.thconfig')
    update_template_files(DEST_PATH + '/template-tot.th', config_vars, DEST_PATH + '/' + SurveyTitle + '-tot.th')
    update_template_files(DEST_PATH + '/template-maps.th', config_vars, DEST_PATH + '/' +  SurveyTitle + '-maps.th')
    
    #################################################################################################     
    # Final therion compilation                                                                     #
    #################################################################################################
 
    if globalData.finalTherionExe == True :
        FILE = DEST_PATH + '/' +  SurveyTitle + '.thconfig'      
        t = compile_file(FILE, therion_path=globalData.therionPath) 
        threads.append(t)
        
        for thread in threads:  # Attendre que tous les threads se terminent
            thread.join()
            
        logfile = (DEST_PATH + '/therion.log').replace("\\", "/")   
        
        with open(logfile, 'r') as f:
            content = f.read()
            # print(content)
        
        stat = get_stats_from_log(content)
        
        if stat["length"] != 0.0 and stat["depth"] != 0.0 :
            totReadMe += f"\tFinal compilation successful length: {stat["length"]} m, depth: {stat["depth"]} m\n"
            log.info(f"Final compilation successful length: {Colors.ENDC}{stat["length"]}{Colors.INFO} m, depth: {Colors.ENDC}{stat["depth"]}{Colors.INFO} m")
        else :
            totReadMe += f"\tFinal compilation error, check log file\n"
            log.error(f"Final compilation error, check log file")
                    
    config_vars['readMeList'] = totReadMe

    update_template_files(DEST_PATH + '/template-readme.md', config_vars, DEST_PATH +'/' + SurveyTitle + '-readme.md')
    
    stationList["Survey_Name_02"] = SurveyTitle

    totReadMeError += totReadMeErrorDat
    
    return stationList, SurveyTitle, totReadMeError, threads


#################################################################################################
def wait_until_file_is_released(filepath, timeout=30):
    """Wait until a file is released (i.e., not locked by another process).

    Args:
        filepath (str): The path to the file to check.
        timeout (int, optional): The maximum time to wait in seconds. Defaults to 30.

    Returns:
        bool: True if the file is released, False if the timeout is reached.
        
    """
    
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
    _fileTitle = ""
    
    #################################################################################################
    # Parse arguments                                                                               #
    #################################################################################################
    parser = argparse.ArgumentParser(
        description=f"{Colors.BLUE}Create a skeleton folder and th, th2 files with scraps from  *.tro, *.mak, *.dat, *.th Therion files, version: {Colors.ENDC}{globalData.Version}\n",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.print_help = colored_help.__get__(parser)
    parser.add_argument("--file", help="the file (*.th, *.mak, *.dat, *.tro) to perform e.g. './Therion_file.th'", default="")
    parser.add_argument("--proj", choices=['All', 'Plan', 'Extended', 'None'], help="the th2 files scrap projection to produce, default: All", default="All")
    parser.add_argument("--scale", help="scale for the pdf layout exports, default value: 1000 (i.e. xvi files scale is 100)", default="1000")
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
        
    output_log = splitext(abspath(args.file))[0] + ".log"        
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
    config_file = load_config(args)

    #################################################################################################
    # titre                                                                                         #
    #################################################################################################
    titre_largeur = 160
    bordure = "#" * titre_largeur + Colors.ENDC
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')

    def pad_line(texte, center=False):
        # Supprimer les séquences ANSI pour le calcul de longueur visuelle
        visible_len = len(ansi_escape.sub('', texte))
        espace_total = titre_largeur - visible_len - 2  # 2 pour les * à gauche et droite

        if center:
            left = espace_total // 2
            right = espace_total - left
            return f"#{' ' * left}{texte}{' ' * right}{Colors.ENDC}{Colors.INFO}#"
        else:
            return f"# {texte}{' ' * max(0, espace_total - 1)}{Colors.INFO}#"

    _titre = [
        bordure,
        pad_line(f"{Colors.BOLD}{Colors.YELLOW}Conversion Th, Dat, Mak, Tro, files to Therion files and folders", center=True),
        pad_line(f"Script pyCreateTh by : {Colors.BLUE}alexandre.pont@yahoo.fr"),
        pad_line(f"Version :              {Colors.ENDC}{globalData.Version}"),
        pad_line(f"Input file :           {Colors.ENDC}{safe_relpath(args.file)}"),
        pad_line(f"Output folder :        {Colors.ENDC}{safe_relpath(splitext(abspath(args.file))[0])}"),
        pad_line(f"Log file :             {Colors.ENDC}{os.path.basename(output_log)}"),
        pad_line(f"Config file:           {Colors.ENDC}{safe_relpath(config_file)}"),
        pad_line(""),
        bordure
    ]

    for line in _titre:
        log.info(line)

        
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
                                                                CONFIG_PATH = "",
                                                                args_file = args.file,
                                                                proj = args.proj.lower())
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
        
        content, val, enc = load_text_file_utf8(ABS_file, os.path.basename(ABS_file))
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
        
        with alive_bar( QtySections, title=f"{Colors.GREEN}Dat to Th conversion progress: {Colors.BLUE}", length = 20, enrich_print=False,
                stats=True,  # Désactive les stats par défaut pour plus de lisibilité
                elapsed=True,  # Optionnel : masque le temps écoulé
                monitor=True,  # Optionnel : masque les métriques (ex: "eta")
                bar="smooth"  # Style de la barre (autres options: "smooth", "classic", "blocks") 
                ) as bar:
            with redirect_stdout(sys.__stdout__):
                for i in range(1): 
                    if globalData.error_count > 0:
                        bar.text(f"{Colors.INFO}file: {Colors.ENDC}{os.path.basename(ABS_file)[:-4]}{Colors.ERROR}, error: {Colors.ENDC}{globalData.error_count}")
                    else :
                        bar.text(f"{Colors.INFO}file: {Colors.ENDC}{os.path.basename(ABS_file)[:-4]}")
                    stationList, fileTitle, totReadMeError, thread2 = dat_to_th_files (ABS_file , fixPoints = [], crs_wkt = "", CONFIG_PATH = _ConfigPath, totReadMeError = "", bar = bar)
                    threads += thread2
                    bar()
        
    #################################################################################################
    # Fichier TRO                                                                                   #
    #################################################################################################    
    elif args.file[-3:].lower() == "tro" :
        
        SrcFile = abspath(args.file)
        DestFile = SrcFile[:-4] + ".th"
        
        source_content, val, encodage = load_text_file_utf8(SrcFile, os.path.basename(SrcFile))
        
        entrance, fileTitle, coordinates, coordsyst, fle_th_fnme = convert_tro( fle_tro_fnme = SrcFile, fle_tro_encoding= encodage, 
                                    fle_th_fnme = DestFile, cavename = None, icomments = True, icoupe = False, istructure = False, 
                                    thlang = None, Errorfiles = False )
        
        if coordsyst == None :
            log.critical(f"The VisualTopo file {Colors.ENDC}{SrcFile}{Colors.ERROR}{Colors.BOLD}, have no coordinate system define. Correct it and try again")
            exit(0)
        
        content, val, encodage = load_text_file_utf8(fle_th_fnme, os.path.basename(fle_th_fnme))
        
        if globalData.parse_tro_files_by_explo :
            
            _centerlines = parse_therion_centerline(content)
            centerlines = regroupe_date(_centerlines)
            
             
            with alive_bar( len(centerlines) + 1 , title=f"{Colors.GREEN}Tro to Th conversion progress: {Colors.BLUE}", length = 20, enrich_print=False,
                    stats=True,  # Désactive les stats par défaut pour plus de lisibilité
                    elapsed=True,  # Optionnel : masque le temps écoulé
                    monitor=True,  # Optionnel : masque les métriques (ex: "eta")
                    bar="smooth"  # Style de la barre (autres options: "smooth", "classic", "blocks") 
                    ) as bar:
                
                with redirect_stdout(sys.__stdout__):
                    for i in range(1): 
                        if globalData.error_count > 0:
                            bar.text(f"{Colors.INFO}file: {Colors.ENDC}{os.path.basename(SrcFile)}{Colors.ERROR}, error: {Colors.ENDC}{globalData.error_count}")
                        
                        else :
                            bar.text(f"{Colors.INFO}file: {Colors.ENDC}{os.path.basename(SrcFile)}")
                        
                        stationList, fileTitle, totReadMeError, thread2 = tro_to_th_files (ENTRY_FILE = SrcFile , 
                                                                                           centerlines = centerlines,
                                                                                           entrance = entrance, 
                                                                                           fileTitle = fileTitle, 
                                                                                           coordinates = coordinates, 
                                                                                           coordsyst = coordsyst, 
                                                                                           fle_th_fnme = fle_th_fnme, 
                                                                                           CONFIG_PATH = "", 
                                                                                           totReadMeError = "", 
                                                                                           bar = bar)
                        threads += thread2
                        bar()            
                
        else :
            if encodage != "utf-8":
                with open(str(fle_th_fnme), "w+", encoding="utf-8") as f:
                    f.write(content)
            
            with open(fle_th_fnme, 'a', encoding='utf-8') as file:        # Données originales en commentaire dans le fichier th        
                file.write(f"\n\n#############################################################################################")
                file.write(f"\n# Originals data file : {args.file}")
                if globalData.error_count == 0 :   
                    file.write(f"\n# Conversion with pyCreateTh version {globalData.Version}, the {datetime.now().strftime("%Y.%m.%d %H:%M:%S")}, without error")
                else :
                    file.write(f"\n# Conversion with pyCreateTh version {globalData.Version}, the {datetime.now().strftime("%Y.%m.%d %H:%M:%S")}, with {globalData.error_count} error(s)")

                file.write(f"\n#############################################################################################\n\n")
                for line in source_content.splitlines():
                    file.write(f"# {line}\n")        
                    
            flagErrorCompile, stat, totReadMeError, thread2 = create_th_folders( 
                                                                ENTRY_FILE = fle_th_fnme, 
                                                                TARGET = None, 
                                                                PROJECTION= args.proj,
                                                                SCALE = args.scale, 
                                                                UPDATE = args.update, 
                                                                CONFIG_PATH = "",
                                                                args_file = args.file,
                                                                proj = args.proj.lower() )
            
            threads += thread2
            fileTitle = sanitize_filename(os.path.basename(fle_th_fnme)[:-3])
        
        if os.path.isfile(fle_th_fnme):
            os.remove(fle_th_fnme)
             
    #################################################################################################
    # Fichier TROX                                                                                  #
    #################################################################################################    
    elif args.file[-4:].lower() == "trox" :
        SrcFile = abspath(args.file)
        analyse_xml_balises(SrcFile)
        fileTitle = sanitize_filename(os.path.basename(SrcFile)[:-4])
          
    #################################################################################################
    # Autres types                                                                                  #
    #################################################################################################    
    else :
        log.error(f"file {Colors.ENDC}{safe_relpath(args.file)}{Colors.ERROR} not yet supported")
        globalData.error_count += 1
    
    for t in threads:
        t.join()

    destination_path = os.path.dirname(output_log) + "\\" + fileTitle 
    file_name = os.path.basename(output_log)
    destination_file = os.path.join(destination_path, file_name)
    
    wait_until_file_is_released(output_log)
    
    duration = (datetime.now() - start_time).total_seconds()
    
    if globalData.error_count == 0 :    
        log.info(f"All files processed successfully in {Colors.ENDC}{duration:.2f}{Colors.INFO} secondes, without error")
    else :
        log.error(f"There were {Colors.ENDC}{globalData.error_count}{Colors.ERROR} errors during {Colors.ENDC}{duration:.2f}{Colors.ERROR} secondes, check the log file: {Colors.ENDC}{os.path.basename(output_log)}")

    wait_until_file_is_released(output_log)
    
    release_log_file(log)
    
    # Supprimer le fichier cible si il existe déjà
    if os.path.isfile(destination_file):
        os.remove(destination_file)

    if not args.update :
        shutil.move(output_log, destination_path)
        
    if os.path.exists(fileTitle):
        os.remove(fileTitle)

