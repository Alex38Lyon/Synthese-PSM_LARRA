
"""
#############################################################################################
#                                                                                       	#  
#  Script pour convertir des données topographiques au format .th .mak ou .dat de compass   #
#                           au format th et th2 de Therion                              	#
#                     By Alexandre PONT (alexandre_pont@yahoo.fr)                         	#
#                                                                                          	#
# Définir les différentes variables dans fichier config.ini                                 #
#                                                                                           #
# Usage : python pyCreateTh.py                                                              #
#         Commandes : pyCreateTh.py --help                                                  #
#                                                                                       	#  
#############################################################################################

Création Alex le 2025 06 09 :
    
Version 2025 06 16 :    Création fonction createThFolders 
                        Ajout des fonctions pour mettre en log    
                        Création de la fonction readMakFile
                        
                        
A venir :
    - gérer les visées orphelines dans une même survey
    - gérer les updates des th2 files (th, dat, mak)
    - raccourcir nom des surveys compilés (ajouter total en commentaire)
    - habillage des th2 files
    - tester les différentes options args.
    - reprendre les options de la ligne de commande
    - mettre au format les minutes en feet
    - ajouter les commentaires et les déclinaisons dans les th files
    - organiser la fonction datToTh
    - organiser la fonction readMakAtToTh
    - organiser la fonction main    
    - mettre en place barres de progression
    - completer readme avec détail pour retrouver les fichiers
        - liste et chemin des points fixes
        - instructions d'utilisation
    - trouver une solution pour les team et les clubs manquants
    - mettre en template les fichier th et th2
    



"""

Version ="2025.06.17"  

#################################################################################################
#################################################################################################
import os
from os.path import isfile, join, abspath, splitext
import sys
import re
import pandas as pd
pd.set_option('future.no_silent_downcasting', True)
import unicodedata
import argparse
import shutil
from datetime import datetime
import configparser
import tkinter as tk
from tkinter import filedialog
from collections import defaultdict
from charset_normalizer import from_path
from copy import deepcopy

from Lib.survey import SurveyLoader, NoSurveysFoundException
from Lib.therion import compile_template, Colors, compile_file, safe_relpath
from Lib.logger_config import setup_logger
import Lib.global_data as global_data

#################################################################################################

## [Survey_Data]  default values
Author = "Created by pyCreateTh.py"
Copyright = "# Copyright (C) pyCreateTh.py"
Copyright_Short = "Licence (C) pyCreateTh.py"
map_comment = "Created by pyCreateTh.py"
cs = "UTM30"
club = "Therion"
thanksto = "Therion"
datat = "https://therion.speleo.sk/"
wpage = "https://therion.speleo.sk/"

## [Application_data] default values
template_path = "./Template"
station_by_scrap = 20
final_therion_exe = True
therion_path = "C:/Therion/therion.exe"
LINES = -1
NAMES = -1

configIni = "config.ini"       # Default config file name
debug_log = False              # Mode debug des messages
# global_data.error_count = 0                # Compteur d'erreurs


#################################################################################################
@pd.api.extensions.register_series_accessor("stationName")
class StationNameAccessor:
    def __init__(self, pandas_obj):
        self._obj = pandas_obj

    def __call__(self):
        return (
            self._obj
            .str.replace('[', '___', regex=False)
            .str.replace(']', '_%_', regex=False)
            .str.replace('@', '_._', regex=False)
        )

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
    th_name = th_name.lower().capitalize()

    # Avoid empty result
    return th_name or "default_filename"



#################################################################################################
def colored_help(parser):
    # Captures the help output
    help_text = parser.format_help()
    
    # Coloration des différentes parties
    colored_help_text = help_text.replace(
        'usage:', f'{Colors.ERROR}usage:{Colors.ENDC}'
    ).replace(
        'options:', f'{Colors.GREEN}options:{Colors.ENDC}'
    ).replace('positional arguments:', f'{Colors.BLUE}positional arguments:{Colors.ENDC}'
    ).replace(', --help', f'{Colors.BLUE}, --help:{Colors.ENDC}'
    ).replace('elp:', f'{Colors.BLUE}elp{Colors.ENDC}')

    # Surligner les arguments
    for action in parser._actions:
        if action.option_strings:
            # Colorer les options (--xyz)
            for opt in action.option_strings:
                colored_help_text = colored_help_text.replace(opt, f'{Colors.BLUE}{opt}{Colors.ENDC}').replace('--help', f'{Colors.BLUE}--help:{Colors.ENDC}')
    
    # Imprimer le texte coloré
    print(colored_help_text)
    sys.exit(1)


#################################################################################################
def read_config(config_file):
    global Author
    global Copyright
    global Copyright_Short
    global map_comment
    global club
    global thanksto
    global datat
    global wpage
    global cs
    global template_path
    global station_by_scrap
    global final_therion_exe
    global therion_path
    global LINES
    global NAMES
    

    # Initialize the configparser to read .ini files
    config = configparser.ConfigParser()
    config.read(config_file, encoding="utf-8")

    if 'Survey_Data' in config and 'Author' in config['Survey_Data']:
        Author = config['Survey_Data']['Author']
    
    if 'Survey_Data' in config and 'Copyright1' in config['Survey_Data']:
        Copyright = config['Survey_Data']['Copyright1'] + "\n" + config['Survey_Data']['Copyright2'] + "\n" + config['Survey_Data']['Copyright3'] + "\n"
           
    if 'Survey_Data' in config and 'Copyright_Short' in config['Survey_Data']:
        Copyright_Short = config['Survey_Data']['Copyright_Short']        
        
    if 'Survey_Data' in config and 'map_comment' in config['Survey_Data']:
        map_comment = config['Survey_Data']['map_comment']
    
    if 'Survey_Data' in config and 'club' in config['Survey_Data']:
        club = config['Survey_Data']['club']
    
    if 'Survey_Data' in config and 'thanksto' in config['Survey_Data']:
        thanksto = config['Survey_Data']['thanksto']
    
    if 'Survey_Data' in config and 'datat' in config['Survey_Data']:
        datat = config['Survey_Data']['datat']
        
    if 'Survey_Data' in config and 'wpage' in config['Survey_Data']:
        wpage = config['Survey_Data']['wpage']
        
    if 'Survey_Data' in config and 'cs' in config['Survey_Data']:
        cs = config['Survey_Data']['cs']
        
    if 'Application_Data' in config and 'template_path' in config['Application_Data']:
        template_path = config['Application_Data']['template_path']    
        
    if 'Application_Data' in config and 'station_by_scrap' in config['Application_Data']:
        station_by_scrap = int(config['Application_Data']['station_by_scrap'])
    
    if 'Application_Data' in config and 'final_therion_exe' in config['Application_Data']:
        final_therion_exe = bool(config['Application_Data']['final_therion_exe'])
        
    if 'Application_Data' in config and 'therion_path' in config['Application_Data']:
        therion_path = config['Application_Data']['therion_path']
    
    if LINES == -1 :    
        if 'Application_Data' in config and 'shot_lines_in_th2_files' in config['Application_Data']:
            LINES = 0 if config['Application_Data']['shot_lines_in_th2_files'] == "False" else 1
    
    if NAMES == -1 :    
        if 'Application_Data' in config and 'station_name_in_th2_files' in config['Application_Data']:
            NAMES = 0 if config['Application_Data']['station_name_in_th2_files'] == "False" else 1
        

#################################################################################################
def copy_template_if_not_exists(template_path, destination_path):
    # Check if the destination folder exists
    try:
        if not os.path.exists(destination_path):
            # If the destination folder does not exist, copy the template
            shutil.copytree(template_path, destination_path)  
            log.info(f"The folder '{Colors.ENDC}{template_path}{Colors.GREEN}' has been copied to '{Colors.ENDC}{safe_relpath(destination_path)}")
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
        global_data.error_count += 1
        
    
