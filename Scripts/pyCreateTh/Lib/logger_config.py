"""
#############################################################################################
logger_config.py for pyCreateTh.py                                                           
#############################################################################################
"""
import logging
import sys
import re

#################################################################################################
# Couleurs ANSI par niveau de log
#################################################################################################
COLOR_CODES = {
    logging.DEBUG: "\033[94m",       # Bleu
    logging.INFO: "\033[92m",        # Vert
    logging.WARNING: "\033[95m",
    logging.ERROR: "\033[91m",       # Rouge
    logging.CRITICAL: "\033[1;91m",  # Rouge vif
}
RESET = "\033[0m"

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

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(min_level)
    console_formatter = ConsoleFormatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler
    file_handler = logging.FileHandler(logfile, encoding="utf-8")
    file_handler.setLevel(min_level)
    file_formatter = FileFormatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger
