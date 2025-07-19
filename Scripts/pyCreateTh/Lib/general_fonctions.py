"""
#############################################################################################
general_fonctions.py for pyCreateTh.py                                                           
#############################################################################################
"""
import os, logging, sys, re, configparser, unicodedata, shutil
import Lib.global_data as global_data
import tkinter as tk
from tkinter import filedialog

log = logging.getLogger("Logger")

#################################################################################################
# Couleurs ANSI par niveau de log
#################################################################################################
COLOR_CODES = {
    logging.DEBUG: "\033[94m",       # Bleu
    logging.INFO: "\033[92m",        # Vert
    logging.WARNING: "\033[95m",     # MAGENTA
    logging.ERROR: "\033[91m",       # Rouge
    logging.CRITICAL: "\033[1;91m",  # Rouge vif
}
RESET = "\033[0m"

#################################################################################################
# Codes de couleur ANSI
class Colors:
    BLACK = '\033[90m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    
    ERROR = '\033[91m'
    WARNING = '\033[95m'
    HEADER = '\033[96m'
    DEBUG = '\033[94m'          # Bleu
    INFO = '\033[92m'           # Vert
    CRITICAL = '\033[1;91m',    # Rouge vif
   
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


#################################################################################################
def safe_relpath(path):
    abs_path = os.path.abspath(path)
    ref_path = os.path.abspath(os.getcwd())
    
    try:
        valeur = "~\\" +  os.path.relpath(path, ref_path)
        return valeur
    
    except ValueError:
        max_depth = 4  # Profondeur maximale pour tronquer le chemin
        
        # Disques différents, afficher le chemin relatif partiel depuis la racine commune
        path_parts = abs_path.split(os.sep)
        ref_parts = ref_path.split(os.sep)
        while path_parts and ref_parts and path_parts[0] == ref_parts[0]:
            path_parts.pop(0)
            ref_parts.pop(0)
        result = os.path.join(*path_parts) if path_parts else os.path.basename(path)

        # Si max_depth est défini, tronque le chemin
        if max_depth is not None:
            parts = result.split(os.sep)
            if len(parts) > max_depth:
                result = os.path.join("~\\" , *parts[-max_depth:])
        
        return result


#################################################################################################
# Coloration des messages d'aide d'arg                                                          #
#################################################################################################
def colored_help(parser):
    """
    Affiche l'aide colorée pour les arguments de la ligne de commande.

    Args:
        parser (argparse.ArgumentParser): Le parseur d'arguments.
    Returns:
        None
            
    """
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
# Mise au format des noms                                                                       #
#################################################################################################
def sanitize_filename(thName):
    """
    Cleans a string to make it compatible with filenames on Windows, Linux, and macOS.
    Replaces special and accented characters with compatible characters.
    Replaces parentheses with underscores and enforces proper casing.

    Args:
        thName (str): The filename to clean.

    Returns:
        str: The cleaned and compatible string.
        
    """
    # Unicode normalization to replace accented characters with their non-accented equivalents
    thName = unicodedata.normalize('NFKD', thName).encode('ASCII', 'ignore').decode('ASCII')

    # Replace parentheses with underscores
    thName = thName.replace('(', '_').replace(')', '_')

    # Replace illegal characters with an underscore
    thName = re.sub(r'[<>:"/\\|?*\']', '_', thName)   # Illegal on Windows
    thName = re.sub(r'\s+', '_', thName)             # Spaces to underscores
    thName = re.sub(r'[^a-zA-Z0-9._-]', '_', thName) # Keep only allowed chars

    # Convert to lowercase, then capitalize the first letter
    # thName = thName.lower().capitalize()
    # thName = thName.capitalize()
    
    # Suppression des underscores en début et fin
    thName = thName.strip('_')

    return thName or "default_filename"  # Avoid empty result


#################################################################################################
def select_file_tk_window():
    """
    Ouvre une boite de dialogue tkinter pour sélectionner un fichier.

    Returns:
        str: Le chemin complet du fichier sélectionné.
    """
    # Créer une instance de la fenêtre tkinter
    root = tk.Tk()
    
    # Cacher la fenêtre principale
    root.withdraw()
    
    # Afficher la boite de dialogue de sélection de fichier
    file_path = filedialog.askopenfilename(
        title="Select your file",
        filetypes=[ 
                   ("Compatibles files", "*.th *.mak *.dat *.tro"), 
                   ("MAK files", "*.mak"),
                   ("TH files", "*.th"), 
                   ("DAT files", "*.dat"), 
                   ("TRO files", "*.tro"), 
                   ("All files", "*.*")]
        )
    
    
    return file_path  # Retourner le chemin complet du fichier sélectionné


