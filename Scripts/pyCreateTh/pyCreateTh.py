
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
                        Ajout des fonctions pour mettre en log    
                        Création de la fonction mak_to_th_file
                        
                        
A venir :
    - gérer les visées orphelines dans une même survey
    - gérer les updates (th, dat, mak)
    - créer fonction pour faire habillage des th2 files, les jointures...
    - reprendre l'option shot lines dans les th2 files pour supprimer les splays.
    - reprendre les options en ligne de commande, tester
    - ajouter les commentaires et les déclinaisons dans les th files
    - ajouter message pour les corrections non implantés
    - trouver une solution pour les teams et les clubs manquants
    - gérer le cas ou il y a 2 SurveyTitle identiques
    - alléger les equates --> 1 fois dans le projet


"""

Version ="2025.06.18"  

#################################################################################################
#################################################################################################
import os, re, unicodedata, argparse, shutil, sys, time
from os.path import isfile, join, abspath, splitext
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

log = setup_logger(logfile="app.log", debug_log=True)

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
                stations[f"{x}.{y}"] = [x, y, station]

        # Calcul des bornes x et y
        x_values = [float(value[0]) for value in stations.values()]
        y_values = [float(value[1]) for value in stations.values()]
        x_min, x_max = min(x_values), max(x_values)
        y_min, y_max = min(y_values), max(y_values)
        x_ecart = x_max - x_min
        y_ecart = y_max - y_min

        # Extraction des lignes
        for line in xvi_shots.split("\n"):
            match = re.search(r"^\s*{\s*(-?\d+\.\d+)\s*(-?\d+\.\d+)\s*(-?\d+\.\d+)\s*(-?\d+\.\d+)\s*.*}", line)
            if match:
                x1, y1, x2, y2 = match.groups()
                key1 = f"{x1}.{y1}"
                key2 = f"{x2}.{y2}"
                station1 = stations[key1][2] if key1 in stations else None
                station2 = stations[key2][2] if key2 in stations else None
                lines.append([x1, y1, x2, y2, station1, station2])

    return stations, lines, x_min, x_max, y_min, y_max, x_ecart, y_ecart

################################################################################################# 
# Création des dossiers à partir d'un th file                                                   #
#################################################################################################   
def create_th_folders(ENTRY_FILE, 
                    PROJECTION = "All", 
                    TARGET = "None", 
                    FORMAT = "th2", 
                    SCALE = "500", 
                    UPDATE = "", 
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
        UPDATE (str): Le mode de mise à jour.
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
          
    if PROJECTION.lower() != "plan" and PROJECTION.lower() != "extended" and PROJECTION.lower() != "all":
        log.critical(f"Sorry, projection '{Colors.ENDC}{PROJECTION}{Colors.ERROR}' not yet implemented{Colors.ENDC}")
        exit(1)
    
    if not os.path.isfile(ENTRY_FILE):
        log.critical(f"The Therion file didn't exist: {Colors.ENDC}{shortCurentFile}")
        exit(1)

    if FORMAT not in ["th2", "plt"]:
        log.critical(f"Please choose a supported format: th2, plt{Colors.ENDC}")
        exit(1)

    # Normalise name, namespace, key, file path
    log.info(f"Parsing survey entry file: {Colors.ENDC}{shortCurentFile}")

    survey_list = parse_therion_surveys(ENTRY_FILE)
    # print(survey_list)
    
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
    
   
    if UPDATE == "th2": 
        log.info(f" Update th2 files {Colors.ENDC}")
        log.info(f"\t{Colors.BLUE}survey_file :  {Colors.ENDC} {args.survey_file}")
        log.info(f"\t{Colors.BLUE}ENTRY_FILE:    {Colors.ENDC} {ENTRY_FILE}") 
        log.info(f"\t{Colors.BLUE}PROJECTION:    {Colors.ENDC} {PROJECTION}") 
        log.info(f"\t{Colors.BLUE}TARGET:        {Colors.ENDC} {TARGET}") 
        # log.info(f"\t{Colors.BLUE}OUTPUT:        {Colors.ENDC} {OUTPUT}") 
        log.info(f"\t{Colors.BLUE}FORMAT:        {Colors.ENDC} {FORMAT}")     
        log.info(f"\t{Colors.BLUE}SCALE:         {Colors.ENDC} {SCALE}")
        log.info(f"\t{Colors.BLUE}TH_NAME:       {Colors.ENDC} {TH_NAME}")
        DEST_PATH = os.path.dirname(args.survey_file)
        log.info(f"\t{Colors.BLUE}DEST_PATH:     {Colors.ENDC} {DEST_PATH}")
        log.info(f"\t{Colors.BLUE}ABS_PATH:      {Colors.ENDC} {ABS_PATH}")
    
    
    #################################################################################################    
    # Copy template folders                                                                         #
    #################################################################################################
    if UPDATE == "": 
        log.debug(f"Copy template folder and adapte it")
        copy_template_if_not_exists(globalData.templatePath, DEST_PATH)
        copy_file_with_copyright(ENTRY_FILE, DEST_PATH + "/Data", globalData.Copyright)
    
        
    #################################################################################################                   
    # Produce the parsable XVI file                                                                 #
    #################################################################################################      
    log.info(f"Compiling 2D XVI file: {Colors.ENDC}{TH_NAME}")
    
    if UPDATE == "th2": 
        template_args = {
            "th_file": DEST_PATH + "/" + TH_NAME + ".th",  
            "selector": survey.therion_id,
            "th_name": DEST_PATH + "/" + TH_NAME, 
            "scale": SCALE,
        }

    else :
        template_args = {
            "th_file": DEST_PATH + "/Data/" + TH_NAME + ".th",  
            "selector": survey.therion_id,
            "th_name": DEST_PATH + "/Data/" + TH_NAME, 
            "scale": SCALE,
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
    if UPDATE == "": 
        
        ERR = "# " if flagErrorCompile else ""
        
        totdata = f"""\tinput Data/{TH_NAME}.th
            
