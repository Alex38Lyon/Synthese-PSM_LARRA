"""
#############################################################################################
general_fonctions.py for pyCreateTh.py                                                           
#############################################################################################
"""
import os, logging, sys, re, configparser
import Lib.global_data as global_data
import tkinter as tk
from tkinter import filedialog

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
    """
    Renvoie un chemin relatif si possible, sinon un chemin partiel à partir du dossier de référence.
    """
    
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
        filetypes=[("MAK files", "*.mak"), ("Compatibles files", "*.th *.mak *.dat"), ("TH files", "*.th"), ("DAT files", "*.dat"), ("All files", "*.*")]
        )
    
    
    return file_path  # Retourner le chemin complet du fichier sélectionné


#################################################################################################
def read_config(config_file):
    """
    Lit le fichier de configuration et initialise les variables globales.

    Args:
        config_file (str): Le chemin vers le fichier de configuration.
        
    Returns:
        None
        
    """

    # Initialize the configparser to read .ini files
    config = configparser.ConfigParser()
    config.read(config_file, encoding="utf-8")

    if 'Survey_Data' in config and 'Author' in config['Survey_Data']:
        global_data.Author = config['Survey_Data']['Author']
    
    if 'Survey_Data' in config and 'Copyright1' in config['Survey_Data']:
        global_data.Copyright = config['Survey_Data']['Copyright1'] + "\n" + config['Survey_Data']['Copyright2'] + "\n" + config['Survey_Data']['Copyright3'] + "\n"
           
    if 'Survey_Data' in config and 'Copyright_Short' in config['Survey_Data']:
        global_data.CopyrightShort = config['Survey_Data']['Copyright_Short']        
        
    if 'Survey_Data' in config and 'map_comment' in config['Survey_Data']:
        global_data.mapComment = config['Survey_Data']['map_comment']
    
    if 'Survey_Data' in config and 'club' in config['Survey_Data']:
        global_data.club = config['Survey_Data']['club']
    
    if 'Survey_Data' in config and 'thanksto' in config['Survey_Data']:
        global_data.thanksto = config['Survey_Data']['thanksto']
    
    if 'Survey_Data' in config and 'datat' in config['Survey_Data']:
        global_data.datat = config['Survey_Data']['datat']
        
    if 'Survey_Data' in config and 'wpage' in config['Survey_Data']:
        global_data.wpage = config['Survey_Data']['wpage']
        
    if 'Survey_Data' in config and 'cs' in config['Survey_Data']:
        global_data.cs = config['Survey_Data']['cs']
        
    if 'Application_Data' in config and 'template_path' in config['Application_Data']:
        global_data.templatePath = config['Application_Data']['template_path']    
        
    if 'Application_Data' in config and 'station_by_scrap' in config['Application_Data']:
        global_data.stationByScrap = int(config['Application_Data']['station_by_scrap'])
    
    if 'Application_Data' in config and 'final_therion_exe' in config['Application_Data']:
        global_data.finalTherionExe = bool(config['Application_Data']['final_therion_exe'])
        
    if 'Application_Data' in config and 'therion_path' in config['Application_Data']:
        global_data.therionPath = config['Application_Data']['therion_path']
        
    if 'Application_Data' in config and 'therion_path' in config['Application_Data']:
        global_data.SurveyPrefixName = config['Application_Data']['survey_prefix_name']
    
    if global_data.linesInTh2 == -1 :    
        if 'Application_Data' in config and 'shot_lines_in_th2_files' in config['Application_Data']:
            global_data.linesInTh2 = 0 if config['Application_Data']['shot_lines_in_th2_files'] == "False" else 1
    
    if global_data.stationNamesInTh2 == -1 :    
        if 'Application_Data' in config and 'station_name_in_th2_files' in config['Application_Data']:
            global_data.stationNamesInTh2 = 0 if config['Application_Data']['station_name_in_th2_files'] == "False" else 1
    
    if global_data.wallLineInTh2 == -1 :    
        if 'Application_Data' in config and 'wall_lines_in_th2_files' in config['Application_Data']:
            global_data.wallLineInTh2 = 0 if config['Application_Data']['wall_lines_in_th2_files'] == "False" else 1


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
