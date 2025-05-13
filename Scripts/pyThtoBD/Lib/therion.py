import tempfile
import shutil
import os
from os.path import join
import subprocess
import re
import logging

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
   
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

#################################################################################################
def compile_template(template, template_args, **kwargs):
    try:
        log = ""
        tmpdir = tempfile.mkdtemp()
        config = template.format(**template_args, tmpdir=tmpdir.replace("\\", "/"))
        
        print(f"{Colors.YELLOW}{config}{Colors.ENDC}\n")
        
        config_file = join(tmpdir, "config.thconfig")
        log_file = join(tmpdir, "log.log")
        therion_path = kwargs["therion_path"] if "therion_path" in kwargs else "therion"
        with open(config_file, mode="w+", encoding="utf-8") as tmp:
            with open(log_file, mode="w+") as tmp2:
                tmp.write(config)
                tmp.flush()
                subprocess.check_output('''"{}" "{}" -l "{}"'''.format(therion_path, config_file, log_file), shell=True, )
                tmp2.flush()
                log = tmp2.read()
        if kwargs["cleanup"]:
            shutil.rmtree(tmpdir)
        print("\n" )
        return log, tmpdir
    
        
    except Exception as e:
        print(f"{Colors.ERROR}Error: Therion template compilation error: {Colors.ENDC}{e}")
        
#################################################################################################
def compile_file(filename, **kwargs):
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
        
        log.info(f"Start therion compilation file : {Colors.WHITE}{filename}")
        # Lecture en temps réel        
        for line in process.stdout:
            line = line.rstrip()
            lower_line = line.lower()
            if "error" in lower_line:
                log.error(f"\t\t[Therion_Compile]\t\{line}")
            elif "warning" in lower_line:
                log.warning(f"\t[Therion_Compile]\t{line}")
            else:
                log.debug(f"\t\t[Therion_Compile]\t{Colors.WHITE}{line}")

        process.wait()
        
        # Si la commande échoue, result.returncode sera non nul
        if process.returncode != 0:
            # Affichage des erreurs et de la sortie standard
            log.error(f"Error during Therion compilation, stderr : \n{Colors.MAGENTA}{process.stderr.decode()}")
        
        log.info(f"Therion file : {Colors.WHITE}{filename} {Colors.GREEN}compilation succeeded")
        
    except Exception as e:
            log.error(f"Error: Therion file {Colors.ENDC}{filename}{Colors.ERROR} compilation error: {Colors.ENDC}{e}")       
        
        
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