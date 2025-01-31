
"""
#############################################################################################
#                                                                                       	#  
#     Script pour automatiser la création des dossiers et fichiers pour un fichier .th      #
#                                                                                       	#
#                     By Alexandre PONT  (alexandre_pont@yahoo.fr)                         	#
#                                                                                          	#
# Définir les différentes variables dans fichier config.ini                                 #
# Création des dossiers nécessaires d'après dossier 'template'                              #
# Création des fichiers nécessaires : th, th2, -tot.th                                      #
# Création des scrap avec stations topo                                                     #
#                                                                                           #
# usage : python pyCreate_th2.py                                                            #
#                                                        	                                #
#############################################################################################

Creation Alex the 2024 12 16 :
        Thank's too         
        - Tanguy Racine for the script             https://github.com/tr1813
        - Xavier Robert for the main principes     https://github.com/robertxa
        - Benoit Urruty                            https://github.com/BenoitURRUTY
"""

Version ="2025.01.02"  

#################################################################################################
#################################################################################################



import os
from os.path import isfile, join, abspath
import sys
import re
import unicodedata
import argparse
import shutil
from datetime import datetime
import configparser
import tkinter as tk
from tkinter import filedialog

from helpers.survey import SurveyLoader, NoSurveysFoundException
from helpers.therion import compile_template, Colors, compile_file

#################################################################################################

## [Survey_Data]  default values
Author = "Created by pyCreate_th2.py"
Copyright = "# Copyright (C) pyCreate_th2.py"
Copyright_Short = "Licence (C) pyCreate_th2.py"
map_comment = "Created by pyCreate_th2.py"
cs = "UTM30"
club = "Therion"
thanksto = "Therion"
datat = "https://therion.speleo.sk/"
wpage = "https://therion.speleo.sk/"

## [Application_data] default values
template_path = "./template"
station_by_scrap = 20
final_therion_exe = True
therion_path = "C:\Therion\therion.exe"
LINES = -1
NAMES = -1




#################################################################################################
# # Codes de couleur ANSI
# class Colors:
#     BLACK = '\033[90m'
#     RED = '\033[91m'
#     GREEN = '\033[92m'
#     YELLOW = '\033[93m'
#     BLUE = '\033[94m'
#     MAGENTA = '\033[95m'
#     CYAN = '\033[96m'
#     WHITE = '\033[97m'
    
#     ERROR = '\033[91m'
#     WARNING = '\033[95m'
#     HEADER = '\033[96m'
   
#     ENDC = '\033[0m'
#     BOLD = '\033[1m'
#     UNDERLINE = '\033[4m'



#################################################################################################
def sanitize_filename(th_name):
    """
    Cleans a string to make it compatible with filenames on Windows, Linux, and macOS.
    Replaces special and accented characters with compatible characters.
    
    Args:
        th_name (str): The filename to clean.
    
    Returns:
        str: The cleaned and compatible string.
    """
    # Unicode normalization to replace accented characters with their non-accented equivalents
    th_name = unicodedata.normalize('NFKD', th_name).encode('ASCII', 'ignore').decode('ASCII')
    
    # Replace illegal characters with an underscore (_)
    th_name = re.sub(r'[<>:"/\\|?*\']', '_', th_name)   # Characters not allowed on Windows
    th_name = re.sub(r'[\s]', '_', th_name)             # Replace spaces with underscores
    th_name = re.sub(r'[^a-zA-Z0-9._-]', '_', th_name)  # Keep letters, digits, . _ -
    
    # Ensure the name is not empty or just underscores
    return th_name.strip('_') or "default_filename"




#################################################################################################
def colored_help(parser):
    # Captures the help output
    help_text = parser.format_help()
    
    # Coloration des différentes parties
    colored_help_text = help_text.replace(
        'usage:', f'{Colors.ERROR}usage:{Colors.ENDC}'
    ).replace(
        'options:', f'{Colors.GREEN}options:{Colors.ENDC}'
    ).replace('positional arguments:', f'{Colors.BLUE}positional arguments:{Colors.ENDC}')
    
    # Surligner les arguments
    for action in parser._actions:
        if action.option_strings:
            # Colorer les options (--xyz)
            for opt in action.option_strings:
                colored_help_text = colored_help_text.replace(opt, f'{Colors.BLUE}{opt}{Colors.ENDC}')
    
    # Imprimer le texte coloré
    print(colored_help_text)
    sys.exit(0)

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
            print(f"{Colors.GREEN}The folder '{Colors.GREEN}{template_path}{Colors.ENDC}' has been copied to '{Colors.ENDC}{destination_path}{Colors.GREEN}'{Colors.ENDC}")
        else:
            print(f"{Colors.WARNING}Warning: The folder '{Colors.ENDC}{destination_path}{Colors.WARNING}' already exists. No files were copied.{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.ERROR}Copy template error: {Colors.ENDC}{e}")
        exit(1)    
        