\t## Pour le plan
\t{ERR}input Data/{TH_NAME}-Plan.th2
            
\t## Pour la coupe développée
\t{ERR}input Data/{TH_NAME}-Extended.th2
            
\t## Appel des maps
\t{ERR}input {TH_NAME}-maps.th
"""
        
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
            'other_scraps_plan' : "",
            'file_info' : f'# File generated by pyCreateTh.py (version {Version}) date: {datetime.now().strftime("%Y.%m.%d %H:%M:%S")}',
        }
        
        update_template_files(DEST_PATH + '/template.thconfig', config_vars, DEST_PATH + '/' +  TH_NAME + '.thconfig')
        update_template_files(DEST_PATH + '/template-tot.th', config_vars, DEST_PATH + '/' +  TH_NAME + '-tot.th')
        update_template_files(DEST_PATH + '/template-readme.md', config_vars, DEST_PATH + '/' +  TH_NAME + '-readme.md')   
   
    #################################################################################################    
    # Parse the Plan XVI file                                                                       #
    #################################################################################################
    other_scraps_plan = ""
    if PROJECTION.lower() == "plan" or PROJECTION.lower() == "all" and not flagErrorCompile :
        if UPDATE == "th2": 
            th_name_xvi =  DEST_PATH + "/" + TH_NAME + "-Plan.xvi" 
        else :     
            th_name_xvi =  DEST_PATH + "/Data/" + TH_NAME + "-Plan.xvi" 

        log.info(f"Parsing Plan XVI file: {Colors.ENDC}{safe_relpath(th_name_xvi)}")

        stations = {}
        lines = []
        
        stations, lines, x_min, x_max, y_min, y_max, x_ecart, y_ecart = parse_xvi_file(th_name_xvi)
        
        if UPDATE == "th2": 
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
                log.warning(f"{Colors.ENDC}{os.path.basename(output_path)}{Colors.WARNING} file already exists - nothing done")

            else :
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
        if UPDATE == "th2": 
            th_name_xvi =  DEST_PATH + "/" + TH_NAME + "-Extended.xvi" 
        else :
            th_name_xvi =  DEST_PATH + "/Data/" + TH_NAME + "-Extended.xvi" 

        log.info(f"Parsing extended XVI file:\t{Colors.ENDC}{safe_relpath(th_name_xvi)}")

        # Parse the Extended XVI file
        stations = {}
        lines = []
        
        stations, lines, x_min, x_max, y_min, y_max, x_ecart, y_ecart = parse_xvi_file(th_name_xvi)
        

        if UPDATE == "th2":
            th2_name = DEST_PATH + "/" + TH_NAME
        else :
            th2_name = DEST_PATH + "/Data/" + TH_NAME
        output_path = f'{th2_name}-Extended.{FORMAT}'

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
                log.warning(f"{Colors.ENDC}{os.path.basename(output_path)}{Colors.WARNING} file already exists - nothing done{Colors.ENDC}")
            else :
                log.debug(f"Therion output path :\t{Colors.ENDC}{output_path}")
                    
                with open(str(output_path), "w+") as f:
                    f.write(globalData.th2FileHeader)
                    f.write(globalData.th2File.format(
                            name = TARGET,
                            Copyright = globalData.Copyright,
                            Copyright_Short = globalData.CopyrightShort,
                            points="\n".join(th2_points),
                            lines="\n".join(th2_lines) if globalData.linesInTh2 else "",
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
    if UPDATE == "":                      
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
                        'configPath' : CONFIG_PATH,
                        'other_scraps_plan' : other_scraps_plan,
                        'other_scraps_extended' : other_scraps_extended,
                        'file_info' : f"# File generated by pyCreateTh.py version {Version} date: {datetime.now().strftime("%Y.%m.%d-%H:%M:%S")}",
                }
                

        update_template_files(DEST_PATH + '/template-maps.th', config_vars, DEST_PATH + '/' +  TH_NAME + '-maps.th')
    
        
    #################################################################################################     
    # Final therion compilation                                                                     #
    #################################################################################################
    if UPDATE == "":   
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
        ABS_file = os.path.dirname(abspath(args.survey_file)) + "\\"+ file
        content, val = load_text_file_utf8(ABS_file, os.path.basename(ABS_file))
        section = content.split('\x0c')
        QtySections += len(section)

      
    SurveyTitleMak =  sanitize_filename(os.path.basename(abspath(args.survey_file))[:-4])
        
    folderDest = os.path.dirname(abspath(args.survey_file)) + "/" + SurveyTitleMak
        
    copy_template_if_not_exists(globalData.templatePath,folderDest)
    
    
    ##############################################################################################     
    # Boucle pour lire les dat                                                                   #
    ##############################################################################################
    
    
    stationList = pd.DataFrame(columns=['StationName', 'Survey_Name_01', 'Survey_Name_02'])
    totdata = f"\t## Liste inputs\n"
    totMapsPlan = ""
    totMapsExtended = ""
    
    
    with alive_bar(QtySections, title=f"{Colors.GREEN}Surveys progress: {Colors.BLUE}",  length = 20, enrich_print=False) as bar:
        
        with redirect_stdout(sys.__stdout__):
            for file in datFiles:
                
                bar.text(f"{Colors.INFO}file: {Colors.ENDC}{file}")
                
                _file = os.path.dirname(abspath(args.survey_file)) + "\\" + file
                shutil.copy(_file, folderDest + "\\Data\\")
                ABS_file = folderDest + "\\Data\\" + file

                totReadMeError += f"* file: {file}\n"
                totReadMeList += f"file: {file}\n"

                Station, SurveyTitle, totReadMeError, thread2 = dat_to_th_files(ABS_file, fixPoints, crs_wkt, _ConfigPath, totReadMeError, bar)
                
                threads += thread2

                totdata += f"\tinput Data/{SurveyTitle}/{SurveyTitle}-tot.th\n"
                totMapsPlan += f"\tMP-{SurveyTitle}-Plan-tot@{SurveyTitle}\n\tbreak\n"
                totMapsExtended += f"\tMC-{SurveyTitle}-Extended-tot@{SurveyTitle}\n\tbreak\n"

                if not Station.empty:
                    stationList = pd.concat([stationList, Station], ignore_index=True)
                    stationList.sort_values(by='Survey_Name_02', inplace=True, ignore_index=True)

                destination = os.path.join(folderDest, "Sources", os.path.basename(ABS_file))
                if os.path.exists(destination):
                    os.remove(destination)

                shutil.move(ABS_file, destination)

                bar() 
    
    
    ################################################################################################# 
    # Gestion des equats 
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
    
    # print(f"tableau_pivot : {Colors.ENDC}{tableau_pivot}{Colors.INFO} in {Colors.ENDC}{args.survey_file}")
    
    totdata +=f"\n\t## Liste equates\n"
    
    if 'Survey_Name_2' in tableau_pivot.columns:
        # On réinitialise l'index pour avoir StationName comme colonne normale
        tableau_pivot = tableau_pivot.reset_index()
        tableau_equate = tableau_pivot[tableau_pivot['Survey_Name_2'].notna()]


        log.info(f"Total des 'equats' : {Colors.ENDC}{len(tableau_equate)}{Colors.INFO} in {Colors.ENDC}{safe_relpath(args.survey_file)}")
        # print(tableau_equate)
        # print(f"fixePoints : {Colors.ENDC}{fixed_names}{Colors.INFO} in {Colors.ENDC}{args.survey_file}")
        
        # Pour chaque ligne du tableau
        for _, row in tableau_equate.iterrows():
            station = row['StationName']
            
            # On récupère tous les Survey_Name non vides (NaN exclus)
            surveys = [row[col] for col in tableau_equate.columns if col.startswith('Survey_Name') and pd.notna(row[col])]
            
            # Pour chaque paire unique (i < j), on écrit la ligne 'equate'
            for i in range(len(surveys)):
                for j in range(i + 1, len(surveys)):
                    totdata +=f"\tequate {station}@{surveys[i]} {station}@{surveys[j]}\n"
                    # print(f"\tequate {station}@{surveys[i]} {station}@{surveys[j]}")
    else:
        log.info(f"No 'equats' found in {Colors.ENDC}{args.survey_file}")
            
    totdata +=f"\n\t## Appel des maps\n\tinput {SurveyTitleMak}-maps.th\n"
        
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
                    'other_scraps_plan' : totMapsPlan,
                    'other_scraps_extended' : totMapsExtended,
                    'readMeList' : totReadMeList,
                    'errorList' : totReadMeError,
                    'fixPointList' : totReadMeFixPoint,
                    'file_info' : f"# File generated by pyCreateTh.py version {Version} date: {datetime.now().strftime("%Y.%m.%d-%H:%M:%S")}",
            }

    DEST_PATH = os.path.dirname(args.survey_file) + '/' +  SurveyTitleMak

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
def station_list(data, list, fixPoints) :  
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
        'Survey_Name_01': data['SURVEY_NAME']
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

    # Étape 2 : chercher les entrées ayant des stations communes
    for key, entries in grouped.items():
        if len(entries) < 2:
            continue

        visited_pairs = set()

        for i in range(len(entries)):
            id_i = entries[i]['ID']
            stations_i = set(entries[i]['STATION'].iloc[:, 0])

            ids_group = [id_i]
            common_stations = set()

            for j in range(i+1, len(entries)):
                pair = tuple(sorted((id_i, entries[j]['ID'])))
                if pair in visited_pairs:
                    continue

                visited_pairs.add(pair)
                stations_j = set(entries[j]['STATION'].iloc[:, 0])
                intersection = stations_i & stations_j

                if intersection:
                    ids_group.append(entries[j]['ID'])
                    common_stations.update(intersection)

            if len(ids_group) > 1:
                ids_group = sorted(set(ids_group))
                common_stations = sorted(common_stations)
                already_recorded = False

                for d in duplicates:
                    if set(d['IDS']) == set(ids_group):
                        already_recorded = True
                        break

                if not already_recorded:
                    duplicates.append({
                        'SURVEY_DATE': key[0],
                        'SURVEY_TEAM': key[1],
                        'IDS': ids_group,
                        'COMMON_STATIONS': common_stations
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
        
#################################################################################################     
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
    totdata = f"\t## Liste inputs\n"
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
            'DATA' : [],  
            'STATION': [],
            'SOURCE' : []
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
                jour, mois, annee = date.split()
                date_convertie = f"{annee} {mois} {jour}"
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
                # current_field = 'DECLINATION'
                # Découper la ligne en trois parties
                declination_part = line.split(':', 1)[1].strip()
                jumpLine = True # Sauter une ligne après la ligne DECLINATION
                # Extraire DECLINATION (premier nombre)
                declination_val = declination_part.split()[0]
                section_data['DECLINATION'] = declination_val
                # Trouver FORMAT et CORRECTIONS
                if 'FORMAT:' in declination_part:
                    format_part = declination_part.split('FORMAT:', 1)[1]
                    format_val = format_part.split('CORRECTIONS:', 1)[0].strip()
                    section_data['FORMAT'] = format_val
                    
                    if 'CORRECTIONS:' in format_part:
                        corrections_val = format_part.split('CORRECTIONS:', 1)[1].strip()
                        section_data['CORRECTIONS'] = corrections_val
                        
            else :
                if line.strip() != '' :       
                    section_data['DATA'].append(line.strip())
                else :
                    line.strip()
        
        # Ajouter les données de la section à la liste
        if len(section_data['DATA']) > 0 :
            listStationSection, dfDATA = station_list(section_data, listStationSection, fixPoints)
            section_data['STATION'] = listStationSection
            data.append(section_data)    
            unique_id += 1 
            

            #################################################################################################     
            # Détecter les surveys avec plusieurs points de départ                                          #
            #################################################################################################    
  
            points = points_uniques(section_data, crs_wkt)

            if len(points) > 1 :
                log.warning(f"Points {Colors.ENDC}{points}{Colors.WARNING} uniques dans la section {Colors.ENDC}{section_data['SURVEY_NAME']}")
                # globalData.error_count += 1
                
            else :
                log.debug(f"Points {Colors.ENDC}{points}{Colors.DEBUG} uniques dans la section {section_data['SURVEY_NAME']}")
                

    #################################################################################################
    # Grouper les sections ayant même date team et un point commun                                  #
    #################################################################################################
    val1 = len(data)
    
    duplicates = find_duplicates_by_date_and_team(data)     

    data = merge_duplicate_surveys(data, duplicates)
    
    val2 = val1 - len(data)
    
    bar(val2)
    
    log.info(f"Read dat file: {Colors.ENDC}{shortCurentFile}{Colors.GREEN} with {Colors.ENDC}{len(data)}/{len(data)}{Colors.GREEN} survey")
    

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
    
    if  args.survey_file[-3:].lower() != "dat" :
        _destination =  folderDest + "\\config.thc"
        # print(f"destination_path : {_destination}")
        os.remove(_destination)
    
    # Trie des données par date        
    data = sorted(data, key=lambda x: x['SURVEY_DATE'] or "")
    
    #################################################################################################     
    # 3 : Boucle pour créer les surveys au format th                                                #
    #################################################################################################

    surveyCount = 1
    SurveyListEqui = [] 
    
    # totReadMe += f"* Source file: {os.path.basename(ENTRY_FILE)}\n"
    
    for _line in data :    
        
        # currentSurveyName = f"{globalData.typeSurveyName}{surveyCount:02d}"
        # currentSurveyName = f"{globalData.typeSurveyName}{surveyCount:02d}_{sanitize_filename(_line['SURVEY_NAME'])}"
        currentSurveyName = f"{globalData.SurveyPrefixName}{surveyCount:02d}_{sanitize_filename(_line['SURVEY_DATE'])}"
   
        output_file = f"{folderDest}\\Data\\{currentSurveyName}.th"
        
        SurveyNameCount = {
            'surveyCount' :f"{currentSurveyName}", 
            'SURVEY_NAME': _line['SURVEY_NAME']
        }

        SurveyListEqui.append(SurveyNameCount)

        #################################################################################################     
        # gestion des déclinaisons                                                                      #
        #################################################################################################
        
    
        #################################################################################################     
        # gestion des DATA                                                                              #
        #################################################################################################
    
        stationList, dfDATA = station_list(_line, stationList, fixPoints)

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
        
        with open(str(output_file), "w+", encoding="utf-8") as f:
            f.write(globalData.thFileDat.format(
                    VERSION = Version,
                    DATE=datetime.now().strftime("%Y.%m.%d-%H:%M:%S"),
                    # SURVEY_NAME = sanitize_filename(_line['SURVEY_NAME']),  
                    SURVEY_NAME = f"{currentSurveyName}", 
                    SURVEY_DATE = _line['SURVEY_DATE'], 
                    SURVEY_TEAM = _line['SURVEY_TEAM'], 
                    FORMAT = _line['FORMAT'], 
                    COMPASS = compass,
                    LENGTH = length, 
                    CLINO = clino,    
                    DATA_FORMAT = dataFormat,
                    CORRECTIONS = _line['CORRECTIONS'], 
                    DATA = formated_station_list(dfDATA, dataFormat, length, shortCurentFile),
                    COMMENT = sanitize_filename(_line['SURVEY_NAME'] + " " + _line['COMMENT']).replace('"', "'").replace('_', " "),
                    FIX_POINTS = fixPoint,
                    EXPLO_DATE = "????",
                    EXPLO_TEAM = "????",
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
            SCALE = args.scale, 
            UPDATE = args.update, 
            CONFIG_PATH = _Config_PATH, 
            totReadMeError = totReadMeErrorDat)
        threads += thread2 
     
        log.info(f"File: {Colors.ENDC}{os.path.basename(ENTRY_FILE)}.dat{Colors.INFO} compilation successful, length: {Colors.ENDC}{stat["length"]}m{Colors.INFO}, depth: {Colors.ENDC}{stat["depth"]}m")   
        totReadMe += f"\t{currentSurveyName} compilation successful length: {stat["length"]} m, depth: {stat["depth"]} m\n"
         
        _destination = output_file[:-3] + "\\Sources"
        destination_path = os.path.join(_destination, os.path.basename(output_file))
        shutil.move(output_file, destination_path)      
        
        if args.survey_file[-3:].lower() != "dat" :
            _destination =  output_file[:-3] + "\\config.thc"
            destination_path = os.path.join(_destination, os.path.basename(output_file))
            # print(f"destination_path : {_destination}")
            os.remove(_destination)
        
        if not StatCreateFolder :
            totMapsPlan += f"\tMP-{currentSurveyName}-Plan-tot@{currentSurveyName}\n\tbreak\n"
            totMapsExtended += f"\tMC-{currentSurveyName}-Extended-tot@{currentSurveyName}\n\tbreak\n"
        surveyCount += 1
        
        bar()

#################################################################################################     
# 4 : Finalisation (remplissage des -tot.th et maps.th                                          #
#################################################################################################

    ################################################################################################# 
    # Gestion des equats 
    #################################################################################################
        
    totdata +=f"\n" 
    
    dfEqui = pd.DataFrame(SurveyListEqui)
    stationList = stationList.merge(dfEqui, how='left', left_on='Survey_Name_01', right_on='SURVEY_NAME')
    stationList['Survey_Name_01'] = stationList['surveyCount']
    stationList.drop(columns=['SURVEY_NAME', 'surveyCount'], inplace=True)
    
    _stationList = stationList.copy()
    
    # On numérote les doublons de Survey_Name pour chaque StationName
    _stationList['Survey_Number'] = _stationList.groupby('StationName').cumcount() + 1
    
    # On pivote le tableau pour que chaque Survey_Name devienne une colonne
    tableau_pivot = _stationList.pivot(index='StationName', columns='Survey_Number', values='Survey_Name_01')
    
    tableau_pivot.columns = [f'Survey_Name_{i}' for i in tableau_pivot.columns]
    
    # print(f"tableau_pivot : {Colors.ENDC}{tableau_pivot}{Colors.INFO} in {Colors.ENDC}{ENTRY_FILE}")
    
    totdata +=f"\n\t## Liste equates\n"
    
    if 'Survey_Name_2' in tableau_pivot.columns:
        # On réinitialise l'index pour avoir StationName comme colonne normale
        tableau_pivot = tableau_pivot.reset_index()
        tableau_equate = tableau_pivot[tableau_pivot['Survey_Name_2'].notna()]


        log.info(f"Total 'equats' : {Colors.ENDC}{len(tableau_equate)}{Colors.INFO} in {Colors.ENDC}{shortCurentFile}")
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
        log.info(f"No 'equats' found in {Colors.ENDC}{ENTRY_FILE}")
             
    totdata +=f"\n\t## Appel des maps\n\tinput {SurveyTitle}-maps.th\n"
    
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
                    'cs' : crs_wkt,
                    'totData' : totdata,
                    'configPath' : CONFIG_PATH,
                    'other_scraps_plan' : totMapsPlan,
                    'readMeList' : totReadMe,
                    'errorList' : totReadMeErrorDat,
                    'fixPointList' : totReadMeFixPoint,
                    'other_scraps_extended' : totMapsExtended,
                    'file_info' : f"# File generated by pyCreateTh.py version {Version} date: {datetime.now().strftime("%Y.%m.%d-%H:%M:%S")}",
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
                raise TimeoutError(f"Timeout: le fichier est toujours verrouillé après {timeout} secondes : {filepath}")
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
        description=f"{Colors.HEADER}Create a skeleton folder and th, th2 files with scraps from *.mak, *.dat, *.th Therion files, version: {Colors.ENDC}{Version}\n",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.print_help = colored_help.__get__(parser)
    parser.add_argument("--survey_file", help="The survey file (*.th, *.mak, *.dat,) to perform e.g. './Therion_file.th'", default="")
    parser.add_argument("--survey_name", help="Scrap name (if different from 'survey_file' name)", default="None")
    parser.add_argument("--proj", choices=['All', 'Plan', 'Extended', 'None'], help="The scrap projection to produce", default="All")
    #parser.add_argument("--format", choices=['th2', 'plt'], help="Output format. Either th2 for producing skeleton for drawing or plt for visualizing in aven/loch", default="th2")
    parser.add_argument("--output", default="./", help="Output folder path")
    # parser.add_argument("--therion-path", help="Path to therion binary", default="therion")
    parser.add_argument("--scale", help="Scale for the exports", default="1000")
    parser.add_argument("--lines", type=str_to_bool, help="Shot lines in th2 files", default=-1)
    parser.add_argument("--names", type=str_to_bool, help="Stations names in th2 files", default=-1)
    parser.add_argument("--update", help="Mode update, option th2", default="")
                        
    parser.epilog = (
        f"{Colors.GREEN}Please, complete {Colors.BLUE}config.ini{Colors.GREEN} file for personal configuration{Colors.ENDC}\n"
        f"{Colors.GREEN}If no argument :{Colors.BLUE} files selection windows\n{Colors.ENDC}\n"
        f"{Colors.BLUE}Examples:{Colors.ENDC}\n"
        f"\t> python pyCreateTh.py ./Tests/Entree.th --survey_name Geophysicaya_01_entree --output ./test/  --scale 1000\n"
        f"\t> python pyCreateTh.py Entree.th\n"
        f"\t> python pyCreateTh.py\n\n")
    args = parser.parse_args()
    
    if args.survey_file == "":
        args.survey_file = select_file_tk_window()
        # print(f"Selected file : {args.survey_file}")    
        
    output_log = splitext(abspath(args.survey_file))[0]+".log"    
    log = setup_logger(output_log, debug_log)
    
    # log.debug("Ceci est un message de debug")
    # log.info("Tout va bien")
    # log.warning("Attention, possible souci")
    # log.error("Une erreur est survenue")
    # log.critical("Erreur critique !")
         
    if os.name == 'posix':  os.system('clear') # Linux, MacOS
    elif os.name == 'nt':  os.system('cls')# Windows
    else: print("\n" * 100)
    
    
    _titre =[f'********************************************************************************************************************************************\033[0m', 
            f'* Conversion Th, Dat, Mak files to Therion files and folders',
            f'*       Script pyCreateTh by : {Colors.ENDC}alexandre.pont@yahoo.fr',
            f'*       Version : {Colors.ENDC}{Version}',
            f'*       Input file : {Colors.ENDC}{safe_relpath(args.survey_file)}',           
            f'*       Output file : {Colors.ENDC}{safe_relpath(splitext(abspath(args.survey_file))[0])}',
            f'*       Log file : {Colors.ENDC}{safe_relpath(output_log)}',
            f'*       ',
            f'*       ',
            f'*       ',
            f'********************************************************************************************************************************************\033[0m']     

    for i in range(11): log.info(_titre[i])     


    #################################################################################################
    # Reading config.ini                                                                            #
    #################################################################################################
    try:
        read_config(configIni) 
        
    except ValueError as e:
        log.critical(f"Reading config.ini file error: {Colors.ENDC}{e}")
        exit(0)
    
    if args.survey_file[-2:].lower() == "th" :
        flagErrorCompile, stat, totReadMeError, thread2 = create_th_folders(
                                                                ENTRY_FILE = abspath(args.survey_file), 
                                                                TARGET = args.survey_name, 
                                                                PROJECTION= args.proj,
                                                                SCALE = args.scale, 
                                                                UPDATE = args.update,
                                                                CONFIG_PATH = "")
        threads += thread2
        fileTitle = sanitize_filename(os.path.basename(args.survey_file))[:-3]
        
    elif args.survey_file[-3:].lower() == "mak" :
        fileTitle, thread2 = mak_to_th_file(abspath(args.survey_file))    
        threads += thread2
        
    elif args.survey_file[-3:].lower() == "dat" :
        _ConfigPath = "./"
        
        QtySections = 0
         
        ABS_file = abspath(args.survey_file)
        
        content, val = load_text_file_utf8(ABS_file, os.path.basename(ABS_file))
        section = content.split('\x0c')
        QtySections += len(section)

        
        
        with alive_bar(QtySections, title=f"{Colors.GREEN}Surveys progress: {Colors.BLUE}",  length = 20, enrich_print=False) as bar:
            with redirect_stdout(sys.__stdout__):
                for i in range(1): 
                    bar.text(f"{Colors.INFO}file: {Colors.ENDC}{os.path.basename(ABS_file)}")
                    stationList, fileTitle, totReadMeError, thread2 = dat_to_th_files (ABS_file , fixPoints = [], crs_wkt = "", CONFIG_PATH = _ConfigPath, totReadMeError = "", bar = bar)
                    threads += thread2
                    bar()
        
    else :
        log.error(f"file {Colors.ENDC}{safe_relpath(args.survey_file)}{Colors.ERROR} not yet supported")
        globalData.error_count += 1

    duration = (datetime.now() - start_time).total_seconds()
    
    for t in threads:
        t.join()

    destination_path = os.path.dirname(output_log) + "\\" + fileTitle 
    wait_until_file_is_released(output_log)
    
    if globalData.error_count == 0 :    
        log.info(f"All files processed successfully in {Colors.ENDC}{duration:.2f}{Colors.INFO} secondes, without errors")
    else :
        log.error(f"There were {Colors.ENDC}{globalData.error_count}{Colors.ERROR} errors during {Colors.ENDC}{duration:.2f}{Colors.ERROR} secondes, check the log file: {Colors.ENDC}{os.path.basename(output_log)}")

    wait_until_file_is_released(output_log)
    release_log_file(log)
    shutil.move(output_log, destination_path)
    
        
    