#################################################################################################
def load_config(args, configIni="config.ini"):
    """
    Charge un fichier de configuration .ini et initialise les variables globales.

    Args:
        args: Argument contenant le chemin du fichier principal.
        configIni: Nom du fichier de configuration.
    """
    try:
        # Chemin potentiel du fichier config
        config_file = os.path.join(os.path.dirname(args.file), configIni)
        if not os.path.isfile(config_file):
            config_file = configIni  # Fallback si fichier absent

        config = configparser.ConfigParser()
        config.read(config_file, encoding="utf-8")

        survey_keys = {
            'Author': 'Author',
            'Copyright1': None,
            'Copyright2': None,
            'Copyright3': None,
            'Copyright_Short': 'CopyrightShort',
            'map_comment': 'mapComment',
            'club': 'club',
            'thanksto': 'thanksto',
            'datat': 'datat',
            'wpage': 'wpage',
            'cs': 'cs'
        }

        for key, attr in survey_keys.items():
            if 'Survey_Data' in config and key in config['Survey_Data']:
                if key.startswith('Copyright') and all(
                    k in config['Survey_Data'] for k in ['Copyright1', 'Copyright2', 'Copyright3']
                ):
                    global_data.Copyright = "\n".join([
                        config['Survey_Data']['Copyright1'],
                        config['Survey_Data']['Copyright2'],
                        config['Survey_Data']['Copyright3']
                    ])
                elif attr:
                    setattr(global_data, attr, config['Survey_Data'][key])

        app_keys = {
            'template_path': 'templatePath',
            'station_by_scrap': ('stationByScrap', int),
            'final_therion_exe': ('finalTherionExe', lambda x: x.lower() == 'true'),
            'therion_path': 'therionPath',
            'survey_prefix_name': 'SurveyPrefixName',
            'shot_lines_in_th2_files': ('linesInTh2', lambda x: x.lower() == 'true'),
            'station_name_in_th2_files': ('stationNamesInTh2', lambda x: x.lower() == 'true'),
            'kSmooth': ('kSmooth', float),
        }

        for key, value in app_keys.items():
            if 'Application_Data' in config and key in config['Application_Data']:
                attr, caster = (value, str) if isinstance(value, str) else value
                setattr(global_data, attr, caster(config['Application_Data'][key]))
        
        return config_file

    except Exception as e:
        log.critical(f"Reading {configIni} file error: {Colors.ENDC}{e}")
        exit(0)


#################################################################################################
# Supprime les codes ANSI (pour l'écriture dans les fichiers)
#################################################################################################
def strip_ansi_codes(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


#################################################################################################
# Formatter pour la console avec couleurs
#################################################################################################
class ConsoleFormatter(logging.Formatter):
    def format(self, record):
        color = COLOR_CODES.get(record.levelno, "")
        message = super().format(record)
        return f"{color}{message}{RESET}"


#################################################################################################
# Formatter pour le fichier avec "!!!" sur les erreurs
#################################################################################################
class FileFormatter(logging.Formatter):
    def format(self, record):
        clean_msg = strip_ansi_codes(record.getMessage())
        prefix = "!!! " if record.levelno >= logging.ERROR else ""
        record_copy = logging.LogRecord(
            name=record.name,
            level=record.levelno,
            pathname=record.pathname,
            lineno=record.lineno,
            msg=f"{prefix}{clean_msg}",
            args=(),
            exc_info=record.exc_info,
            func=record.funcName,
            sinfo=record.stack_info
        )
        return super().format(record_copy)
    
    
#################################################################################################
# Fonction de configuration du logger
#################################################################################################
def setup_logger(logfile="app.log", debug_log=False):
    logger = logging.getLogger("Logger")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    
    min_level = logging.DEBUG if debug_log else logging.INFO
    
    # Console stderr handler — affichage à l'écran avec couleurs
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(min_level)
    stderr_formatter = ConsoleFormatter("%(levelname)s: %(message)s")  # <-- Ta classe personnalisée
    stderr_handler.setFormatter(stderr_formatter)
    logger.addHandler(stderr_handler)

    # File handler — fichier de log
    file_handler = logging.FileHandler(logfile, encoding="utf-8")
    file_handler.setLevel(min_level)
    file_formatter = FileFormatter("%(asctime)s - %(levelname)s - %(message)s")  # <-- Ta classe personnalisée
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger


#################################################################################################
def release_log_file(logger):
    handlers = logger.handlers[:]
    for handler in handlers:
        if isinstance(handler, logging.FileHandler):
            handler.close()
            logger.removeHandler(handler)


#################################################################################################
def copy_template_if_not_exists(template_path, destination_path):
    # Check if the destination folder exists
    try:
        if not os.path.exists(destination_path):
            # If the destination folder does not exist, copy the template
            shutil.copytree(template_path, destination_path)  
            log.info(f"The folder {Colors.ENDC}{template_path}{Colors.GREEN} has been copied to {Colors.ENDC}{safe_relpath(destination_path)}{Colors.GREEN}")
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
        
        _destFile = sanitize_filename(os.path.basename(th_file)[:-3]) + ".th"
        # Copier le fichier vers le dossier de destination
        dest_file = os.path.join(destination_path, _destFile)
        shutil.copy(th_file, dest_file)
        
        # Ajouter le copyright dans l'en-tête si nécessaire
        add_copyright_header(dest_file, copyright_text)
        
        log.debug(f"File {Colors.ENDC}{safe_relpath(th_file)}{Colors.GREEN} has been copied to {Colors.ENDC}{safe_relpath(destination_path)}{Colors.GREEN} with the copyright header added.{Colors.ENDC}")
    else:
        log.error(f"The file .th does not exist {Colors.ENDC}{safe_relpath(th_file)}")
        global_Data.error_count += 1
   
        
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
        global_Data.error_count += 1
        
    except PermissionError:
        log.error(f"Insufficient permissions to write the file")
        global_Data.error_count += 1
        
    except Exception as e:
        log.error(f"An error occurred (update_template_files): {Colors.ENDC}{e}")
        global_Data.error_count += 1

