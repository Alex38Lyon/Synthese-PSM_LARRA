"""
#############################################################################################
therion.py for pyCreateTh.py                                                           
#############################################################################################
"""

import tempfile, shutil, os, re, logging, threading, subprocess
from os.path import join
import Lib.global_data as global_data
from Lib.general_fonctions import Colors


log = logging.getLogger("Logger")

################################################################################################# 
# Compilation Therion 'Template' (version sans blocage)                                         #
# Compiler une configuration générée dynamiquement à partir d'un template texte.                #
#################################################################################################
def compile_template(template, template_args, totReadMeError = "", **kwargs ):
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
            totReadMeError += f"\tTherion compilation failed with return code: {result.returncode}\n"
            global_data.error_count += 1
            return "Therion error", tmpdir, totReadMeError

        stat = get_stats_from_log(logfile)

        log.info(f"Therion compilation successful, length: {Colors.ENDC}{stat["length"]}m{Colors.INFO}, depth: {Colors.ENDC}{stat["depth"]}m")
        return logfile, tmpdir, totReadMeError

    except subprocess.TimeoutExpired:
        log.error(f"Therion process timed out and was terminated: {Colors.ENDC}{logfile}")
        totReadMeError += f"\tTherion process timed out and was terminated\n"
        global_data.error_count += 1
        return "Therion error", tmpdir, totReadMeError

    except Exception as e:
        log.error(f"Therion template compilation error: {Colors.ENDC}{e}")
        totReadMeError += f"\tTherion template compilation error: {e}\n"
        global_data.error_count += 1
        return "Therion error", tmpdir, totReadMeError

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
    timeout = kwargs.get("timeout", 240)

    log.info(f"Start therion [Therion Compile {Colors.WHITE}{os.path.basename(filename)[:-9]}{Colors.GREEN}], compilation file")

    def run():
        try:
            process = subprocess.Popen(
                [therion_path, filename, "-l", log_file],
                cwd=tmpdir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            def read_output(proc):
                try:
                    for line in proc.stdout:
                        line = line.rstrip()
                        lower_line = line.lower()
                        if "average loop error" in lower_line:
                            None
                            # log.warning(f"[Therion Compile {Colors.WHITE}{os.path.basename(filename)[:-9]}{Colors.WARNING}] {Colors.ENDC}{line}")
                        elif "error" in lower_line:
                            log.error(f"[Therion_Compile {Colors.WHITE}{os.path.basename(filename)[:-9]}{Colors.ERROR}] {Colors.ENDC}{line}")    
                        elif "warning" in lower_line :
                            if not any( msg in line for msg in [
                                    "invalid scrap outline",
                                    "average loop error",
                                    "multiple scrap outer outlines not supported yet"
                                    ]):             
                                log.warning(f"[Therion compile {Colors.WHITE}{os.path.basename(filename)[:-9]}{Colors.WARNING}] {Colors.ENDC}{line}")
                        else:
                            log.debug(f"[Therion compile {Colors.WHITE}{os.path.basename(filename)[:-9]}{Colors.DEBUG}] {Colors.ENDC}{line}")
                except Exception as e:
                    log.warning(f"Reading Therion [Therion_Compile {Colors.WHITE}{os.path.basename(filename)[:-9]}{Colors.WARNING}], output: {Colors.ENDC}{e}")

            output_thread = threading.Thread(target=read_output, args=(process,))
            output_thread.start()

            output_thread.join(timeout)
            if output_thread.is_alive():
                log.error(f"Therion compilation [Therion_Compile {Colors.WHITE}{os.path.basename(filename)[:-9]}{Colors.ERROR}], timed out after {Colors.ENDC}{timeout}{Colors.ERROR} seconds. Killing process...")
                global_data.error_count += 1
                process.kill()

            output_thread.join()  # Toujours attendre proprement
            process.wait()

            if process.returncode != 0:
                log.error(f"Therion [Therion_Compile {Colors.WHITE}{os.path.basename(filename)[:-9]}{Colors.ERROR}], returned error code {Colors.ENDC}{process.returncode}")
                global_data.error_count += 1
            else:
                # stat = get_stats_from_log(log_file)
                log.info(f"Therion file: [Therion Compile {Colors.WHITE}{os.path.basename(filename)[:-9]}{Colors.GREEN}], compilation succeeded")

        except Exception as e:
            log.error(f"Therion file: [Therion Compile {Colors.WHITE}{os.path.basename(filename)[:-9]}{Colors.ERROR}], compilation error: {Colors.ENDC}{e}")
            global_data.error_count += 1

    # Lancer le thread principal pour cette compilation et le retourner
    thread = threading.Thread(target=run)
    
    thread.start()
    
    return thread


#################################################################################################
def compile_file_th(filepath, **kwargs):
    template = """source {filepath}
        layout test
        scale 1 100
    endlayout
    """
    template_args = {"filepath": filepath}
    logs, _, = compile_template(template, template_args, cleanup=True, **kwargs)
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