#################################################################################################        
def add_copyright_header(file_path, copyright_text):
    # Lire le contenu du fichier
    with open(file_path, 'r') as file:
        content = file.readlines()
    
    # Vérifier si le copyright est déjà présent
    if not any("copyright" in line.lower() for line in content):
        # Ajouter le copyright en en-tête
        content.insert(0, f"{copyright_text}\n")
        
        # Réécrire le fichier avec le copyright ajouté
        with open(file_path, 'w') as file:
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
        
        # print(f"{Colors.GREEN}File '{Colors.ENDC}{th_file}{Colors.GREEN}' has been copied to '{Colors.ENDC}{destination_path}{Colors.GREEN}' with the copyright header added.{Colors.ENDC}")
    else:
        print(f"{Colors.ERROR}Error: The file .th does not exist {Colors.ENDC}{th_file}")
    


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
        
        print(f"{Colors.GREEN}Update template successfully: {Colors.ENDC}{output_path}")
        
        # Delete the original template file
        os.remove(template_path)
    
    except FileNotFoundError:
        print(f"{Colors.WARNING}Warning: Template file {Colors.ENDC}{template_path}{Colors.WARNING} not found.{Colors.ENDC}")
    except PermissionError:
        print(f"{Colors.ERROR}Error: Insufficient permissions to write the file.{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.ERROR}An error occurred: {Colors.ENDC}{e}")


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
        print(f"{Colors.WARNING}Warning: File {Colors.ENDC}{file_path}{Colors.WARNING} not found.{Colors.ENDC}")
    except PermissionError:
        print(f"{Colors.ERROR}Error: Insufficient permissions to read {Colors.ENDC}{file_path}")
    except Exception as e:
        print(f"{Colors.ERROR}An error occurred: {Colors.ENDC}{e}")
    
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
    # Afficher la boîte de dialogue de sélection de fichier
    file_path = filedialog.askopenfilename(title="Sélectionnez un fichier")
    # Retourner le chemin complet du fichier sélectionné
    return file_path



