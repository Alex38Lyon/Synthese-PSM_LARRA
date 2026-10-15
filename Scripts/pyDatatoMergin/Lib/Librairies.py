"""
#############################################################################################
Librairies générales pour pyDatatoMergin.py
#############################################################################################
"""

import logging, sys, re, hashlib, os, configparser  # noqa: I001
from pathlib import Path
from parameter_expansion import expand # type: ignore
from Lib import GlobalData

logger = logging.getLogger("Logger")

#################################################################################################
# Couleurs ANSI par niveau de log
#################################################################################################
COLOR_CODES = {
    logging.DEBUG: "\033[94m",  # Bleu
    logging.INFO: "\033[92m",  # Vert
    logging.WARNING: "\033[95m",  # MAGENTA
    logging.ERROR: "\033[91m",  # Rouge
    logging.CRITICAL: "\033[1;91m",  # Rouge vif
}

RESET = "\033[0m"


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
    colored_help_text = (
        help_text.replace("usage:", f"{Colors.ERROR}Usage:{Colors.ENDC}")
        .replace("options:", f"{Colors.GREEN}options:{Colors.ENDC}")
        .replace(", --help", f"{Colors.BLUE}, --help:{Colors.ENDC}")
        .replace("elp:", f"{Colors.BLUE}elp{Colors.ENDC}")
        .replace("show this help message and exit", f"Voir ce message et terminer")
    )

    # Surligner les arguments
    for action in parser._actions:
        if action.option_strings:
            # Colorer les options (--xyz)
            for opt in action.option_strings:
                colored_help_text = (
                    colored_help_text.replace(opt, f"{Colors.BLUE}{opt}{Colors.ENDC}")
                    .replace("--help", f"{Colors.BLUE}--help:{Colors.ENDC}")
                    .replace("python", f"{Colors.BLUE}python{Colors.ENDC}")
                )

    # Imprimer le texte coloré
    print(colored_help_text)
    sys.exit(1)


#################################################################################################
# Codes de couleur ANSI
#################################################################################################
class Colors:
    BLACK = "\033[90m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    TITRE = "\033[30m\033[42m"
    TITRE_2 = "\033[37m\033[42m"

    ERROR = "\033[91m"
    WARNING = "\033[95m"
    HEADER = "\033[96m"
    DEBUG = "\033[94m"  # Bleu
    INFO = "\033[92m"  # Vert
    CRITICAL = "\033[1;91m"  # Rouge vif

    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


#################################################################################################
# Fonction de configuration du logger
#################################################################################################
def setup_logger(logfile="app.log", debug_log=False):
    logger = logging.getLogger("Logger")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    min_level = logging.DEBUG if debug_log else logging.INFO

    class MaxLevelFilter(logging.Filter):
        def __init__(self, max_level):
            super().__init__()
            self.max_level = max_level

        def filter(self, record):
            return record.levelno < self.max_level

    # stdout : DEBUG, INFO et WARNING
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(min_level)
    stdout_handler.addFilter(MaxLevelFilter(logging.ERROR))
    stdout_handler.setFormatter(ConsoleFormatter("%(levelname)s: %(message)s"))
    logger.addHandler(stdout_handler)

    # stderr : ERROR et CRITICAL uniquement
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)
    stderr_handler.setFormatter(ConsoleFormatter("%(levelname)s: %(message)s"))
    logger.addHandler(stderr_handler)

    # Fichier de log
    file_handler = logging.FileHandler(logfile, encoding="utf-8")
    file_handler.setLevel(min_level)
    file_handler.setFormatter(FileFormatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(file_handler)

    return logger


#################################################################################################
class AnsiStrippingStream:
    """Supprime les codes ANSI des sorties en mode non interactif."""

    def __init__(self, stream):
        self.stream = stream

    def write(self, text):
        return self.stream.write(strip_ansi_codes(text))

    def flush(self):
        return self.stream.flush()

    def isatty(self):
        return self.stream.isatty()

    def fileno(self):
        return self.stream.fileno()

    def __getattr__(self, name):
        return getattr(self.stream, name)


INTERACTIF = sys.stdout.isatty() and sys.stderr.isatty() and os.environ.get("TERM", "").lower() != "dumb"

if not INTERACTIF:
    sys.stdout = AnsiStrippingStream(sys.stdout)
    sys.stderr = AnsiStrippingStream(sys.stderr)


#################################################################################################
# Formatter pour la console avec couleurs
#################################################################################################
class ConsoleFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)

        if INTERACTIF:
            color = COLOR_CODES.get(record.levelno, "")
            return f"{color}{message}{RESET}"

        return strip_ansi_codes(message)


#################################################################################################
# Supprime les codes ANSI (pour l'écriture dans les fichiers ou en mode non interactif)
#################################################################################################
def strip_ansi_codes(text):
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


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
            sinfo=record.stack_info,
        )
        return super().format(record_copy)


#################################################################################################
def release_log_file(logger):
    handlers = logger.handlers[:]
    for handler in handlers:
        if isinstance(handler, logging.FileHandler):
            handler.close()
            logger.removeHandler(handler)


################################################################################################
def get_sha256(file_path):
    """Calcule le hash SHA-256 d'un fichier.

    Args:
        file_path (str): Le chemin vers le fichier.

    Returns:
        str: Le hash SHA-256 du fichier.
    """

    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)

    return sha256.hexdigest()

#################################################################################################
def load_config(configIni="config.ini", profile="Default"):
    """
    Charge un fichier de configuration .ini et initialise les variables globales.

    Args:
        configIni: Nom du fichier de configuration.
        profile: Nom du profil Survey_Data à utiliser.
                 Exemple : Survey_Data:PSM
    """

    try:   
        # Chemin potentiel du fichier config
        config_file = Path(__file__).resolve().parent / configIni
        # config_file = os.path.join(os.path.dirname(__file__), configIni)
        if not os.path.isfile(config_file):
            config_file = configIni

        config = configparser.ConfigParser()
        config.read(config_file, encoding="utf-8")

        # ----------------------------------------------------------
        # Sélection du profil Depot_Data
        # ----------------------------------------------------------
        depot_section = f"Depot_Data:{profile}"

        if depot_section in config:
            depot_cfg = config[depot_section]

        elif "Depot_Data" in config:
            # Compatibilité ancienne configuration
            depot_cfg = config["Depot_Data"]

            if profile != "Default":
                logger.warning(f"Profile '{Colors.ENDC}{profile}{Colors.WARNING}' not found. Using legacy default {Colors.ENDC}[Survey_Data]{Colors.WARNING} section.")
                profile = "Default"
        
        else:
            raise ValueError(f"Section [{depot_section}] not found and no legacy [Survey_Data] section available.")

        # ----------------------------------------------------------
        # Lecture Depot_Data
        # ----------------------------------------------------------
        depot_keys = {
            'Dest_project': 'Dest_project',
            'Github_repo': 'Github_repo',
            'Github_path': 'Github_path',
            'Github_branch': 'Github_branch',
            'Dest_folder': 'Dest_folder'
        }

 
        for key, attr in depot_keys.items():
            if key in depot_cfg:
                value = expand(depot_cfg[key])
                setattr(GlobalData, attr, value)

        return config_file

    except (OSError, configparser.Error, ValueError) as e:
        logger.critical(f"Reading config file : {Colors.ENDC}{configIni}{Colors.ERROR} error : {Colors.ENDC}{e}"  )
        sys.exit(0)
