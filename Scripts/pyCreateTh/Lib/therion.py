import tempfile
import shutil
import os
from os.path import join
import subprocess
import re
import logging
import threading

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
def compile_template(template, template_args, **kwargs):
    global error_count
    
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
        error_count += 1
        

def compile_template2(template, template_args, **kwargs):
    global error_count
    
    logfile = ""
    tmpdir = None
    try:
        tmpdir = tempfile.mkdtemp()
        config = template.format(**template_args, tmpdir=tmpdir.replace("\\", "/"))

        log.debug(f"{config}\n")

        config_file = join(tmpdir, "config.thconfig")
        log_file = join(tmpdir, "log.log")

        therion_path = kwargs.get("therion_path", "therion")

        # Écriture des fichiers config + log
        with open(config_file, "w", encoding="utf-8") as tmp:
            tmp.write(config)
            tmp.flush()

        # Exécution de Therion
        result = subprocess.run(
            [therion_path, config_file, "-l", log_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,           # Décode automatiquement en UTF-8 (avec fallback ci-dessous)
            timeout=kwargs.get("timeout", 60),
            errors="replace"     # Remplace caractères invalides (évite UnicodeDecodeError)
        )

        # Lecture du log (en mode tolérant)
        try:
            with open(log_file, "r", encoding="cp1252", errors="replace") as f:
                logfile = f.read()
        except Exception as log_err:
            log.warning(f"Could not read Therion log: {Colors.ENDC}{log_err}")

        # Analyse du code retour
        if result.returncode != 0:
            log.error(f"Therion compilation failed with return code {Colors.ENDC}{result.returncode} {Colors.ERROR}{result.stdout}")
            error_count += 1
          
        else:
            log.info(f"Therion compilation successful")

        return logfile, tmpdir

    except subprocess.TimeoutExpired:
        log.error(f"Therion process timed out and was terminated")
        error_count += 1
        return "Therion timeout", tmpdir

    except Exception as e:
        log.error(f"Therion template compilation error: {Colors.ENDC}{e}")
        error_count += 1    
        return str(e), tmpdir

    finally:
        if kwargs.get("cleanup", True) and tmpdir:
            try:
                shutil.rmtree(tmpdir)
            except Exception as cleanup_err:
                log.warning(f"Could not delete temp directory: {Colors.ENDC}{cleanup_err}")

        
#################################################################################################
def compile_file(filename, **kwargs):
    global error_count
    
    try:
        tmpdir = os.path.dirname(filename)
        log_file = join(tmpdir, "therion.log").replace("\\", "/")
        therion_path = kwargs["therion_path"] if "therion_path" in kwargs else "therion"     
        
        process = subprocess.Popen(
            [therion_path, filename, "-l", log_file],
            cwd=tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # fusion stdout + stderr
            universal_newlines=True,   # décodage automatique en texte
            bufsize=1                  # ligne par ligne
        )
        
        log.info(f"Start therion compilation file : {Colors.ENDC}~\\{os.path.relpath(filename)}")
        # Lecture en temps réel        
        for line in process.stdout:
            line = line.rstrip()
            lower_line = line.lower()
            if "error" in lower_line:
                log.error(f" [Therion_Compile] {Colors.ENDC}{line}")
            elif "warning" in lower_line:
                log.warning(f" [Therion_Compile] {Colors.ENDC}{line}")
            else:
                log.debug(f" [Therion_Compile] {Colors.ENDC}{line}")

        process.wait()
        
        # Si la commande échoue, result.returncode sera non nul
        if process.returncode != 0:
            # Affichage des erreurs et de la sortie standard
            log.error(f"Error during Therion compilation, stderr : \n{Colors.ENDC}{process.stderr.decode()}")
            error_count += 1
        
        log.info(f"Therion file : {Colors.ENDC}~\\{os.path.relpath(filename)}{Colors.GREEN} succeeded")
        
    except Exception as e:
            log.error(f"Therion file {Colors.ENDC}~\\{os.path.relpath(filename, os.path.expanduser('~'))}{Colors.ERROR} compilation error: {Colors.ENDC}{e}")
            error_count += 1
           
        


def compile_file2(filename, **kwargs):
    global error_count
    
    tmpdir = os.path.dirname(filename)
    log_file = join(tmpdir, "therion.log").replace("\\", "/")
    therion_path = kwargs.get("therion_path", "therion")
    timeout = kwargs.get("timeout", 60)  # seconds

    log.info(f"Start therion compilation file : {Colors.WHITE}{filename}")

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
                    if "error" in lower_line:
                        log.error(f"[Therion_Compile] {Colors.ENDC}{line}")
                    elif "warning" in lower_line:
                        log.warning(f" [Therion_Compile] {Colors.ENDC}{line}")
                    else:
                        log.debug(f" [Therion_Compile] {Colors.ENDC}{line}")
            except Exception as e:
                log.warning(f"Reading Therion output: {Colors.ENDC}{e}")

        # Démarrage du thread de lecture
        output_thread = threading.Thread(target=read_output, args=(process,))
        output_thread.start()

        # Attente avec timeout
        output_thread.join(timeout)
        if output_thread.is_alive():
            log.error(f"Therion compilation timed out after {Colors.ENDC}{timeout}{Colors.ERROR} seconds. Killing process...")
            error_count += 1
            process.kill()
            output_thread.join()

        process.wait()

        # Vérification du code de retour
        if process.returncode != 0:
            log.error(f"Therion returned error code {Colors.ENDC}{process.returncode}")
            error_count += 1
            
        else:
            log.info(f"Therion file : {Colors.ENDC}~\\{os.path.relpath(filename)}{Colors.GREEN} compilation succeeded")

    except Exception as e:
        log.error(f"Therion file {Colors.ENDC}~\\{os.path.relpath(filename)}{Colors.ERROR} compilation error: {Colors.ENDC}{e}")
        error_count += 1



#################################################################################################
def compile_file_th(filepath, **kwargs):
    template = """source {filepath}
        layout test
        scale 1 500
    endlayout
    """
    template_args = {"filepath": filepath}
    logs, _ = compile_template(template, template_args, cleanup=True, **kwargs)
    return logs

#################################################################################################
# Attention fonctionne pour la version therion en français ! à voir pour les autres langues
lengthre = re.compile(r".*Longueur totale de la topographie = \s*(\S+)m")
depthre = re.compile(r".*Longueur totale verticale =\s*(\S+)m")


#################################################################################################
def get_stats_from_log(log):
    lenmatch = lengthre.findall(log)
    depmatch = depthre.findall(log)
    if len(lenmatch) == 1 and len(depmatch) == 1:
        return {"length": lenmatch[0], "depth": depmatch[0]}
    return {"length": 0, "depth": 0}


#################################################################################################
syscoord = re.compile(r".*output coordinate system: \s*(\S+)")


#################################################################################################
def get_syscoord_from_log(log):
    lenmatch = syscoord.findall(log)

    if len(lenmatch) == 1:
        return {"syscoord": lenmatch[0]}
    return {"syscoord": 0}