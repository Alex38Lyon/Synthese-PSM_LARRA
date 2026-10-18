"""
#############################################################################################
Librairies générales pour pyDatatoMergin.py
#############################################################################################
"""

import logging, sys, re, hashlib, os, configparser  # noqa: I001
from pathlib import Path
from parameter_expansion import expand  # type: ignore
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
        .replace("options:", f"{Colors.GREEN}Options:{Colors.ENDC}")
        .replace(", --help", f"{Colors.BLUE}, --help:{Colors.ENDC}")
        .replace("elp:", f"{Colors.BLUE}elp{Colors.ENDC}")
        .replace("show this help message and exit", "Voir ce message et terminer")
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
def load_config_old(configIni="config.ini", profile="Default"):
    """
    Charge un fichier de configuration .ini et initialise les variables globales.

    Args:
        configIni: Nom du fichier de configuration.
        profile: Nom du profil Survey_Data à utiliser.
                 Exemple : Depot_Data:ARR
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
                logger.error(
                    f"Projet '{Colors.ENDC}{profile}{Colors.ERROR}' inexistant, utilisation du profil par défaut {Colors.ENDC}[Depot_Data]{Colors.ERROR} section."
                )
                profile = "Default"

        else:
            logger.error(f"Section {Colors.ENDC}[{depot_section}]{Colors.ERROR}, inexistant et aucun profil par défaut {Colors.ENDC}[Depot_Data]{Colors.ERROR}")
            raise ValueError()

        # ----------------------------------------------------------
        # Lecture Depot_Data
        # ----------------------------------------------------------
        depot_keys = {
            "Dest_project": "Dest_project",
            "Github_repo": "Github_repo",
            "Github_path": "Github_path",
            "Github_branch": "Github_branch",
            "Dest_folder": "Dest_folder",
        }

        for key, attr in depot_keys.items():
            if key in depot_cfg:
                value = expand(depot_cfg[key])
                setattr(GlobalData, attr, value)

        return config_file

    except (OSError, configparser.Error, ValueError) as e:
        logger.critical(f"Lecture du fichier: {Colors.ENDC}{configIni}{Colors.CRITICAL} impossible : {Colors.ENDC}{e}")
        sys.exit(0)


def load_config(configIni="config.ini", profile="Default"):
    """
    Charge un fichier de configuration .ini et initialise les variables globales.

    Args:
        configIni: Nom ou chemin du fichier de configuration.
        profile: Profil Depot_Data à utiliser.
                 Exemple : "Default" ou "LAKORA".

    Returns:
        Chemin du fichier de configuration lu.
    """

    try:
        # ----------------------------------------------------------
        # Recherche du fichier config
        # ----------------------------------------------------------
        config_file = Path(__file__).resolve().parent / configIni

        if not config_file.is_file():
            config_file = Path(configIni)

        if not config_file.is_file():
            raise FileNotFoundError(f"Fichier introuvable : {config_file}")

        config = configparser.ConfigParser()
        config.read(config_file, encoding="utf-8")

        # ----------------------------------------------------------
        # Sélection du profil Depot_Data
        # ----------------------------------------------------------
        depot_section = "Depot_Data" if profile == "Default" else f"Depot_Data:{profile}"

        if depot_section in config:
            depot_cfg = config[depot_section]

        elif "Depot_Data" in config:
            depot_cfg = config["Depot_Data"]

            if profile != "Default":
                logger.error(
                    f"Projet '{Colors.ENDC}{profile}{Colors.ERROR}' inexistant, utilisation du profil par défaut {Colors.ENDC}[Depot_Data]{Colors.ERROR}."
                )
                profile = "Default"

        else:
            raise ValueError(f"Section [{depot_section}] inexistante et aucun profil par défaut [Depot_Data].")

        # ----------------------------------------------------------
        # Lecture des paramètres classiques
        # ----------------------------------------------------------
        depot_keys = {"Dest_project": "Dest_project", "Github_repo": "Github_repo", "Github_branch": "Github_branch"}

        for key, attr in depot_keys.items():
            if key in depot_cfg:
                value = expand(depot_cfg[key])
                setattr(GlobalData, attr, value)

        # ----------------------------------------------------------
        # Lecture des paires source / destination
        # ----------------------------------------------------------
        Liste_copie = []

        for key, value in depot_cfg.items():
            if not key.startswith("liste_copie"):
                continue

            # Vérifier le nom Liste_copie suivi d'un numéro
            suffix = key[11:]

            if not suffix.isdigit():
                continue

            # Séparer la source et la destination
            if "|" not in value:
                raise ValueError(f"{key} invalide dans [{depot_section}] : séparateur '|' manquant.")

            source, destination = (part.strip() for part in value.split("|", maxsplit=1))

            if not source or not destination:
                raise ValueError(f"{key} invalide dans [{depot_section}] : source ou destination vide.")

            Liste_copie.append((int(suffix), expand(source), expand(destination)))

        # Trier les paires par numéro
        Liste_copie.sort(key=lambda Liste_copie: Liste_copie[0])

        # Stocker uniquement les couples (source, destination)
        GlobalData.Liste_copie = [(source, destination) for _, source, destination in Liste_copie]

        logger.debug(
            f"{Colors.ENDC}{len(GlobalData.Liste_copie)}{Colors.DEBUG} couple(s) source/destination chargé(s) pour le profil [{Colors.ENDC}{depot_section}{Colors.DEBUG}]."
        )

        return config_file

    except (OSError, configparser.Error, ValueError) as e:
        logger.critical(f"Lecture du fichier {Colors.ENDC}{configIni}{Colors.CRITICAL} impossible : {Colors.ENDC}{e}")
        sys.exit(1)


#################################################################################################
# fonction pour réduire l'affichage des chemins long                                            #
#################################################################################################
def safe_relpath(path, base_dir=Path(__file__).parent, max_depth=4, max_name_len=50, prefix="~"):
    """
    Retourne un chemin lisible et sûr pour affichage (logs / UI).

    - Compatible Windows / Linux / macOS
    - Tronque la profondeur du chemin
    - Tronque le nom de fichier si trop long
    - Ne lève jamais d'exception
    """

    # ── 1. Résolution du chemin ──────────────────────────────────────────────
    try:
        path = Path(path).expanduser().resolve()

    except (OSError, configparser.Error, ValueError):
        return str(path)

    try:
        base = Path(base_dir).expanduser().resolve() if base_dir else Path.cwd().resolve()

    except (OSError, configparser.Error, ValueError):
        base = None

    # ── 2. Nom du fichier / dossier (tronqué) ─────────────────────────────────
    name = path.name or str(path)

    if len(name) > max_name_len:
        stem = path.stem[: max(1, max_name_len - 6)]
        name = f"{stem}...{path.suffix}"

    # ── 3. Construction des parties ──────────────────────────────────────────
    try:
        if base:
            rel = path.relative_to(base)
            parts = list(rel.parts)
        else:
            raise ValueError

    except (OSError, configparser.Error, ValueError):
        parts = list(path.parts)

    # ── 4. Cas path == base  → "." ────────────────────────────────────────────
    if not parts:
        parts = ["."]

    # ── 5. Limitation de profondeur ──────────────────────────────────────────
    if isinstance(max_depth, int) and max_depth > 0 and len(parts) > max_depth:
        parts = parts[-max_depth:]
        parts.insert(0, prefix)

    # ── 6. Remplacement du nom final ──────────────────────────────────────────
    if parts and parts[-1] not in (".", os.sep):
        parts[-1] = name

    # ── 7. Construction finale sûre ──────────────────────────────────────────
    try:
        return os.path.join(*parts)

    except (OSError, configparser.Error, ValueError):
        return name
