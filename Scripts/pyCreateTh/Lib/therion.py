"""
#############################################################################################
therion.py for pyCreateTh.py                                                           
#############################################################################################
"""

import tempfile, shutil, os, re, logging, threading, subprocess, time
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
            selector_value = template_args['selector']
            log.error(f"Therion compilation {Colors.ENDC}{selector_value}{Colors.ERROR}, failed with return code: {Colors.ENDC}{result.returncode}\n{Colors.WHITE}{result.stdout}")
            totReadMeError += f"\tTherion compilation {selector_value}, failed with return code: {result.returncode}\n"
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

            last_output_time = time.time()

            def read_output(proc):
                nonlocal last_output_time
                try:
                    for line in iter(proc.stdout.readline, ''):
                        line = line.rstrip()
                        last_output_time = time.time()  # ← reset du timer ici
                        lower_line = line.lower()

                        if "average loop error" in lower_line:
                            continue
                        elif "error" in lower_line:
                            log.error(f"[Therion_Compile {Colors.WHITE}{os.path.basename(filename)[:-9]}{Colors.ERROR}] {Colors.ENDC}{line}")    
                        elif "warning" in lower_line:
                            if not any(msg in line for msg in [
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

            # Boucle de surveillance du timeout
            while output_thread.is_alive():
                output_thread.join(timeout=1)
                if time.time() - last_output_time > timeout:
                    log.error(f"Therion compilation [Therion_Compile {Colors.WHITE}{os.path.basename(filename)[:-9]}{Colors.ERROR}], timed out after {Colors.ENDC}{timeout}{Colors.ERROR} seconds of inactivity. Killing process...")
                    global_data.error_count += 1
                    process.kill()
                    break

            output_thread.join()
            process.wait()

            if process.returncode != 0:
                log.error(f"Therion [Therion_Compile {Colors.WHITE}{os.path.basename(filename)[:-9]}{Colors.ERROR}], returned error code {Colors.ENDC}{process.returncode}")
                global_data.error_count += 1
            else:
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
fr_lengthre = re.compile(r".*Longueur totale de la topographie = \s*(\S+)m")
fr_depthre = re.compile(r".*Longueur totale verticale =\s*(\S+)m")

en_lengthre = re.compile(r".*Total length of survey legs = \s*(\S+)m")
en_depthre = re.compile(r".*Vertical range =\s*(\S+)m")

def get_stats_from_log(log):
    lenmatch = fr_lengthre.findall(log)
    depmatch = fr_depthre.findall(log)
    
    if len(lenmatch) == 0 and len(depmatch) == 0: 
        lenmatch = en_lengthre.findall(log)
        depmatch = en_depthre.findall(log)
    
    if len(lenmatch) == 1 and len(depmatch) == 1:
        return {"length": lenmatch[0], "depth": depmatch[0]}
    
    return {"length": 0.0, "depth": 0.0}


#################################################################################################
syscoord = re.compile(r".*output coordinate system: \s*(\S+)")

def get_syscoord_from_log(log):
    lenmatch = syscoord.findall(log)

    if len(lenmatch) == 1:
        return {"syscoord": lenmatch[0]}
    
    return {"syscoord": 0}