#################################################################################################
def process_template(template_path, variables, output_path):
    """
    Process a Therion template file by replacing variables.
    
    Args:
        template_path (str): Path to the original template file
        variables (dict): Dictionary of variables to replace
        output_path (str): Path for the new configuration file
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
        global_data.error_count += 1
        
    except PermissionError:
        log.error(f"Insufficient permissions to write the file")
        global_data.error_count += 1
        
    except Exception as e:
        log.error(f"An error occurred (process_template): {Colors.ENDC}{e}")
        global_data.error_count += 1


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
        global_data.error_count += 1
        
    except PermissionError:
        log.error(f"Insufficient permissions to read {Colors.ENDC}{safe_relpath(file_path)}")
        global_data.error_count += 1
        
    except Exception as e:
        log.error(f"An error occurred (parse_therion_surveys): {Colors.ENDC}{e}{Colors.ERROR}, file: {Colors.ENDC}{safe_relpath(file_path)}")
        global_data.error_count += 1
        
    
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
def select_file():
    # Créer une instance de la fenêtre tkinter
    root = tk.Tk()
    # Cacher la fenêtre principale
    root.withdraw()
    # Afficher la boite de dialogue de sélection de fichier
    file_path = filedialog.askopenfilename(
        title="Select your file",
        filetypes=[("Compatibles files", "*.th *.mak *.dat"), ("TH files", "*.th"), ("DAT files", "*.dat"), ("MAK files", "*.mak"),("All files", "*.*")]
        )
    # Retourner le chemin complet du fichier sélectionné
    return file_path


################################################################################################# 
# Création des dossiers à partir d'un th file                                                   #
#################################################################################################   
def createThFolders(ENTRY_FILE, PROJECTION = "Plan", TARGET = "None", FORMAT = "th2", SCALE = "500", UPDATE = "", CONFIG_PATH = "") :  
#"""
# Entrées :
#   ENTRY_FILE : input th file 
#   PROJECTION : Plan ou Extended (Extended, not yet implanted)
#   TARGET : Scrap name if different from 'ENTRY_FILE' name
#   FORMAT : Output format, either th2 for producing skeleton for drawing or plt for visualizing in aven/loch", default="th2"
#   SCALE : Scale for the th2 exports, default="500"
#   UPDATE : Mode update, option th2" update only th2 files, default="" update all data
#
# Sorties :
#   Création des dossiers nécessaires d'après dossier 'template'                              
#   Création des fichiers nécessaires : th, th2, -tot.th                                      
#   Création des scrap avec stations topo                                                     
#
#"""
    global Author
    global Copyright
    global Copyright_Short
    global map_comment
    global club
    global thanksto
    global datat
    global wpage
    global cs
    global template_path
    global station_by_scrap
    global final_therion_exe
    global therion_path
    global LINES
    global NAMES
    
    TH_NAME = sanitize_filename(os.path.splitext(os.path.basename(ENTRY_FILE))[0])
    # DEST_PATH = os.path.dirname(args.survey_file) + "/" + TH_NAME
    DEST_PATH = os.path.dirname(ENTRY_FILE) + "/" + TH_NAME
    ABS_PATH = os.path.dirname(ENTRY_FILE)
    
    log.debug(f"ENTRY_FILE: {ENTRY_FILE}") 
    log.debug(f"PROJECTION: {PROJECTION}") 
    log.debug(f"TARGET: {TARGET}") 
    log.debug(f"FORMAT: {FORMAT}")     
    log.debug(f"SCALE: {SCALE}")
    log.debug(f"TH_NAME: {TH_NAME}")
    log.debug(f"DEST_PATH: {DEST_PATH}")
    log.debug(f"ABS_PATH: {ABS_PATH}")  
          
    if PROJECTION.lower() != "plan" :
        log.critical(f"Sorry, projection '{Colors.ENDC}{PROJECTION}{Colors.ERROR}' not yet implemented{Colors.ENDC}")
        exit(1)
    
    if not os.path.isfile(ENTRY_FILE):
        log.critical(f"The Therion file didn't exist: {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")
        exit(1)

    if FORMAT not in ["th2", "plt"]:
        log.critical(f"Please choose a supported format: th2, plt{Colors.ENDC}")
        exit(1)

    # Normalise name, namespace, key, file path
    log.info(f"Parsing survey entry file:\t{Colors.ENDC}{safe_relpath(ENTRY_FILE)}")

    survey_list = parse_therion_surveys(ENTRY_FILE)
    # print(survey_list)
    
    if TARGET == "None" :
        if len(survey_list) > 1 : 
            log.critical(f"Multiple surveys were found, not yet implemented{Colors.ENDC}")
            exit(1)  
    
    TARGET = sanitize_filename(survey_list[0])
    
    log.info(f"Parsing survey target:\t{Colors.ENDC}{TARGET}")        
    
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
        copy_template_if_not_exists(template_path, DEST_PATH)
        copy_file_with_copyright(ENTRY_FILE, DEST_PATH + "/Data", Copyright)
        
        totdata = f"""\tinput Data/{TH_NAME}.th
            
\t## Pour le plan
\tinput Data/{TH_NAME}-Plan.th2
            
\t## Pour la coupe développée
\tinput Data/{TH_NAME}-Extended.th2
            
\t## Appel des maps
\tinput {TH_NAME}-maps.th
"""
        
        # Adapte templates 
        config_vars = {
            'fileName': TH_NAME,
            'cavename': TH_NAME.replace("_", " "),
            'Author': Author,
            'Copyright': Copyright,
            'Scale' : SCALE,
            'Target' : TARGET,
            'map_comment' : map_comment,
            'club' : club,
            'thanksto' : thanksto.replace("_", r"\_"),
            'datat' : datat.replace("_", r"\_"),
            'wpage' : wpage.replace("_", r"\_"), 
            'cs' : cs,
            'configPath' : CONFIG_PATH,
            'totData' : totdata,
            'other_scraps_plan' : "",
            'file_info' : f'# File generated by pyCreateTh.py (version {Version}) date: {datetime.now().strftime("%Y.%m.%d %H:%M:%S")}',
        }
        
        process_template(DEST_PATH + '/template.thconfig', config_vars, DEST_PATH + '/' +  TH_NAME + '.thconfig')
        process_template(DEST_PATH + '/template-tot.th', config_vars, DEST_PATH + '/' +  TH_NAME + '-tot.th')
        process_template(DEST_PATH + '/template-readme.md', config_vars, DEST_PATH + '/readme.md')
        
       
    #################################################################################################                   
    # Produce the parsable XVI file                                                                 #
    #################################################################################################      
    log.info(f"Compiling 2D XVI file:      \t{Colors.ENDC}{TH_NAME}")
    
    template = """source "{th_file}"
    layout minimal
    scale 1 {scale}
    endlayout

    select {selector}

    #export model -o "{th_name}.lox"
    export map -projection plan -o "{th_name}-Plan.xvi" -layout minimal -layout-debug station-names
    export map -projection extended -o "{th_name}-Extended.xvi" -layout minimal -layout-debug station-names
    """

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

    logfile, tmpdir = compile_template(template, template_args, cleanup=False, therion_path=therion_path)
    
    if logfile == "Therion error":
        # log.error(f"Therion error in: {Colors.ENDC}{TH_NAME}")
        return logfile
        
   
    #################################################################################################    
    # Parse the Plan XVI file                                                                       #
    #################################################################################################
    
    if UPDATE == "th2": 
        th_name_xvi =  DEST_PATH + "/" + TH_NAME + "-Plan.xvi" 
    else :     
        th_name_xvi =  DEST_PATH + "/Data/" + TH_NAME + "-Plan.xvi" 

    log.info(f"Parsing plan XVI file:\t{Colors.ENDC}{safe_relpath(th_name_xvi)}")

    stations = {}
    lines = []
    
    with open(join(th_name_xvi), "r", encoding="utf-8") as f:
        xvi_content = f.read()
        xvi_stations, xvi_shots = xvi_content.split("XVIshots")

        # Extract all the stations
        for line in xvi_stations.split("\n"):
            match = re.search(r"{\s*(-?\d+\.\d+)\s*(-?\d+\.\d+)\s([^@]+)(?:@([^\s}]*))?\s*}", line)
            if match:
                x = match.groups()[0]
                y = match.groups()[1]
                station_number = match.groups()[2]
                namespace = match.groups()[3]
                namespace_array = namespace.split(".") if namespace else []
                station = station_number
                if len(namespace_array) > 1:
                    station = "{}@{}".format(station_number, ".".join(namespace_array[0:-1]))
                stations["{}.{}".format(x, y)] = [x, y, station]

        # Extraire les valeurs x et y à partir des listes dans stations
        x_values = [float(value[0]) for value in stations.values()]
        y_values = [float(value[1]) for value in stations.values()]

        # Trouver les min et max de x
        x_min = float(min(x_values))
        x_max = float(max(x_values))

        # Trouver les min et max de y
        y_min = float(min(y_values))
        y_max = float(max(y_values))

        x_ecart = x_max - x_min
        y_ecart = y_max - y_min

        # Afficher les résultats
        # log.debug("x_min:", x_min, "x_max:", x_max)
        # log.debug("y_min:", y_min, "y_max:", y_max)
        # log.debug("Écart max-min pour x:", x_ecart)
        # log.debug("Écart max-min pour y:", y_ecart)
        
        # Extract all the lines
        for line in xvi_shots.split("\n"):
            match = re.search(r"^\s*{\s*(-?\d+\.\d+)\s*(-?\d+\.\d+)\s*(-?\d+\.\d+)\s*(-?\d+\.\d+)\s*.*}", line )
            if match:
                x1 = match.groups()[0]
                y1 = match.groups()[1]
                x2 = match.groups()[2]
                y2 = match.groups()[3]
                key1 = "{}.{}".format(x1, y1)
                key2 = "{}.{}".format(x2, y2)
                # Splays won't have stations
                station1 = stations[key1][2] if key1 in stations else None
                station2 = stations[key2][2] if key2 in stations else None
                lines.append([x1, y1, x2, y2, station1, station2])
                
    shutil.rmtree(tmpdir)
    
    if UPDATE == "th2": 
        th2_name = DEST_PATH + "/" + TH_NAME
    else : 
        th2_name = DEST_PATH + "/Data/" + TH_NAME
    output_path = f'{th2_name}-{PROJECTION}.{FORMAT}'
    
    scrap_to_add = int(len(stations)/station_by_scrap)-1

    # log.debug(stations)

    log.info(f"Writing output to:\t{Colors.ENDC}{safe_relpath(output_path)}")

    # Write TH2
    if FORMAT == "th2":
        th2_file_header = """encoding  utf-8"""

        th2_file = """
##XTHERION## xth_me_area_adjust {X_Min} {Y_Min} {X_Max} {Y_Max}
##XTHERION## xth_me_area_zoom_to 100
##XTHERION## xth_me_image_insert {insert_XVI} 

{Copyright}
# File generated by pyCreateTh.py version {version} date: {date}

# x_min: {X_Min}, x_max: {X_Max} ecart : {X_Max_X_Min}
# y_min: {Y_Min}, y_max: {Y_Max} ecart : {Y_Max_Y_Min}

scrap S{projection_short}-{name}_01 -station-names "" "@{name}" -projection {projection} -author {year} "{author}" -copyright {year} "{Copyright_Short}"
    
{points}
    
{names}
    
{lines}
    
endscrap"""

        th2_point = """    point {x} {y} station -name {station}"""
        th2_name  = """    point {x} {y} station-name -align tr -scale xs -text {station}"""

        th2_line  = """    line u:Shot_Survey
            {x1} {y1}
            {x2} {y2}
            
        endline"""

        seen = set()
        th2_lines = []
        th2_points = []
        th2_names = []
        other_scraps_plan = f"\tS{PROJECTION[0].upper()}-{TARGET}_01\n\tbreak\n"
        
        for line in lines:
            th2_lines.append(th2_line.format(x1=line[0], y1=line[1], x2=line[2], y2=line[3]))
            coords1 = "{}.{}".format(line[0], line[1])
            
            if coords1 not in seen:
                seen.add(coords1)
                th2_points.append(th2_point.format(x=line[0], y=line[1], station=line[4]))
                th2_names.append(th2_name.format(x=line[0], y=line[1], station=line[4]))
            coords2 = "{}.{}".format(line[2], line[3])
            
            if "{}.{}".format(line[2], line[3]) not in seen:
                seen.add(coords2)
                if line[5] != None:
                    th2_points.append(th2_point.format(x=line[2], y=line[3], station=line[5]))
                    th2_names.append(th2_name.format(x=line[2], y=line[3], station=line[5]))


        if isfile(output_path):
            log.warning(f"{Colors.ENDC}{os.path.basename(output_path)}{Colors.WARNING} file already exists - nothing done")

        else :
            name = TARGET, 
            log.debug(f"Therion output path :\t{Colors.ENDC}{safe_relpath(output_path)}")

            with open(str(output_path), "w+") as f:
                f.write(th2_file_header)
                f.write(th2_file.format(
                        name = sanitize_filename(name[0]),
                        Copyright = Copyright,
                        Copyright_Short = Copyright_Short,
                        points="\n".join(th2_points),
                        lines="\n".join(th2_lines) if LINES else "",
                        names="\n".join(th2_names) if NAMES else "",
                        projection=PROJECTION.lower(),
                        projection_short=PROJECTION[0].upper(),
                        author=Author,
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
                        other_scraps_plan = other_scraps_plan + f"\tS{PROJECTION[0].upper()}-{name[0]}_{i+2:02}\n\tbreak\n"
                        th2_scrap = """
                        
scrap S{projection_short}-{name}_{num:02} -station-names "" "@{name}" -projection {projection} -author {year} "{author}" -copyright {year} "{Copyright_Short}" 
    
endscrap

"""
                        f.write(th2_scrap.format(
                            name=name[0],
                            projection=PROJECTION.lower(),
                            projection_short=PROJECTION[0].upper(),
                            author=Author,
                            year=datetime.now().year,
                            Copyright_Short = Copyright_Short,
                            num=f"{i+2:02}",                         
                            )
                        )
                            

    #################################################################################################    
    # Parse the Extended XVI file                                                                   #
    #################################################################################################
    if UPDATE == "th2": 
        th_name_xvi =  DEST_PATH + "/" + TH_NAME + "-Extended.xvi" 
    else :
        th_name_xvi =  DEST_PATH + "/Data/" + TH_NAME + "-Extended.xvi" 

    log.info(f"Parsing extended XVI file:\t{Colors.ENDC}{safe_relpath(th_name_xvi)}")

    # Parse the Extended XVI file
    stations = {}
    lines = []
    
    with open(join(th_name_xvi), "r", encoding="utf-8") as f:
        xvi_content = f.read()
        xvi_stations, xvi_shots = xvi_content.split("XVIshots")

        # Extract all the stations
        for line in xvi_stations.split("\n"):
            match = re.search(r"{\s*(-?\d+\.\d+)\s*(-?\d+\.\d+)\s([^@]+)(?:@([^\s}]*))?\s*}", line)
            if match:
                x = match.groups()[0]
                y = match.groups()[1]
                station_number = match.groups()[2]
                namespace = match.groups()[3]
                namespace_array = namespace.split(".") if namespace else []
                station = station_number
                if len(namespace_array) > 1:
                    station = "{}@{}".format(station_number, ".".join(namespace_array[0:-1]))
                stations["{}.{}".format(x, y)] = [x, y, station]

        # Extraire les valeurs x et y à partir des listes dans stations
        x_values = [float(value[0]) for value in stations.values()]
        y_values = [float(value[1]) for value in stations.values()]

        # Trouver les min et max de x
        x_min = float(min(x_values))
        x_max = float(max(x_values))

        # Trouver les min et max de y
        y_min = float(min(y_values))
        y_max = float(max(y_values))

        x_ecart = x_max - x_min
        y_ecart = y_max - y_min

        # Afficher les résultats
        # log.debug("x_min:", x_min, "x_max:", x_max)
        # log.debug("y_min:", y_min, "y_max:", y_max)
        # log.debug("Écart max-min pour x:", x_ecart)
        # log.debug("Écart max-min pour y:", y_ecart)
        
        # Extract all the lines
        for line in xvi_shots.split("\n"):
            match = re.search(r"^\s*{\s*(-?\d+\.\d+)\s*(-?\d+\.\d+)\s*(-?\d+\.\d+)\s*(-?\d+\.\d+)\s*.*}", line )
            if match:
                x1 = match.groups()[0]
                y1 = match.groups()[1]
                x2 = match.groups()[2]
                y2 = match.groups()[3]
                key1 = "{}.{}".format(x1, y1)
                key2 = "{}.{}".format(x2, y2)
                # Splays won't have stations
                station1 = stations[key1][2] if key1 in stations else None
                station2 = stations[key2][2] if key2 in stations else None
                lines.append([x1, y1, x2, y2, station1, station2])
    shutil.rmtree(tmpdir)

    if UPDATE == "th2":
        th2_name = DEST_PATH + "/" + TH_NAME
    else :
        th2_name = DEST_PATH + "/Data/" + TH_NAME
    output_path = f'{th2_name}-Extended.{FORMAT}'

    log.info(f"Writing output to:\t\t{Colors.ENDC}{safe_relpath(output_path)}")

    # Write TH2
    if FORMAT == "th2":
        th2_file_header = """encoding  utf-8"""

        th2_file = """
##XTHERION## xth_me_area_adjust {X_Min} {Y_Min} {X_Max} {Y_Max}
##XTHERION## xth_me_area_zoom_to 100
##XTHERION## xth_me_image_insert {insert_XVI} 

{Copyright}
# File generated by pyCreateTh.py version {version} date: {date}

# x_min: {X_Min}, x_max: {X_Max} ecart : {X_Max_X_Min}
# y_min: {Y_Min}, y_max: {Y_Max} ecart : {Y_Max_Y_Min}

scrap SC-{name}_01 -station-names "" "@{name}" -projection extended -author {year} "{author}" -copyright {year} "{Copyright_Short}"
    
{points}
    
{names}
    
{lines}
    
endscrap"""

        th2_point = """    point {x} {y} station -name {station}"""
        th2_name  = """    point {x} {y} station-name -align tr -scale xs -text {station}"""

        th2_line  = """    line u:Shot_Survey 
            {x1} {y1}
            {x2} {y2}
        endline
        """

        seen = set()
        th2_lines = []
        th2_points = []
        th2_names = []
        other_scraps_extended = f"\tSC-{TARGET}_01\n\tbreak\n"
        
        for line in lines:
            th2_lines.append(th2_line.format(x1=line[0], y1=line[1], x2=line[2], y2=line[3]))
            coords1 = "{}.{}".format(line[0], line[1])
            
            if coords1 not in seen:
                seen.add(coords1)
                th2_points.append(th2_point.format(x=line[0], y=line[1], station=line[4]))
                th2_names.append(th2_name.format(x=line[0], y=line[1], station=line[4]))
            coords2 = "{}.{}".format(line[2], line[3])
            
            if "{}.{}".format(line[2], line[3]) not in seen:
                seen.add(coords2)
                if line[5] != None:
                    th2_points.append(th2_point.format(x=line[2], y=line[3], station=line[5]))
                    th2_names.append(th2_name.format(x=line[2], y=line[3], station=line[5]))


        if isfile(output_path):
            log.warning(f"{Colors.ENDC}{os.path.basename(output_path)}{Colors.WARNING} file already exists - nothing done{Colors.ENDC}")
        else :
            name = TARGET, 
            log.debug(f"Therion output path :\t{Colors.ENDC}{output_path}")
                 
            with open(str(output_path), "w+") as f:
                f.write(th2_file_header)
                f.write(th2_file.format(
                        name = sanitize_filename(name[0]),
                        Copyright = Copyright,
                        Copyright_Short = Copyright_Short,
                        points="\n".join(th2_points),
                        lines="\n".join(th2_lines) if LINES else "",
                        names="\n".join(th2_names) if NAMES else "",
                        projection="extended",
                        projection_short="C",
                        author=Author,
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
                        other_scraps_extended = other_scraps_extended + f"\tSC-{name[0]}_{i+2:02}\n\tbreak\n"
                        th2_scrap = """
                        
scrap SC-{name}_{num:02} -station-names "" "@{name}" -projection extended -author {year} "{author}" -copyright {year} "{Copyright_Short}" 
    
endscrap

"""
                        f.write(th2_scrap.format(
                            name=name[0],
                            author=Author,
                            Copyright_Short = Copyright_Short,
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
                        'Author': Author,
                        'Copyright': Copyright,
                        'Scale' : SCALE,
                        'Target' : TARGET,
                        'map_comment' : map_comment,
                        'club' : club,
                        'thanksto' : thanksto,
                        'datat' : datat,
                        'wpage' : wpage, 
                        'cs' : cs,
                        'configPath' : CONFIG_PATH,
                        'other_scraps_plan' : other_scraps_plan,
                        'other_scraps_extended' : other_scraps_extended,
                        'file_info' : f"# File generated by pyCreateTh.py version {Version} date: {datetime.now().strftime("%Y.%m.%d-%H:%M:%S")}",
                }
                

        process_template(DEST_PATH + '/template-maps.th', config_vars, DEST_PATH + '/' +  TH_NAME + '-maps.th')
    
        
    #################################################################################################     
    # Final therion compilation                                                                     #
    #################################################################################################

    if UPDATE == "":   
        if final_therion_exe == True:
            FILE = os.path.dirname(ENTRY_FILE) + "/" + TH_NAME + "/" + TH_NAME + ".thconfig"      
            # log.info(f"Final therion compilation: {Colors.ENDC}{safe_relpath(FILE)}")     
            compile_file(FILE, therion_path=therion_path) 

################################################################################################# 
# lecture d'un .file                                                                            #
#################################################################################################    
def makToThFile(ENTRY_FILE) :
    
    _ConfigPath = "./../../"
    
    datFiles = []
    patternDat = re.compile(r'^#.*?\.dat[,;]$', re.IGNORECASE)  # Motif insensible à la casse
    
    fixPoints = []
    patternFixPoints = re.compile(r'^([\w-]+)\[(m|f),\s*(-?\d+\.?\d*),\s*(-?\d+\.?\d*),\s*(-?\d+\.?\d*)\][,;]$', re.IGNORECASE)
    
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
        log.error(f"The mak file {ENTRY_FILE} dit not exist")
        global_data.error_count += 1
        
    except Exception as e:
        log.error(f"An error occurred (readMakFile): {Colors.ENDC}{e}")
        global_data.error_count += 1
        
    
    # Vérification des valeurs
    if len(Datums) > 1:
        log.critical(f"Several different Datums found in {Colors.ENDC}{safe_relpath(ENTRY_FILE)}{Colors.CRITICAL}, case not handled! : {Colors.ENDC}{Datums}")
        exit(0)
    elif not Datums :
        log.critical(f"no datum found in mak file : {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")
        exit(0)
    elif not datFiles :
        log.critical(f"No dat file found in mak file : {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")
        exit(0)
    elif not fixPoints :
        log.critical(f"No fix points found in mak file : {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")
        exit(0)
    
    datum_to_epsg = {
        # Datums globaux
        "wgs84": "326",   # UTM Nord (WGS84) - EPSG:326XX
        "etrs89": "258",   # UTM Nord (ETRS89) - Europe
        
        # Datums européens
        "european1950": "230",  # ED50 / UTM Nord - Europe
        "ed50": "230",
        
        # Datums nord-américains
        "nad27": "267",    # UTM Nord (NAD27) - Amérique du Nord
        "northamericandatum1927": "267",
        "northamerican1927": "267",
        "nad83": "269",    # UTM Nord (NAD83) - Amérique du Nord
        "northamericandatum1983": "269",
        "northamerican1983" : "269",
        
        # Datums français
        "ntf": "275",      # UTM Nord (NTF) - France (Paris)
        "nouvelletriangulationfrançaise": "275",
        
        # Datums africains
        "clarke1880": "297",  # UTM Nord (Clarke 1880) - Afrique
        
        # Datums australiens
        "agd66": "202",    # UTM Nord (AGD66) - Australie
        "australiangeodeticdatum1966": "202",
        "australiangeodetic1966": "202",
        "agd84": "203",    # UTM Nord (AGD84) - Australie
        "australiangeodeticdatum1984": "203",
        "australiangeodetic1984": "203",
        "gda94": "283",    # UTM Nord (GDA94) - Australie
        "geocentricdatumofaustralia1994": "283",
        "geocentricofaustralia1994": "283",
        
        # Datums asiatiques
        "pulkovo1942": "284",  # UTM Nord (Pulkovo 1942) - Russie/CEI
        "beijing1954": "214",  # UTM Nord (Beijing 1954) - Chine
        
        # Datums sud-américains
        "sad69": "291",    # UTM Nord (SAD69) - Amérique du Sud
        "southamericandatum1969": "291",
        "southamerican1969": "291",
        "sirgas2000": "319",  # UTM Nord (SIRGAS 2000) - Amérique Latine
    }
    

    datum_lower = next(iter(Datums)).strip().lower().replace(" ","")
    if datum_lower not in datum_to_epsg:
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
    epsg_prefix = datum_to_epsg[datum_lower]
    epsg_code = f"{epsg_prefix}{zone_num}" if hemisphere == "N" else f"{epsg_prefix}{zone_num + 100}"
    
    # Génération du CRS QGIS (format WKT)
    crs_wkt = f'EPSG:{epsg_code}'

    log.info(f"Reading mak file : {Colors.ENDC}{safe_relpath(ENTRY_FILE)}{Colors.GREEN}, fixed station : {Colors.ENDC}{len(fixPoints)}{Colors.GREEN}, files {Colors.ENDC}{len(datFiles)}{Colors.GREEN}, UTM Zone : {Colors.ENDC}{UTM[0]}{Colors.GREEN}, Datum : {Colors.ENDC}{next(iter(Datums))}{Colors.GREEN}, SCR : {Colors.ENDC}{crs_wkt}")
    # log.debug(datFiles)
    # log.debug(fixPoints)
    
    fixPoints 
    
    SurveyTitleMak =  sanitize_filename(os.path.basename(abspath(args.survey_file))[:-4])
        
    folderDest = os.path.dirname(abspath(args.survey_file)) + "/" + SurveyTitleMak
        
    copy_template_if_not_exists(template_path,folderDest)
    
    stationList = pd.DataFrame(columns=['StationName', 'Survey_Name_01', 'Survey_Name_02'])
    totdata = f"\t## Liste inputs\n"
    totMapsPlan = ""
    totMapsExtended = ""
    
    for file in datFiles :      
        _file = os.path.dirname(abspath(args.survey_file)) + "\\"+ file
        shutil.copy(_file, folderDest + "\\Data\\")
        ABS_file = folderDest + "\\Data\\"+ file
        Station, SurveyTitle = datToThFiles (ABS_file, fixPoints, crs_wkt, _ConfigPath)
        
        totdata +=f"\tinput Data/{SurveyTitle}/{SurveyTitle}-tot.th\n" 
        totMapsPlan += f"\tMP-{SurveyTitle}-Plan-tot@{SurveyTitle}\n\tbreak\n"
        totMapsExtended += f"\tMC-{SurveyTitle}-Extended-tot@{SurveyTitle}\n\tbreak\n"

        if not Station.empty:  # pour éviter d'ajouter des DataFrames vides
            stationList = pd.concat([stationList, Station], ignore_index=True)
            stationList.sort_values(by='Survey_Name_02', inplace=True, ignore_index=True)


        destination = os.path.join(folderDest, "Sources", os.path.basename(ABS_file))
        if os.path.exists(destination):
            os.remove(destination)

        shutil.move(ABS_file, destination)  
    
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
                    'cavename': SurveyTitleMak.replace("_", " "),
                    'Author': Author,
                    'Copyright': Copyright,
                    'Scale' : args.scale,
                    'Target' : "TARGET",
                    'map_comment' : map_comment,
                    'club' : club,
                    'thanksto' : thanksto,
                    'datat' : datat,
                    'wpage' : wpage, 
                    'cs' : crs_wkt,
                    'configPath' : " ",
                    'totData' : totdata,
                    'other_scraps_plan' : totMapsPlan,
                    'other_scraps_extended' : totMapsExtended,
                    'file_info' : f"# File generated by pyCreateTh.py version {Version} date: {datetime.now().strftime("%Y.%m.%d-%H:%M:%S")}",
            }

    DEST_PATH = os.path.dirname(args.survey_file) + '/' +  SurveyTitleMak

    process_template(DEST_PATH + '/template.thconfig', config_vars, DEST_PATH + '/' +  SurveyTitleMak + '.thconfig')
    process_template(DEST_PATH + '/template-tot.th', config_vars, DEST_PATH + '/' + SurveyTitleMak + '-tot.th')
    process_template(DEST_PATH + '/template-maps.th', config_vars, DEST_PATH + '/' +  SurveyTitleMak + '-maps.th')
    process_template(DEST_PATH + '/template-readme.md', config_vars, DEST_PATH + '/readme.md')
    
    return 

#################################################################################################
def station_List(data, list, fixPoints) :  
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
def formated_Station_List(df, dataFormat ,unit = "meter", ENTRY_FILE = None) :
        
        # Remplacer les None/NaN par des espaces
        df = df.fillna(" ")

        # Conserver la première ligne (en-têtes) séparément
        header_row = df.iloc[0]

        # Traiter uniquement les lignes à partir de la deuxième (index 1)
        df_data = df.iloc[1:].copy()
                    
        columns = dataFormat.split()

        Koef = 0.3048 if unit == "meter" else 1.0
            
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
                log.warning(f"Flags '{Colors.ENDC}{col10}{Colors.WARNING}' not implemented in therion, line {Colors.ENDC}{idx+1}{Colors.WARNING} in {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")

            # Si la colonne 10 contient #|P#    exclude from plotting
            elif "#|P#" in col10:
                surface_row = [" "] * len(row)
                surface_row[0] = "# flags exclude from plot no implemented"
                new_rows.append(surface_row)

                new_rows.append(row.tolist())

                not_surface_row = [" "] * len(row)
                not_surface_row[0] = "# flags not exclude from plot no implemented"
                new_rows.append(not_surface_row)
                log.warning(f"Flags exclude from plot #|P# not implemented in therion, line {Colors.ENDC}{idx+1}{Colors.WARNING} in {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")

            # Si la colonne 10 contient #|C#    exclude from closure
            elif "#|C#" in col10:
                surface_row = [" "] * len(row)
                surface_row[0] = "# flags exclude from closure no implemented"
                new_rows.append(surface_row)

                new_rows.append(row.tolist())

                not_surface_row = [" "] * len(row)
                not_surface_row[0] = "# flags not exclude from closure no implemented"
                new_rows.append(not_surface_row)
                log.warning(f"Flags #|C# exclude from closure not implemented in therion, line {Colors.ENDC}{idx+1}{Colors.WARNING} in {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")

            # Si la colonne 10 contient #|PL#    exclude from plotting and Length
            elif "#|PL#" in col10 or "#|LP#" in col10:
                surface_row = [" "] * len(row)
                surface_row[0] = "flags duplicate"
                new_rows.append(surface_row)

                new_rows.append(row.tolist())

                not_surface_row = [" "] * len(row)
                not_surface_row[0] = "flags not duplicate"
                new_rows.append(not_surface_row)
                log.warning(f"Flags '{Colors.ENDC}{col10}{Colors.WARNING}' not implemented in therion, line {Colors.ENDC}{idx+1}{Colors.WARNING} in {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")

            # Si la colonne 10 contient #|LC#    exclude from Length and Closure
            elif "#|LC#" in col10 or "#|CL#" in col10:
                surface_row = [" "] * len(row)
                surface_row[0] = "flags duplicate"
                new_rows.append(surface_row)

                new_rows.append(row.tolist())

                not_surface_row = [" "] * len(row)
                not_surface_row[0] = "flags not duplicate"
                new_rows.append(not_surface_row)
                log.warning(f"Flags '{Colors.ENDC}{col10}{Colors.WARNING}' not implemented in therion, line {Colors.ENDC}{idx+1}{Colors.WARNING} in {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")

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
                log.error(f"Flags unknown '{Colors.ENDC}{col10}{Colors.WARNING}' not implemented, line {Colors.ENDC}{idx+1}{Colors.WARNING} in {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")
                global_data.error_count += 1
                
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
            row_str = "\t\t" + "\t".join(map(str, row))
            output.append(row_str)

        # print(new_rows)
            
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
def pointsUniques(data, crs_wkt):
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
# Création des dossiers Th à partir d'un dat                                                    #
#################################################################################################  
def datToThFiles (ENTRY_FILE, fixPoints = [], crs_wkt = "", CONFIG_PATH = "") :
# Input : Dat file for conversion
# Outputs : Th files by survey
    global Author
    global Copyright
    global Copyright_Short
    global map_comment
    global club
    global thanksto
    global datat
    global wpage
    global cs
    global template_path
    global station_by_scrap
    global final_therion_exe
    global therion_path
    global LINES
    global NAMES

    
    # Détecter la fin de section (FF CR LF qui correspond à \x0c\r\n)
    section_separator = '\x0c'
    content = ""
    
    #################################################################################################     
    # Lecture du fichier dat                                                                        #
    ################################################################################################# 
    try:
        result = from_path(ENTRY_FILE)
        best_guess = result.best()
        
        if best_guess is None or best_guess.encoding is None:
            log.critical(f"Unable to detect the file encoding {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")
            exit(0)
            return None
        
        encoding_detected = best_guess.encoding.lower()
        
        with open(ENTRY_FILE, 'r', encoding=encoding_detected) as f:
            content = f.read()
        
        if encoding_detected.lower() != 'utf-8':
            log.info(f"{Colors.ENDC}{safe_relpath(ENTRY_FILE)}{Colors.GREEN}, encodage : {Colors.ENDC}{encoding_detected}{Colors.GREEN} conversion utf-8")
        else :
            log.debug(f"{Colors.ENDC}{safe_relpath(ENTRY_FILE)}{Colors.DEBUG}, encodage : {Colors.ENDC}{encoding_detected}")

    except FileNotFoundError:
        log.error(f"The dat file {Colors.ENDC}{safe_relpath(ENTRY_FILE)} {Colors.ERROR}did not exist")
        global_data.error_count += 1
        
    except Exception as e:
        log.error(f"An error occurred (datToThFiles): {Colors.ENDC}{e}{Colors.ERROR}, file : {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")
        global_data.error_count += 1
        
    
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
    
    # Tableau global pour stocker toutes les stations
    stationList = pd.DataFrame(columns=['StationName', 'Survey_Name_01', 'Survey_Name_02'])
    
    section0 = True; 
    
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
            
        for line in lines:
            line = line.strip()
            if line.startswith('SURVEY NAME:'):
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
                    log.warning(f"Attention, survey {Colors.ENDC}{section_data['SURVEY_NAME']}{Colors.WARNING} with no date, add default date 2000 01 01 ")
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
            listStationSection, dfDATA = station_List(section_data, listStationSection, fixPoints)
            section_data['STATION'] = listStationSection
            data.append(section_data)    
            unique_id += 1 

            #################################################################################################     
            # Détecter les survey avec plusieurs points de départ                                           #
            #################################################################################################    
  
            points = pointsUniques(section_data, crs_wkt)

            if len(points) > 1 :
                log.warning(f"Points {Colors.ENDC}{points}{Colors.ERROR} uniques dans la section {Colors.ENDC}{section_data['SURVEY_NAME']}: ")
                # global_data.error_count += 1
                
            else :
                log.debug(f"Points {Colors.ENDC}{points}{Colors.DEBUG} uniques dans la section {section_data['SURVEY_NAME']}")


    
    #################################################################################################
    # Grouper les sections ayant même date team et un point commun                                  #
    #################################################################################################
 
    duplicates = find_duplicates_by_date_and_team(data)
    
    # for d in duplicates:
    #     print(d['IDS'])
    #     for i  in range (len(d['IDS'])) :
    #         log.debug(f"ID: {data[d['IDS'][i]]['ID']}, DATE: {data[d['IDS'][i]]['SURVEY_DATE']}, TEAM: {data[d['IDS'][i]]['SURVEY_TEAM']}, Station : {d['COMMON_STATIONS']}")
    #     print()
        

    
    oldLen = len(data)    
    
    # for line in data :
    #     if line['ID'] == 3 :
    #         log.debug(f"ID: {Colors.ENDC}{line['ID']}")
    #         log.debug(f"SURVEY TITLE: {Colors.ENDC}{line['SURVEY_TITLE']}")
    #         log.debug(f"SURVEY NAME: {Colors.ENDC}{line['SURVEY_NAME']}")
    #         log.debug(f"SURVEY DATE: {Colors.ENDC}{line['SURVEY_DATE']}")
    #         log.debug(f"COMMENT: {Colors.ENDC}{line['COMMENT']}")
    #         log.debug(f"SURVEY TEAM: {Colors.ENDC}{line['SURVEY_TEAM']}")
    #         log.debug(f"DECLINATION: {Colors.ENDC}{line['DECLINATION']}")
    #         log.debug(f"FORMAT: {Colors.ENDC}{line['FORMAT']}")
    #         log.debug(f"CORRECTIONS: {Colors.ENDC}{line['CORRECTIONS']}")
    #         log.debug(f"DATA: {Colors.ENDC}{(line['DATA'])}")
    #         log.debug(f"DATA Qté: {Colors.ENDC}{len(line['DATA'])}")
    #         log.debug(f"STATION: {Colors.ENDC}{(line['STATION'])}")
    #         log.debug(f"SOURCE: {Colors.ENDC}{line['SOURCE']}\n")
    #         # print(f"DATA: {Colors.ENDC}{line['DATA']}")

    data = merge_duplicate_surveys(data, duplicates)
    
    # for line in data :
    #     if line ['ID'] == 10000 :
    #         log.debug(f"ID: {Colors.ENDC}{line['ID']}")
    #         log.debug(f"SURVEY TITLE: {Colors.ENDC}{line['SURVEY_TITLE']}")
    #         log.debug(f"SURVEY NAME: {Colors.ENDC}{line['SURVEY_NAME']}")
    #         log.debug(f"SURVEY DATE: {Colors.ENDC}{line['SURVEY_DATE']}")
    #         log.debug(f"COMMENT: {Colors.ENDC}{line['COMMENT']}")
    #         log.debug(f"SURVEY TEAM: {Colors.ENDC}{line['SURVEY_TEAM']}")
    #         log.debug(f"DECLINATION: {Colors.ENDC}{line['DECLINATION']}")
    #         log.debug(f"FORMAT: {Colors.ENDC}{line['FORMAT']}")
    #         log.debug(f"CORRECTIONS: {Colors.ENDC}{line['CORRECTIONS']}")
    #         log.debug(f"DATA: {Colors.ENDC}{(line['DATA'])}")
    #         log.debug(f"DATA Qté: {Colors.ENDC}{len(line['DATA'])}")
    #         log.debug(f"STATION: {Colors.ENDC}{(line['STATION'])}")
    #         log.debug(f"SOURCE: {Colors.ENDC}{line['SOURCE']}\n")
    #         # print(f"DATA: {Colors.ENDC}{line['DATA']}")

    log.info(f"Read dat file : {Colors.ENDC}{safe_relpath(ENTRY_FILE)}{Colors.GREEN} with {Colors.ENDC}{len(data)}/{oldLen}{Colors.GREEN} survey")
    

    #################################################################################################     
    # Créer fichier th converti                                                                     #
    #################################################################################################
    
    if data[0]['SURVEY_TITLE'] !="" :
        SurveyTitle = sanitize_filename(data[0]['SURVEY_TITLE'])  
        folderDest = os.path.dirname(ENTRY_FILE) + "\\" + SurveyTitle
        if os.path.isdir(folderDest): 
           SurveyTitle = sanitize_filename(os.path.basename(ENTRY_FILE[:-4]))
    else :
        SurveyTitle = sanitize_filename(os.path.basename(ENTRY_FILE[:-4]))

    folderDest = os.path.dirname(ENTRY_FILE) + "\\" + SurveyTitle
    
    copy_template_if_not_exists(template_path,folderDest)
    
    if  args.survey_file[-3:].lower() != "dat" :
        _destination =  folderDest + "\\config.thc"
        # print(f"destination_path : {_destination}")
        os.remove(_destination)
    
    
    for _line in data :    
    
        th_file = """
encoding  utf-8    
# File generated by pyCreateTh.py version {VERSION} date: {DATE}

survey {SURVEY_NAME} -title "{COMMENT}"

\tcenterline
\t\tdate {SURVEY_DATE}
\t\t# team {SURVEY_TEAM}

{FIX_POINTS}

\t\t# explo-date ????
\t\t# explo-team "????"

\t\t# FORMAT: {FORMAT}, CORRECTIONS: {CORRECTIONS}
\t\tunits length {LENGTH}
\t\tunits compass {COMPASS}
\t\tunits clino {CLINO}
\t\t{DATA_FORMAT} 

#{DATA}

\tendcenterline
endsurvey

{SOURCE}

    """

        output_file = folderDest + "\\Data\\" + sanitize_filename(_line['SURVEY_NAME']) + ".th" 
        
        #################################################################################################     
        # gestion des déclinaisons                                                                      #
        #################################################################################################
        
    
        #################################################################################################     
        # gestion des DATA                                                                              #
        #################################################################################################
    
        stationList, dfDATA = station_List(_line, stationList, fixPoints)

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
                if point[1] == 'm' :
                    fixPoint +=  f"\t\tfix {point[0]} {point[2]} {point[3]}	{point[4]}\n" 
                elif point[1] == 'f' :
                    fixPoint +=  f"\t\tfix {point[0]} {point[2]*0.3048} {point[3]*0.3048}	{point[4]*0.3048} # Conversion feet - meter\n" 
        
         
        ################################################################################################# 
        # Gestion des formats
        ################################################################################################# 
        if _line['FORMAT'] is None or len(_line['FORMAT']) < 11:
            log.error(f"Error in format code ID {Colors.ENDC}{_line['ID']}")
            log.debug(f"Error in format code SURVEY_NAME {Colors.ENDC}{_line['SURVEY_NAME']}")
            log.debug(f"Error in format code SURVEY_DATE {Colors.ENDC}{_line['SURVEY_DATE']}")
            log.debug(f"SURVEY TITLE: {Colors.ENDC}{_line['SURVEY_TITLE']}")
            log.debug(f"COMMENT: {Colors.ENDC}{_line['COMMENT']}")
            log.debug(f"SURVEY TEAM: {Colors.ENDC}{_line['SURVEY_TEAM']}")
            log.debug(f"DECLINATION: {Colors.ENDC}{_line['DECLINATION']}")
            log.debug(f"FORMAT: {Colors.ENDC}{_line['FORMAT']}")
            log.debug(f"CORRECTIONS: {Colors.ENDC}{_line['CORRECTIONS']}")
            log.debug(f"DATA: {Colors.ENDC}{(_line['DATA'])}")
            log.debug(f"DATA Qté: {Colors.ENDC}{len(_line['DATA'])}")
            log.debug(f"STATION: {Colors.ENDC}{(_line['STATION'])}")
            log.debug(f"SOURCE: {Colors.ENDC}{_line['SOURCE']}\n")
            global_data.error_count += 1
        
        if _line['FORMAT'][0] == 'D' : compass = 'degree'
        elif _line['FORMAT'][0] == 'R' : compass = 'grads'
        else : 
            compass = 'Compass_error'
            log.error("Compass bearing unit 'quads' not yet implemented")
            global_data.error_count += 1
        
        if _line['FORMAT'][1] == 'D' : length = 'feet'
        elif _line['FORMAT'][1] == 'M' : length = 'meter'
        else : 
            length = 'Length_error'
            log.error("Length unit 'Feet and Inches' not yet implemented") 
            global_data.error_count += 1

        
        if _line['FORMAT'][3] == 'D' : clino = 'degree'
        elif _line['FORMAT'][3] == 'R' : clino = 'grads'
        # elif _line['FORMAT'][3] == 'G' : clino = 'percent'   # %Grades à vérifier?  
        # elif _line['FORMAT'][3] == 'M' : clino = 'grads'     # Degrees and Minutes
        # elif _line['FORMAT'][3] == 'W' : clino = 'grads'     # Depth Gauge
        else : 
            clino = 'Inclination_error'
            log.error("Inclination unit not yet implemented")   
            global_data.error_count += 1
            
        dataFormat = ""
        if  _line['FORMAT'][4] == 'U' : dataFormat = dataFormat + " up"
        elif  _line['FORMAT'][4] == 'D' : dataFormat = dataFormat + " down"
        elif  _line['FORMAT'][4] == 'R' : dataFormat = dataFormat + " right"
        elif  _line['FORMAT'][4] == 'L' : dataFormat = dataFormat + " left"
        else : 
            log.error(f"Error in format str 4 code {Colors.ENDC}{_line['FORMAT']}{Colors.ERROR} in {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")
            global_data.error_count += 1
        
        if  _line['FORMAT'][5] == 'U' : dataFormat = dataFormat + " up"
        elif  _line['FORMAT'][5] == 'D' : dataFormat = dataFormat + " down"
        elif  _line['FORMAT'][5] == 'R' : dataFormat = dataFormat + " right"
        elif  _line['FORMAT'][5] == 'L' : dataFormat = dataFormat + " left"
        else : 
            log.error(f"Error in format str 5code {Colors.ENDC}{_line['FORMAT']}{Colors.ERROR} in {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")
            global_data.error_count += 1
        
        if  _line['FORMAT'][6] == 'U' : dataFormat = dataFormat + " up"
        elif  _line['FORMAT'][6] == 'D' : dataFormat = dataFormat + " down"
        elif  _line['FORMAT'][6] == 'R' : dataFormat = dataFormat + " right"
        elif  _line['FORMAT'][6] == 'L' : dataFormat = dataFormat + " left"
        else : 
            log.error(f"Error in format str 6 code {Colors.ENDC}{_line['FORMAT']}{Colors.ERROR} in {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")
            global_data.error_count += 1
        
        if  _line['FORMAT'][7] == 'U' : dataFormat = dataFormat + " up"
        elif  _line['FORMAT'][7] == 'D' : dataFormat = dataFormat + " down"
        elif  _line['FORMAT'][7] == 'R' : dataFormat = dataFormat + " right"
        elif  _line['FORMAT'][7] == 'L' : dataFormat = dataFormat + " left"
        else : 
            log.error(f"Error in format str 7 code {Colors.ENDC}{_line['FORMAT']}{Colors.ERROR} in {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")
            global_data.error_count += 1
        
        if  _line['FORMAT'][10] == 'L' : dataFormat =  " length" + dataFormat
        elif  _line['FORMAT'][10] == 'A' : dataFormat = " compass" + dataFormat
        elif  _line['FORMAT'][10] == 'D' : dataFormat = " clino" + dataFormat
        elif  _line['FORMAT'][10] == 'a' : dataFormat = "  backcompass" + dataFormat
        elif  _line['FORMAT'][10] == 'd' : dataFormat = "  backclino" + dataFormat
        else : 
            log.error(f"Error in format str 10 code {Colors.ENDC}{_line['FORMAT']}{Colors.ERROR} in {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")
            global_data.error_count += 1
        
        if  _line['FORMAT'][9] == 'L' : dataFormat =  " length" + dataFormat
        elif  _line['FORMAT'][9] == 'A' : dataFormat = " compass" + dataFormat
        elif  _line['FORMAT'][9] == 'D' : dataFormat = " clino" + dataFormat
        elif  _line['FORMAT'][9] == 'a' : dataFormat = "  backcompass" + dataFormat
        elif  _line['FORMAT'][9] == 'd' : dataFormat = "  backclino" + dataFormat
        else : 
            log.error(f"Error in format str 9 code {Colors.ENDC}{_line['FORMAT']}{Colors.ERROR} in {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")
            global_data.error_count += 1
        
        if  _line['FORMAT'][8] == 'L' : dataFormat =  " length" + dataFormat
        elif  _line['FORMAT'][8] == 'A' : dataFormat = " compass" + dataFormat
        elif  _line['FORMAT'][8] == 'D' : dataFormat = " clino" + dataFormat
        elif  _line['FORMAT'][8] == 'a' : dataFormat = "  backcompass" + dataFormat
        elif  _line['FORMAT'][8] == 'd' : dataFormat = "  backclino" + dataFormat
        else : 
            log.error(f"Error in format str 8 code {Colors.ENDC}{_line['FORMAT']}{Colors.ERROR} in {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")
            global_data.error_count += 1
        
        dataFormat = "data normal from to" + dataFormat + " # comment"
        
        with open(str(output_file), "w+", encoding="utf-8") as f:
                        f.write(th_file.format(
                                VERSION = Version,
                                DATE=datetime.now().strftime("%Y.%m.%d-%H:%M:%S"),
                                SURVEY_NAME = sanitize_filename(_line['SURVEY_NAME']),  
                                SURVEY_DATE = _line['SURVEY_DATE'], 
                                SURVEY_TEAM = _line['SURVEY_TEAM'], 
                                FORMAT = _line['FORMAT'], 
                                COMPASS = compass,
                                LENGTH = length, 
                                CLINO = clino,    
                                DATA_FORMAT = dataFormat,
                                CORRECTIONS = _line['CORRECTIONS'], 
                                DATA = formated_Station_List(dfDATA, dataFormat, length, ENTRY_FILE=ENTRY_FILE),
                                COMMENT = sanitize_filename(_line['SURVEY_NAME'] + " " + _line['COMMENT']).replace('"', "'").replace('_', " "),
                                FIX_POINTS = fixPoint,
                                SOURCE = '\n'.join('# ' + line for line in _line['SOURCE'].splitlines()),                    
                                )
                        )
        
        totdata +=f"\tinput Data/{_line['SURVEY_NAME']}/{_line['SURVEY_NAME']}-tot.th\n" 

        log.info(f"Therion file : {Colors.ENDC}{safe_relpath(output_file)}{Colors.GREEN} created from {Colors.ENDC}{os.path.basename(ENTRY_FILE)}")

        ################################################################################################# 
        # Création des dossiers
        ################################################################################################# 
        
        _Config_PATH = CONFIG_PATH + "../../"
        
        createThFolders( ENTRY_FILE = output_file, SCALE = args.scale, UPDATE = args.update, CONFIG_PATH = _Config_PATH,) 
     
        _destination = output_file[:-3] + "\\Sources"
        destination_path = os.path.join(_destination, os.path.basename(output_file))
        shutil.move(output_file, destination_path)      
        
        _destination =  output_file[:-3] + "\\config.thc"
        destination_path = os.path.join(_destination, os.path.basename(output_file))
        # print(f"destination_path : {_destination}")
        os.remove(_destination)
        
        totMapsPlan += f"\tMP-{_line['SURVEY_NAME']}-Plan-tot@{_line['SURVEY_NAME']}\n\tbreak\n"
        totMapsExtended += f"\tMC-{_line['SURVEY_NAME']}-Extended-tot@{_line['SURVEY_NAME']}\n\tbreak\n"


    ################################################################################################# 
    # Gestion des equats 
    #################################################################################################
        
    totdata +=f"\n" 
    
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


        log.info(f"Total 'equats' : {Colors.ENDC}{len(tableau_equate)}{Colors.INFO} in {Colors.ENDC}{safe_relpath(ENTRY_FILE)}")
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
        
    config_vars = {
                    'fileName': SurveyTitle,
                    'cavename': SurveyTitle.replace("_", " "),
                    'Author': Author,
                    'Copyright': Copyright,
                    'Scale' : args.scale,
                    'Target' : "TARGET",
                    'map_comment' : map_comment,
                    'club' : club,
                    'thanksto' : thanksto,
                    'datat' : datat,
                    'wpage' : wpage, 
                    'cs' : crs_wkt,
                    'totData' : totdata,
                    'configPath' : CONFIG_PATH,
                    'other_scraps_plan' : totMapsPlan,
                    'other_scraps_extended' : totMapsExtended,
                    'file_info' : f"# File generated by pyCreateTh.py version {Version} date: {datetime.now().strftime("%Y.%m.%d-%H:%M:%S")}",
            }

    DEST_PATH = os.path.dirname(ENTRY_FILE) + '/' +  SurveyTitle

    process_template(DEST_PATH + '/template.thconfig', config_vars, DEST_PATH + '/' +  SurveyTitle + '.thconfig')
    process_template(DEST_PATH + '/template-tot.th', config_vars, DEST_PATH + '/' + SurveyTitle + '-tot.th')
    process_template(DEST_PATH + '/template-maps.th', config_vars, DEST_PATH + '/' +  SurveyTitle + '-maps.th')
    process_template(DEST_PATH + '/template-readme.md', config_vars, DEST_PATH + '/readme.md')
        
    stationList["Survey_Name_02"] = SurveyTitle

    
    return stationList, SurveyTitle

  
#################################################################################################
#  main function                                                                                #
#################################################################################################
if __name__ == u'__main__':	
    
    start_time  = datetime.now()
    
    #################################################################################################
    # Parse arguments                                                                               #
    #################################################################################################
    parser = argparse.ArgumentParser(
        description=f"{Colors.HEADER}Create a skeleton folder and th, th2 files with scraps from *.mak, *.dat, *.th Therion files, version: {Colors.ENDC}{Version}\n",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.print_help = colored_help.__get__(parser)
    parser.add_argument("--survey_file", help="The survey file (*.th, *.mak, *.dat,) to perform e.g. './Therion_file.th'", default="")
    parser.add_argument("--survey_name", help="Scrap name (if different from 'survey_file' name)", default="None")
    #parser.add_argument("--proj", choices=['plan', 'elevation', 'extended', 'none'], help="The scrap projection to produce", default="plan")
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
        args.survey_file = select_file()
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
        createThFolders(
            ENTRY_FILE = abspath(args.survey_file), 
            TARGET = args.survey_name, 
            SCALE = args.scale, 
            UPDATE = args.update,
            CONFIG_PATH = "")
        
    elif args.survey_file[-3:].lower() == "mak" :
        makToThFile(abspath(args.survey_file))    
        
    elif args.survey_file[-3:].lower() == "dat" :
        _ConfigPath = "./"
        datToThFiles (abspath(args.survey_file), fixPoints = [], crs_wkt = "", CONFIG_PATH = _ConfigPath)
        
    else :
        log.error(f"file {Colors.ENDC}{safe_relpath(args.survey_file)}{Colors.ERROR} not yet supported")
        global_data.error_count += 1

    duration = (datetime.now() - start_time).total_seconds()
    
    if global_data.error_count == 0 :
        
        log.info(f"All files processed successfully in {Colors.ENDC}{duration:.2f}{Colors.INFO} secondes, without errors")
    else :
        log.error(f"There were {Colors.ENDC}{global_data.error_count}{Colors.ERROR} errors during {Colors.ENDC}{duration:.2f}{Colors.ERROR} secondes, check the log file {Colors.ENDC}{safe_relpath(output_log)}")


    
        
    