#################################################################################################
#################################################################################################
if __name__ == u'__main__':	
    
    # Parse arguments
    parser = argparse.ArgumentParser(
        description=f"{Colors.HEADER}Create a skeleton folder and th2 files with scraps from a .th Therion file\nVersion: {Colors.ENDC}{Version}\n",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.print_help = colored_help.__get__(parser)
    parser.add_argument("--survey_file", help="The survey file (*.th) to perform e.g. './Therion_file.th'", default="")
    parser.add_argument("--survey_name", help="Scrap name (if different from 'survey_file' name)", default="None")
    #parser.add_argument("--proj", choices=['plan', 'elevation', 'extended', 'none'], help="The scrap projection to produce", default="plan")
    #parser.add_argument("--format", choices=['th2', 'plt'], help="Output format. Either th2 for producing skeleton for drawing or plt for visualizing in aven/loch", default="th2")
    parser.add_argument("--output", default="./", help="Output folder path")
    # parser.add_argument("--therion-path", help="Path to therion binary", default="therion")
    parser.add_argument("--scale", help="Scale for the exports", default="500")
    parser.add_argument("--lines", type=str_to_bool, help="Shot lines in th2 files", default=-1)
    parser.add_argument("--names", type=str_to_bool, help="Stations names in th2 files", default=-1)
                        
    parser.epilog = (
        f"{Colors.GREEN}Please, complete {Colors.RED}config.ini{Colors.GREEN} file for personal configuration{Colors.ENDC}\n"
        f"{Colors.GREEN}If no argument :{Colors.RED} files selection windows\n{Colors.ENDC}\n"
        f"{Colors.BLUE}Examples:{Colors.ENDC}\n"
        f"\t> python pyCreate_th2.py ./test/Entree.th --survey_name Geophysicaya_01_entree --output ./test/  --scale 1000\n"
        f"\t> python pyCreate_th2.py Entree.th\n"
        f"\t> python pyCreate_th2.py\n\n")
    args = parser.parse_args()

    print("args.survey_file : " + args.survey_file )
    if args.survey_file == "":
        args.survey_file = select_file()
        print(f"Fichier sélectionné : {args.survey_file}")
        

    ENTRY_FILE = abspath(args.survey_file)
    # PROJECTION = args.proj.capitalize()
    PROJECTION = "Plan"
    TARGET = args.survey_name
    OUTPUT = args.output
    #FORMAT = args.format
    FORMAT = "th2"
    SCALE = args.scale
    LINES = args.lines
    NAMES = args.names
    # TH_NAME = args.survey_file.split("/")[-1].strip(".th")
    TH_NAME = sanitize_filename(os.path.splitext(os.path.basename(args.survey_file))[0])
    DEST_PATH = os.path.dirname(args.survey_file) + "/" + TH_NAME
    #DEST_PATH = args.output + TH_NAME.split("/")[-1].strip(".th")
    #ABS_PATH = ENTRY_FILE.strip(args.survey_file)
    ABS_PATH = os.path.dirname(ENTRY_FILE)
    
    # print("args.survey_file : " + args.survey_file )
    # print("ENTRY_FILE: " + ENTRY_FILE ) 
    # print("PROJECTION: " + PROJECTION ) 
    # print("TARGET: " + TARGET ) 
    # print("OUTPUT: " + OUTPUT ) 
    # print("FORMAT: " + FORMAT )     
    # print("SCALE: " + SCALE )
    # print("TH_NAME: " + TH_NAME )
    # print("DEST_PATH: " + DEST_PATH )
    # print("ABS_PATH: " + ABS_PATH )  
    
    try:
        # Load the 'database' section from the configuration file
        read_config("config.ini")
        # print("Auteur: " + Author)
        # print(f"Copyright: \n{Copyright}")

    except ValueError as e:
        # Handle errors if the section is missing
        print(f"{Colors.ERROR}Error: read_config:{Colors.ERROR}", e)
    
    if PROJECTION.lower() != "plan" :
        print(f"{Colors.ERROR}Error: Sorry, projection '{Colors.ENDC}{PROJECTION}{Colors.ERROR}' not yet implemented{Colors.ENDC}")
        exit(1)
    
    if not os.path.isfile(ENTRY_FILE):
        print(f"{Colors.ERROR}Error: The Therion file didn't exist: {Colors.ENDC} {ENTRY_FILE}")
        exit(1)

    if FORMAT not in ["th2", "plt"]:
        print(f"{Colors.ERROR}Error: Please choose a supported format: th2, plt{Colors.ENDC}")
        exit(1)

    # Normalise name, namespace, key, file path
    print(f"{Colors.GREEN}Parsing survey entry file:\t{Colors.ENDC} {args.survey_file}")
    
    survey_list = parse_therion_surveys(ENTRY_FILE)
    # print(survey_list)
    
    if TARGET == "None" :
        if len(survey_list) > 1 : 
            print(f"{Colors.ERROR}Error: Multiple surveys were found, not yet implemented{Colors.ENDC}")
            exit(1)  
    
    TARGET = sanitize_filename(survey_list[0])
    
    print(f"{Colors.GREEN}Parsing survey target:    \t{Colors.ENDC} {TARGET}")        
    
    loader = SurveyLoader(ENTRY_FILE)
    survey = loader.get_survey_by_id(survey_list[0])

    # print(survey.name)
    
    if not survey:
        raise NoSurveysFoundException(f"{Colors.ERROR}Error: No survey found with that selector{Colors.ENDC}")
 
    
    
    
#################################################################################################
    # Copy template folders
    # print(f"{Colors.GREEN}Copy template folder and adapte it{Colors.ENDC}")
    copy_template_if_not_exists(template_path, DEST_PATH)
    copy_file_with_copyright(ENTRY_FILE, DEST_PATH + "/Data", Copyright)
    
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
        'other_scraps_plan' : "",
        'file_info' : f'# File generated by pyCreate_th2.py (version {Version}) date: {datetime.now().strftime("%Y.%m.%d %H:%M:%S")}',
    }
    
    process_template(DEST_PATH + '/template.thconfig', config_vars, DEST_PATH + '/' +  TH_NAME + '.thconfig')
    process_template(DEST_PATH + '/template-tot.th', config_vars, DEST_PATH + '/' +  TH_NAME + '-tot.th')
    process_template(DEST_PATH + '/template-readme.md', config_vars, DEST_PATH + '/readme.md')
                
     
  #################################################################################################      
    # Produce the parsable XVI file
    print(f"{Colors.GREEN}Compiling 2D XVI file:      \t{Colors.ENDC} {TH_NAME}")
    
    template = """source "{th_file}"
    layout minimal
    scale 1 {scale}
    endlayout

    select {selector}

    export model -o "{th_name}.lox"
    export map -projection plan -o "{th_name}-Plan.xvi" -layout minimal -layout-debug station-names
    export map -projection extended -o "{th_name}-Extended.xvi" -layout minimal -layout-debug station-names
    """

    template_args = {
        "th_file": DEST_PATH + "/Data/" + TH_NAME + ".th",  
        "selector": survey.therion_id,
        "th_name": DEST_PATH + "/Data/" + TH_NAME, 
        "scale": SCALE,
    }

    log, tmpdir = compile_template(template, template_args, cleanup=False, therion_path=therion_path)
   
    

