"""
#############################################################################################
Librairies générales pour pyDatatoMergin.py
#############################################################################################
"""

import logging, sys, re, hashlib, os  # noqa: I001

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
def setup_loggerOld(logfile="app.log", debug_log=False):
    logger = logging.getLogger("Logger")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    min_level = logging.DEBUG if debug_log else logging.INFO

    # Console stderr handler — couleurs uniquement en mode interactif
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(min_level)
    stderr_formatter = ConsoleFormatter("%(levelname)s: %(message)s")
    stderr_handler.setFormatter(stderr_formatter)
    logger.addHandler(stderr_handler)

    # File handler — fichier de log sans codes ANSI
    file_handler = logging.FileHandler(logfile, encoding="utf-8")
    file_handler.setLevel(min_level)
    file_formatter = FileFormatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger


def setup_logger(logfile="app.log", debug_log=False):
    logger = logging.getLogger("Logger")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    min_level = logging.DEBUG if debug_log else logging.INFO

    # stdout : DEBUG et INFO
    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setLevel(min_level)
    stdout_handler.addFilter(lambda record: record.levelno < logging.WARNING)
    stdout_handler.setFormatter(ConsoleFormatter("%(levelname)s: %(message)s"))
    logger.addHandler(stdout_handler)

    # stderr : WARNING, ERROR et CRITICAL
    stderr_handler = logging.StreamHandler(stream=sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.addFilter(lambda record: record.levelno >= logging.WARNING)
    stderr_handler.setFormatter(ConsoleFormatter("%(levelname)s: %(message)s"))
    logger.addHandler(stderr_handler)

    # Fichier : tous les messages autorisés
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
