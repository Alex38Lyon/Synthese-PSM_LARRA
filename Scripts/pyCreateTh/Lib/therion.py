"""
#############################################################################################
therion.py for pyCreateTh.py                                                           
#############################################################################################
"""

import tempfile
import shutil
import os
from os.path import join
import subprocess
import re
import logging
import threading
import Lib.global_data as global_data

log = logging.getLogger("Logger")

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
# Compilation Therion 'Template' (version avec blocage)                                         #
#################################################################################################
def compile_templateOld(template, template_args, **kwargs):
    
    try :
        logfile = ""
        tmpdir = tempfile.mkdtemp()
        config = template.format(**template_args, tmpdir=tmpdir.replace("\\", "/"))
        
        log.debug(f"{config}\n")
        
        config_file = join(tmpdir, "config.thconfig")
        log_file = join(tmpdir, "log.log")
        therion_path = kwargs["therion_path"] if "therion_path" in kwargs else "therion"
        with open(config_file, mode="w+", encoding="utf-8") as tmp:
            with open(log_file, mode="w+") as tmp2:
                tmp.write(config)
                tmp.flush()
                subprocess.check_output('''"{}" "{}" -l "{}"'''.format(therion_path, config_file, log_file), shell=True, )
                tmp2.flush()
                logfile = tmp2.read()
        if kwargs["cleanup"]:
            shutil.rmtree(tmpdir)
        log.debug("\n" )
        return logfile, tmpdir
    
    except Exception as e:
        log.error(f"Therion template compilation error: {Colors.ENDC}{e}")
        global_data.error_count += 1
  
################################################################################################# 
# Compilation Therion 'Template' (version sans blocage)                                         #
# Compiler une configuration générée dynamiquement à partir d'un template texte.                #
#################################################################################################
def compile_template(template, template_args, **kwargs):
    logfile = ""
    tmpdir = None
    try:
        tmpdir = tempfile.mkdtemp()
        config = template.format(**template_args, tmpdir=tmpdir.replace("\\", "/"))

        log.debug(f"{config}\n")

        config_file = join(tmpdir, "config.thconfig")
        log_file = join(tmpdir, "log.log")

        therion_path = kwargs.get("therion_path", "therion")

        with open(config_file, "w", encoding="utf-8") as tmp:
            tmp.write(config)
            tmp.flush()

        # Exécution de Therion
        result = subprocess.run(
            [therion_path, config_file, "-l", log_file],
            stdin=subprocess.DEVNULL,  # Évite toute attente d'entrée clavier
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=kwargs.get("timeout", 30),
            errors="replace"
        )

        # Lecture du fichier log
        try:
            with open(log_file, "r", encoding="cp1252", errors="replace") as f:
                logfile = f.read()
        except Exception as log_err:
            log.warning(f"Could not read Therion log: {Colors.ENDC}{log_err}")

        # Analyse du code retour
        if result.returncode != 0 or "press any key" in result.stdout.lower():
            log.error(f"Therion compilation failed with return code: {Colors.ENDC}{result.returncode}\n{Colors.WHITE}{result.stdout}")
            global_data.error_count += 1
            return "Therion error", tmpdir

        stat = get_stats_from_log(logfile)

        log.info(f"Therion compilation successful, length: {Colors.ENDC}{stat["length"]}m{Colors.INFO}, depth: {Colors.ENDC}{stat["depth"]}m")
        return logfile, tmpdir

    except subprocess.TimeoutExpired:
        log.error(f"Therion process timed out and was terminated : {Colors.ENDC}{logfile}")
        global_data.error_count += 1
        return "Therion error", tmpdir

    except Exception as e:
        log.error(f"Therion template compilation error: {Colors.ENDC}{e}")
        global_data.error_count += 1
        return "Therion error", tmpdir

    finally:
        if kwargs.get("cleanup", True) and tmpdir:
            try:
                shutil.rmtree(tmpdir)
            except Exception as cleanup_err:
                log.warning(f"Could not delete temp directory: {Colors.ENDC}{cleanup_err}")

             
################################################################################################# 
# Compilation Therion (version sans blocage)                                                    #
#################################################################################################
def compile_file(filename, **kwargs):
    
    tmpdir = os.path.dirname(filename)
    log_file = join(tmpdir, "therion.log").replace("\\", "/")
    therion_path = kwargs.get("therion_path", "therion")
    timeout = kwargs.get("timeout", 60)  # seconds

    log.info(f"Start therion compilation file: {Colors.ENDC}{safe_relpath(filename)}")

    try:
        # Lancement du processus Therion
        process = subprocess.Popen(
            [therion_path, filename, "-l", log_file],
            cwd=tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        # Fonction de lecture en temps réel (dans un thread séparé)
        def read_output(proc):
            try:
                for line in proc.stdout:
                    line = line.rstrip()
                    lower_line = line.lower()
                    if "average loop error" in lower_line:
                        log.warning(f"[Therion_Compile] {Colors.ENDC}{line}")
                    elif "error" in lower_line:
                        log.error(f"[Therion_Compile] {Colors.ENDC}{line}")    
                    elif "warning" in lower_line:
                        log.warning(f"[Therion_Compile] {Colors.ENDC}{line}")
                    else:
                        log.debug(f"[Therion_Compile] {Colors.ENDC}{line}")
            except Exception as e:
                log.warning(f"Reading Therion output: {Colors.ENDC}{e}")

        # Démarrage du thread de lecture
        output_thread = threading.Thread(target=read_output, args=(process,))
        output_thread.start()

        # Attente avec timeout
        output_thread.join(timeout)
        if output_thread.is_alive():
            log.error(f"Therion compilation timed out after {Colors.ENDC}{timeout}{Colors.ERROR} seconds. Killing process...")
            global_data.error_count += 1
            process.kill()
            output_thread.join()

        process.wait()

        # Vérification du code de retour
        if process.returncode != 0:
            log.error(f"Therion returned error code {Colors.ENDC}{process.returncode}")
            global_data.error_count += 1
            
        else:
            log.info(f"Therion file: {Colors.ENDC}{safe_relpath(filename)}{Colors.GREEN} compilation succeeded")

    except Exception as e:
        log.error(f"Therion file: {Colors.ENDC}{safe_relpath(filename)}{Colors.ERROR} compilation error: {Colors.ENDC}{e}")
        global_data.error_count += 1


#################################################################################################
def compile_file_th(filepath, **kwargs):
    template = """source {filepath}
        layout test
        scale 1 100
    endlayout
    """
    template_args = {"filepath": filepath}
    logs, _ = compile_template(template, template_args, cleanup=True, **kwargs)
    return logs

#################################################################################################
# Attention fonctionne pour la version therion en français ! à voir pour les autres langues
lengthre = re.compile(r".*Longueur totale de la topographie = \s*(\S+)m")
depthre = re.compile(r".*Longueur totale verticale =\s*(\S+)m")

def get_stats_from_log(log):
    lenmatch = lengthre.findall(log)
    depmatch = depthre.findall(log)
    if len(lenmatch) == 1 and len(depmatch) == 1:
        return {"length": lenmatch[0], "depth": depmatch[0]}
    return {"length": 0, "depth": 0}


#################################################################################################
syscoord = re.compile(r".*output coordinate system: \s*(\S+)")


def get_syscoord_from_log(log):
    lenmatch = syscoord.findall(log)

    if len(lenmatch) == 1:
        return {"syscoord": lenmatch[0]}
    return {"syscoord": 0}