#################################################################################################
    # Parse the Plan XVI file
    th_name_xvi =  DEST_PATH + "/Data/" + TH_NAME + "-Plan.xvi" 
    print(f"{Colors.GREEN}Parsing plan XVI file:\t{Colors.ENDC}{th_name_xvi}")
    
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
        # print("x_min:", x_min, "x_max:", x_max)
        # print("y_min:", y_min, "y_max:", y_max)
        # print("Écart max-min pour x:", x_ecart)
        # print("Écart max-min pour y:", y_ecart)
        
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
    # shutil.rmtree(tmpdir)

    th2_name = DEST_PATH + "/Data/" + TH_NAME
    output_path = f'{th2_name}-{PROJECTION}.{FORMAT}'
    
    scrap_to_add = int(len(stations)/station_by_scrap)-1

    # print(stations)
    
    print(f"{Colors.GREEN}Writing output to:\t{Colors.ENDC}{output_path}")

    # Write TH2
    if FORMAT == "th2":
        th2_file_header = """encoding  utf-8"""

        th2_file = """
##XTHERION## xth_me_area_adjust {X_Min} {Y_Min} {X_Max} {Y_Max}
##XTHERION## xth_me_area_zoom_to 100
##XTHERION## xth_me_image_insert {insert_XVI} 

{Copyright}
# File generated by pyCreate_th2.py version {version} date: {date}

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
        other_scraps_plan = ""
        
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
            print(f"{Colors.WARNING}Warning: {Colors.ENDC}{os.path.basename(output_path)}{Colors.WARNING} file already exists - nothing done{Colors.ENDC}")

        else :
            name = TARGET, 
            # print(f"{Colors.GREEN}Therion output path :\t{Colors.ENDC}{output_path}")
                 
            with open(str(output_path), "w+") as f:
                f.write(th2_file_header)
                f.write(th2_file.format(
                        name = name[0],
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
                        other_scraps_plan = other_scraps_plan + f"\tbreak\n\tS{PROJECTION[0].upper()}-{name[0]}_{i+2:02}\n"
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
    th_name_xvi =  DEST_PATH + "/Data/" + TH_NAME + "-Extended.xvi" 
    print(f"{Colors.GREEN}Parsing extended XVI file:\t{Colors.ENDC}{th_name_xvi}")
    
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
        # print("x_min:", x_min, "x_max:", x_max)
        # print("y_min:", y_min, "y_max:", y_max)
        # print("Écart max-min pour x:", x_ecart)
        # print("Écart max-min pour y:", y_ecart)
        
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

    th2_name = DEST_PATH + "/Data/" + TH_NAME
    output_path = f'{th2_name}-Extended.{FORMAT}'
    
    print(f"{Colors.GREEN}Writing output to:\t\t{Colors.ENDC}{output_path}")

    # Write TH2
    if FORMAT == "th2":
        th2_file_header = """encoding  utf-8"""

        th2_file = """
##XTHERION## xth_me_area_adjust {X_Min} {Y_Min} {X_Max} {Y_Max}
##XTHERION## xth_me_area_zoom_to 100
##XTHERION## xth_me_image_insert {insert_XVI} 

{Copyright}
# File generated by pyCreate_th2.py version {version} date: {date}

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
        other_scraps_extended = ""
        
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
            print(f"{Colors.WARNING}Warning: {Colors.ENDC}{os.path.basename(output_path)}{Colors.WARNING} file already exists - nothing done{Colors.ENDC}")
        else :
            name = TARGET, 
            # print(f"{Colors.GREEN}Therion output path :\t{Colors.ENDC}{output_path}")
                 
            with open(str(output_path), "w+") as f:
                f.write(th2_file_header)
                f.write(th2_file.format(
                        name = name[0],
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
                        other_scraps_extended = other_scraps_extended + f"\tbreak\n\tSC-{name[0]}_{i+2:02}\n"
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
                    'other_scraps_plan' : other_scraps_plan,
                    'other_scraps_extended' : other_scraps_extended,
                    'file_info' : f"# File generated by pyCreate_th2.py version {Version} date: {datetime.now().strftime("%Y.%m.%d-%H:%M:%S")}",
            }
            
    process_template(DEST_PATH + '/template-maps.th', config_vars, DEST_PATH + '/' +  TH_NAME + '-maps.th')
    
    
if final_therion_exe == True:
    print(f"{Colors.GREEN}Final therion compilation{Colors.ENDC}")
    PATH = os.path.dirname(args.survey_file) + "/" + TH_NAME + "/" + TH_NAME + ".thconfig"
       
    compile_file(PATH, therion_path=therion_path) 








    