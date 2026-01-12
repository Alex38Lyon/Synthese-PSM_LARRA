"""
!#############################################################################################
#                                                                                            #
#                      general_fonctions.py for  pythStat.py                                 #
#                                                                                            #                           
!#############################################################################################

Alex 2026 01 09

"""
import os, logging, sys, re, unicodedata
from pathlib import Path

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
    HEADER = '\033[1;94m'
    DEBUG = '\033[94m'          # Bleu
    INFO = '\033[92m'           # Vert
    CRITICAL = '\033[1;91m',    # Rouge vif
   
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

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
    # for action in parser._actions:
    #     if action.option_strings:
    #         # Colorer les options (--xyz)
    #         for opt in action.option_strings:
    #             colored_help_text = colored_help_text.replace(opt, f'{Colors.BLUE}{opt}{Colors.ENDC}').replace('--help', f'{Colors.BLUE}--help:{Colors.ENDC}')
    
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
# fonction pour réduire l'affichage des chemins long                                            #
#################################################################################################
def safe_relpath(path, base_dir=None, max_depth=3, max_name_len=50, prefix="~"):
    """
    Retourne un chemin lisible et sûr pour affichage (logs / UI).

    - Compatible Windows / Linux / macOS
    - Tronque la profondeur du chemin
    - Tronque le nom de fichier si trop long
    - Ne lève jamais d'exception
    """

    try:
        path = Path(path).expanduser().resolve()
    except Exception:
        return str(path)

    try:
        base = Path(base_dir).expanduser().resolve() if base_dir else Path.cwd().resolve()
    except Exception:
        base = None

    name = path.name or str(path)
    if len(name) > max_name_len:
        stem = path.stem[: max(1, max_name_len - 6)]
        name = f"{stem}...{path.suffix}"

    try:
        if base:
            rel = path.relative_to(base)
            parts = list(rel.parts)
        else:
            raise ValueError
    except Exception:
        parts = list(path.parts)

    if not parts:
        parts = ["."]

    if isinstance(max_depth, int) and max_depth > 0 and len(parts) > max_depth:
        parts = parts[-max_depth:]
        parts.insert(0, prefix)

    if parts and parts[-1] not in (".", os.sep):
        parts[-1] = name

    try:
        return os.path.join(*parts)
    except Exception:
        return name



 