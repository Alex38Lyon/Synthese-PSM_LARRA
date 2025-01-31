import tempfile
import shutil
import os
from os.path import join
import subprocess
import re

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
        log_file = join(tmpdir, "log.log").replace("\\", "/")
        therion_path = kwargs["therion_path"] if "therion_path" in kwargs else "therion"     
       
        # print(f"{Colors.BLUE}therion_path: {Colors.ENDC}{therion_path}") 
        # print(f"{Colors.BLUE}filename: {Colors.ENDC}{filename}")
        # print(f"{Colors.BLUE}log_file: {Colors.ENDC}{log_file}")
        
        # subprocess.check_output('''"{}" "{}" -l "{}"'''.format(therion_path, filename, log_file), shell=True, )
        result = subprocess.run(
            [therion_path, filename, "-l", log_file],
            stdout=subprocess.PIPE,  # Capture de la sortie standard
            stderr=subprocess.PIPE,  # Capture des erreurs
            shell=True
        )
        
        stdout_with_tabs = "\n".join("\t" + line for line in result.stdout.decode().splitlines())
        
        # Si la commande échoue, result.returncode sera non nul
        if result.returncode != 0:
            # Affichage des erreurs et de la sortie standard
            print(f"{Colors.ERROR}Error during Therion compilation:{Colors.ENDC}")
            print(f"{Colors.WARNING}stdout: {Colors.YELLOW}{stdout_with_tabs}{Colors.ENDC}")
            print(f"{Colors.ERROR}stderr: \n{result.stderr.decode()}{Colors.ENDC}")
        else:
            # Si la commande réussit, affichez la sortie standard
            print(f"{Colors.GREEN}Therion compilation succeeded.\n{Colors.YELLOW}{stdout_with_tabs}{Colors.ENDC}")
        
    except Exception as e:
        print(f"{Colors.ERROR}Error: Therion file {Colors.ENDC}{filename}{Colors.ERROR} compilation error: {Colors.ENDC}{e}")       
        
        
        

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


lengthre = re.compile(r".*Total length of survey legs =\s*(\S+)m")
depthre = re.compile(r".*Vertical range =\s*(\S+)m")

#################################################################################################
def get_stats_from_log(log):
    lenmatch = lengthre.findall(log)
    depmatch = depthre.findall(log)
    if len(lenmatch) == 1 and len(depmatch) == 1:
        return {"length": lenmatch[0], "depth": depmatch[0]}
    return {"length": 0, "depth": 0}
