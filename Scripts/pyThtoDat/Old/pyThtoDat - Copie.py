# -*- coding: utf-8 -*-

"""#####################################################################################################################################
#                                                        	                                                                           #  
#                                     Script pour convertir une database (.sql) produit par Therion                                    #
#                                                 en fichier Compass .dat .mak                                                         #  
#                                         By Alexandre PONT  alexandre.pont@yahoo.fr                                                   #
#                                                                                                                                      #
#                                                                                                                                      #
# Utilisation:                                                                                                                         #
#   Exporter le fichier sql avec Therion, commande dans fichier .thconfig: export database -o Outputs/database.sql                     #
#   Sélectionner le fichier database.sql à calculer dans main (ligne XXXX)                                                             #                                 
#   Résultat : fichiers dat et mak dans le dossier /output                                                                             #
########################################################################################################################################



# Notes de version :
#   Version 2025 01 23
#       - Debug fichier mak et dat
#       - Modification visées exclues ( de X à LP)       
#       - Debug des entrées sans préfix
#       - Box tkinter pour choix fichier
#       
#
#  Création (Septembre 2024)
#    Données Perdues : 
#           - les commentaires, 
#           - les valeurs mesurées dans les unités mesurés (passage en metres, degrés, degrés)
#           - le fichier mak est à finaliser manuellement
#           - manque le système de coordonnées
"""

Version = "2025_01_23"

import sqlite3, sys, os, re
from alive_progress import alive_bar              # https://github.com/rsalmei/alive-progress	
from datetime import datetime
import numpy as np
import pandas as pd
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext
# import matplotlib.pyplot as plt


class RedirectText:
    """Classe pour rediriger les messages de la console vers un widget Tkinter."""
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        """Écrit un message dans le widget et force le défilement."""
        self.text_widget.insert(tk.END, message)
        self.text_widget.see(tk.END)  # Défile automatiquement vers le bas

    def flush(self):
        """Flush est nécessaire pour gérer correctement les flux."""
        pass



"""#####################################################################################################################################
#                              Fonction pour importer un fichier SQL dans une base de données SQLite                                   #
#                                                                                                                                      #
#####################################################################################################################################"""
def Importation_sql_data(fichier_sql, _file):
    """
    Fonction pour importer un fichier SQL dans une base de données SQLite

    Args:
        fichier_sql (_type_): _description_
    """         
         
    global error_count
    
    try:
        # Si la base de données existe, supprimez-la pour forcer l'écriture
        print(f"\033[1;32mPhase 1: Importation de la base de données Therion \033[0m{input_file_name}\033[1;32m dans: \033[0m{_file}")
        if os.path.exists(_file):
            #print("Suppression de la Bd existante: " + _file)
            os.remove(_file)
            
        connection = sqlite3.connect(_file)
        cursor = connection.cursor()
        
        # Lecture du fichier SQL et exécution des commandes
        with open(fichier_sql, 'r') as sql_file:
            sql_script = sql_file.read()
             
        
        # Séparation du script en commandes individuelles
        sql_script = re.sub(r', nan', ', 0', sql_script, flags=re.IGNORECASE)
        commandes = [cmd.strip() + ';\n' for cmd in sql_script.split(';\n') if cmd.strip()]
       

        # Exécution des commandes avec une barre de progression
        with alive_bar(len(commandes), title = "\x1b[32;1m\t Progression\x1b[0m",  length = 20) as bar:
            for commande in commandes:
                cursor.execute(commande)
                connection.commit()
                bar()

        connection.close()
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête importation_sql_data code:\033[0m {e}") 
        error_count  += 1
        sys.exit(1)  # Arrête le programme en cas d'erreur
        
    return

#####################################################################################################################################
#                                    Fonction pour construire le fichier .dat                                                       #
#                                                                                                                                   #
#####################################################################################################################################
def Creation_dat_file(fichier_sql, _file):
    global error_count  
    global prefix
         
    try:      
        conn = sqlite3.connect(fichier_sql)  # Connexion à la base de données SQLite
        cursor = conn.cursor()
        
        print(f"\033[1;32mPhase 2: Écriture des données dans le fichier: \033[0m{_file}") 
        
        output_file_ligne =[]
        flag = "\n"
        comment = "\n"
        discovery ="\n"
        comments = "\n"
        
        SHOT_equates_station(cursor)
        
        List_Ent = sql_fix_ent(cursor)
        
        # print(pd.DataFrame(List_Ent))
        
        results = sql_centerline(cursor) 
        
        for row in results : 
            if (int(row[9] != 0.0) or int(row[10] != 0.0) or int(row[11] != 0.0) ) :
                
                topo_explo = sql_topo_explo(cursor, row[0])
              
                if str(topo_explo[1]) != "None" :
                    comment = "COMMENT: " + str(topo_explo[1][0]) + "(Length : " + str(row[9]) + "m Surface : " + str(row[10]) + "m Duplicate : "+ str(row[11]) +"m)\n"
                else :  
                    comment = "COMMENT: Length : " + str(row[9]) + " Surface : " + str(row[10]) + " Duplicate : "+ str(row[11]) +"\n"                
                
                if str(row[7]) == "None" :                                                
                    discovery = "\n\n"
                else :
                     discovery = "DISCOVERY: " + str(row[7]) + "\n\n"
                    
                output_file_ligne.append(str(row[3]) + "\n")
                output_file_ligne.append("SURVEY NAME: " + str(row[2]) + "\n")
                output_file_ligne.append("SURVEY DATE: " + str(row[5]) + " ")
                output_file_ligne.append(comment)
                if str(topo_explo[0][0]) != "None" :  
                    output_file_ligne.append("SURVEY TEAM:\n" + str(topo_explo[0][0]) + "\n")
                else : 
                    output_file_ligne.append("SURVEY TEAM:\n\n")
                output_file_ligne.append("DECLINATION:    0.00  FORMAT: DMMDUDRLLAaDdNF  CORRECTIONS:  0.00 0.00 0.00  CORRECTIONS2:  0.00 0.00 " + discovery)
                output_file_ligne.append("                FROM                   TO   LENGTH  BEARING      INC     LEFT       UP     DOWN    RIGHT   FLAGS  COMMENTS\n\n")
            
            shot_results = sql_shot(cursor, row[0]) 
            
            for row2 in shot_results : 
                comments = ( "  [ " + str(row2[6]) +
                             "@"    + str(row2[7]) +
                             " "    + str(row2[8]) +
                             " - "  + str(row2[9]) +
                             "@"    + str(row2[10]) + 
                             " "    + str(row2[11]) +
                             " ] " )
                
                if str(row2[5]) is None :
                    flag = comments + "\n"
                elif str(row2[5]) == "srf" :   # Surface
                    flag = "  #|PL#" + comments + "\n"
                elif str(row2[5]) == "dpl" :   # Duplicate
                    flag = "  #|LP#"+ comments + "\n"     # Flag duplicate -> exclusion du Plan et et du dessin (mais pas du calcul)
                elif str(row2[9]) == "." or str(row2[9]) == "-" :   # Splay    
                     flag = "  #|S#" + "\n"
                else :
                     flag = comments + "\n"
                     
                output_file_ligne.append( " ".ljust(20 -len(prefix))
                                        + (stationName(List_Ent, row2[0])).ljust(20 -len(prefix))
                                        + (stationName(List_Ent, row2[1])).ljust(20 -len(prefix))
                                        + str("{:.2f}".format(row2[2])).ljust(9) 
                                        + str("{:.2f}".format(row2[3])).ljust(9)
                                        + str("{:.2f}".format(row2[4])) + "     0.00     0.00     0.00     0.00" + flag )
            output_file_ligne.append("\f\n")
        #output_file_ligne.append("\f\n")
                
            
        # for i in range(9): output_file_ligne.append(titre[i].ljust(90)+"*\n")  
        
        
        
        conn.close()
        
        with open(_file, 'w',  encoding='utf-8') as file:
            file.writelines(output_file_ligne)
                    
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution des requêtes dans Creation_dat_file:\033[0m {e}")
        error_count  += 1  
        
    except FileNotFoundError:
        print(f"\033[91mErreur d'ouverture du fichier: \033[0m{_file} ")
        error_count  += 1  
        
    except Exception as e:
        print(f"\033[91mErreur lors de l'exécution de Creation_dat_file:\033[0m {e}")
        error_count  += 1
        output_file_ligne.append(f"Erreur lors de l'exécution de Creation_dat_file: {e}\n")
        with open(_file, 'w',  encoding='utf-8') as file:
            file.writelines(_file)
       
    return  


#####################################################################################################################################
#                                    Fonction pour construire le fichier .mak                                                       #
#                                                                                                                                   #
#####################################################################################################################################
def Creation_mak_file(fichier_sql, _file, _file_input):
    global error_count  
    global prefix
    
    try:      
        conn = sqlite3.connect(fichier_sql)  # Connexion à la base de données SQLite
        cursor = conn.cursor()
        
        print(f"\033[1;32mPhase 2: Écriture des données dans \033[0m{_file}") 
        
        output_file_ligne =[]
        
        results = sql_fix_ent(cursor) 
        
        List_Ent = sql_fix_ent(cursor)
        
        if len(results) >= 1 :
            output_file_ligne.append("@" + str("{:.3f}".format(results[0][3])) + 
                                     "," + str("{:.3f}".format(results[0][4])) +
                                     "," + str("{:.3f}".format(results[0][5])) +
                                     ",30,1.520;\n")
            output_file_ligne.append("&WGS 1984;\n")
            output_file_ligne.append("!GEvotScxpl;\n\n/\n")            
            # for i in range(9): output_file_ligne.append("/ " + titre[i].ljust(150)+"*\n")
            
            output_file_ligne.append("/\n\n$30;\n&WGS 1984;\n*0.00;\n") 
            output_file_ligne.append("#" + _file_input + ".dat,\n")
            # for row in   results :
            #     output_file_ligne.append(" " + stationName(List_Ent, row[0]) + 
            #                              "[m," + str("{:.3f}".format(row[3])) + 
            #                              "," + str("{:.3f}".format(row[4])) +
            #                              "," + str("{:.3f}".format(row[5])) +
            #                              "]; / " + str(row[1]) + "@" + str(row[6]) + "\n") 
            for i, row in enumerate(results):
                line = " " + stationName(List_Ent, row[0]) + \
                    "[m," + str("{:.3f}".format(row[3])) + \
                    "," + str("{:.3f}".format(row[4])) + \
                    "," + str("{:.3f}".format(row[5]))
    
                # Vérifie si c'est la dernière ligne
                if i == len(results) - 1:
                    line += "]; / " + str(row[1]) + "@" + str(row[6]) + "\n"
                else:
                    line += "], / " + str(row[1]) + "@" + str(row[6]) + "\n"
                
                output_file_ligne.append(line)
            
        else :
            output_file_ligne.append("/ No fix station;\n")
            output_file_ligne.append("&WGS 1984;\n")
            output_file_ligne.append("!GEvotScxpl;\n\n")            
            # for i in range(9): output_file_ligne.append("/ " + titre[i].ljust(150)+"*\n")  
            output_file_ligne.append("/\n*0.00;\n\n") 
            output_file_ligne.append("#" + _file_input + ".dat,\n")
            output_file_ligne.append("/ No fix station;\n") 
        conn.close()
        
        with open(_file, 'w',  encoding='utf-8') as file:
            file.writelines(output_file_ligne)
                    
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution des requêtes dans Creation_mak_file:\033[0m {e}")
        error_count  += 1
        
    except FileNotFoundError:
        print(f"\033[91mErreur d'ouverture du fichier: \033[0m{_file} ")
        error_count  += 1  
        
    except Exception as e:
        print(f"\033[91mErreur lors de l'exécution de Creation_mak_file:\033[0m {e}")
        error_count  += 1
        output_file_ligne.append(f"Erreur lors de l'exécution de Creation_mak_file: {e}\n")
        with open(_file, 'w',  encoding='utf-8') as file:
            file.writelines(_file)
       
    return  




#####################################################################################################################################
#         Fonction pour joindre les equates dans la table des SHOT                                                                  #          #
#####################################################################################################################################
def SHOT_equates_station(_cursor):
    global error_count  
    retour = []
    
    try:
        _cursor.execute(f"""
                        -- Requête recherche des equates --
                        SELECT   
                            -- STATION.ID,
                            -- STATION.NAME,
                            GROUP_CONCAT(STATION.ID) as ID_Group 
                            -- GROUP_CONCAT(STATION.X) as X_Group,
                            -- GROUP_CONCAT(STATION.Y) as Y_Group,
                            -- GROUP_CONCAT(STATION.Z) as Z_Group, 
                            -- COUNT(STATION.X) AS Qte_X, 
                            -- COUNT(STATION.Y) AS Qte_Y, 
                            -- COUNT(STATION.Z) AS Qte_Z
                        FROM STATION 
                        WHERE STATION.NAME <> '.' AND STATION.NAME <> '-'
                        -- INNER JOIN STATION AS STATION_Bis ON STATION.X = STATION_Bis.X AND STATION.Y = STATION_Bis.Y AND STATION.Z = STATION_Bis.Z
                        -- WHERE  STATION.X = STATION_BIS.X
                        GROUP BY STATION.X, STATION.Y, STATION.Z
                        HAVING COUNT(STATION.X)>1 AND COUNT(STATION.Y)>1 AND COUNT(STATION.Y)>1
                    """)    
        equate = _cursor.fetchall()
        
        print(f"\t Jonction de SHOT equates nbre: {len(equate)}")
        for row in equate :
            sous_valeurs = row[0].split(',')
            # print(f": {sous_valeurs[0]} = ", end="")
            for val in range (1, len(sous_valeurs)) :
                # print(f"{sous_valeurs[val]},", end=" ")    
                _cursor.execute(f"SELECT SHOT.ID FROM SHOT WHERE SHOT.FROM_ID = {sous_valeurs[val]}")  
                filtre = _cursor.fetchall()
    
                for row in filtre :  
                    _cursor.execute(f"UPDATE SHOT SET FROM_ID = {sous_valeurs[0]} WHERE ID = {row[0]};")      
                    
                _cursor.execute(f"SELECT SHOT.ID FROM SHOT WHERE SHOT.TO_ID = {sous_valeurs[val]}")  
                filtre = _cursor.fetchall()
    
                for row in filtre :  
                    _cursor.execute(f"UPDATE SHOT SET TO_ID = {sous_valeurs[0]} WHERE ID = {row[0]};")         
        
        return
    
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête (sql_8_equates) code:\033[0m {e}")
        error_count  += 1
        return 

#####################################################################################################################################
#            Requête pour rechercher les ponts fixes et les entrées                                                                 #
#####################################################################################################################################
def sql_fix_ent(_cursor):
    global error_count 
    retour = []

    try:
        _cursor.execute(f"""
                        -- recherche des stations fix et des ent --
                        SELECT   
                            STATION.ID,
                            STATION.NAME,
                            STATION_FLAG.FLAG,
                            STATION.X,
                            STATION.Y,
                            STATION.Z,
                            SURVEY.NAME
                        FROM STATION 
                        JOIN STATION_FLAG ON STATION_FLAG.STATION_ID = STATION.ID
                        JOIN SURVEY ON SURVEY.ID = STATION.SURVEY_ID
                        GROUP BY STATION.X, STATION.Y, STATION.Z
                        """)
        result = _cursor.fetchall()
        
        return result

        
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête (sql_fix_ent):\033[0m {e}")
        error_count  += 1
        return retour


#####################################################################################################################################
#            Requête avec la liste des visées d'une centerlines                                                                     #
#####################################################################################################################################
def sql_shot(_cursor, CenterlineID):
    global error_count 
    retour = []

    try:
        _cursor.execute(f"""
                        -- Liste des shots
                        SELECT
                            SHOT.FROM_ID,
                            SHOT.TO_ID,
                            SHOT.LENGTH * 3.28084 as Length_ft,
                            SHOT.BEARING As AZ,
                            SHOT.GRADIENT As Inc,
                            SHOT_FLAG.FLAG,
                            STATION_FROM.NAME AS FROM_NAME, 
                            FROM_SURVEY.NAME AS FROM_AT,
                            FROM_FLAG.FLAG AS FROM_FLAG,
                            STATION_TO.NAME AS TO_NAME,
                            TO_SURVEY.NAME AS TO_AT,
                            TO_FLAG.FLAG AS TO_FLAG
                        FROM SHOT
                        JOIN CENTRELINE ON SHOT.CENTRELINE_ID = CENTRELINE.ID
                        LEFT JOIN STATION AS STATION_FROM ON STATION_FROM.ID = SHOT.FROM_ID
                        LEFT JOIN STATION_FLAG AS FROM_FLAG ON STATION_FROM.ID = FROM_FLAG.STATION_ID
                        LEFT JOIN SURVEY AS FROM_SURVEY ON FROM_SURVEY.ID = STATION_FROM.SURVEY_ID

                        LEFT JOIN STATION AS STATION_TO ON STATION_TO.ID = SHOT.TO_ID
                        LEFT JOIN STATION_FLAG AS TO_FLAG ON STATION_TO.ID = TO_FLAG.STATION_ID
                        LEFT JOIN SURVEY AS TO_SURVEY ON TO_SURVEY.ID = STATION_TO.SURVEY_ID

                        LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                        WHERE CENTRELINE.ID={CenterlineID}
                        GROUP BY
							SHOT.FROM_ID,
							SHOT.TO_ID,
							SHOT.BEARING,
							SHOT.GRADIENT,
							SHOT_FLAG.FLAG,
							STATION_FROM.NAME,
							FROM_SURVEY.NAME,
							STATION_TO.NAME,
							TO_SURVEY.NAME;
                        """)
        result = _cursor.fetchall()
        
        return result

        
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête (sql_shot):\033[0m {e}")
        error_count  += 1
        return retour


#####################################################################################################################################
#            Requête avec la liste des centerlines                                                                                  #
#####################################################################################################################################
def sql_centerline(_cursor):
    global error_count 
    retour = []

    try:
        _cursor.execute(f"""
                        -- Liste des centerlines
                        SELECT
	                        CENTRELINE.ID As Num,
	                        SURVEY.NAME As SURVEY_NAME,
	                        SURVEY.FULL_NAME As Survey_Full_Name,
	                        SURVEY.TITLE As Survey_Title,
	                        CENTRELINE.TITLE,
                            substr(CENTRELINE.TOPO_DATE, 9, 2) || ' ' || substr(CENTRELINE.TOPO_DATE, 6, 2) || ' ' || substr(CENTRELINE.TOPO_DATE, 1, 4) AS SURVEY_DATE,
	                        Topo_Info.Noms_Prenoms_Topo,
                            substr(CENTRELINE.EXPLO_DATE, 9, 2) || ' ' || substr(CENTRELINE.EXPLO_DATE, 6, 2) || ' ' || substr(CENTRELINE.EXPLO_DATE, 1, 4) AS EXPLO_DATE,
	                        Explo_Info.Noms_Prenoms_Explo,
	                        CENTRELINE.LENGTH,
	                        CENTRELINE.SURFACE_LENGTH,
	                        CENTRELINE.DUPLICATE_LENGTH
                        FROM CENTRELINE
                        JOIN SURVEY On CENTRELINE.SURVEY_ID = SURVEY.ID
                        LEFT JOIN (
	                        SELECT
		                        TOPO.CENTRELINE_ID,
		                        GROUP_CONCAT(CONCAT(PERSON.NAME, ' ', PERSON.SURNAME), ', ') As Noms_Prenoms_Topo
	                        FROM TOPO  
	                        LEFT JOIN PERSON On TOPO.PERSON_ID = PERSON.ID
	                        -- WHERE TOPO.CENTRELINE_ID = 28
                            ) AS Topo_Info ON CENTRELINE.ID = Topo_Info.CENTRELINE_ID
                        LEFT JOIN (
	                        SELECT
		                        EXPLO.CENTRELINE_ID,
		                        GROUP_CONCAT(CONCAT(PERSON.NAME, ' ', PERSON.SURNAME), ', ') As Noms_Prenoms_Explo
	                        FROM EXPLO  
	                        LEFT JOIN PERSON On EXPLO.PERSON_ID = PERSON.ID
	                        -- WHERE TOPO.CENTRELINE_ID = 28
                        ) AS Explo_Info ON CENTRELINE.ID = Explo_Info.CENTRELINE_ID
                        LEFT JOIN PERSON On CENTRELINE.ID = PERSON.ID
                        WHERE CENTRELINE.LENGTH IS NOT 0.0
						ORDER BY SURVEY_DATE ASC
                        """)
        result = _cursor.fetchall()
        
        return result
        
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête (sql_centerline):\033[0m {e}")
        error_count  += 1
        return retour
        
#####################################################################################################################################
#            Requête pour extraire les noms des topographes (1) puis les noms des explorateurs                                                                                #
#####################################################################################################################################
def sql_topo_explo(_cursor, _centerline_ID):
    global error_count 
    retour = []

    try:
        _cursor.execute(f"""
                        -- Requête pour extraire les noms des topographes (1) puis les noms des explorateurs 
                        SELECT 
                            GROUP_CONCAT(PERSON.NAME || ' ' || PERSON.SURNAME, ', ') AS concatenated_names
                        FROM 
                            TOPO
                        JOIN 
                            PERSON
                        ON 
                            TOPO.PERSON_ID = PERSON.ID
                        WHERE 
                            TOPO.CENTRELINE_ID = {_centerline_ID}

                        UNION ALL

                        SELECT 
                            GROUP_CONCAT(PERSON.NAME || ' ' || PERSON.SURNAME, ', ') AS concatenated_names
                        FROM 
                            EXPLO
                        JOIN 
                            PERSON
                        ON 
                            EXPLO.PERSON_ID = PERSON.ID
                        WHERE 
                            EXPLO.CENTRELINE_ID = {_centerline_ID};
                        """)
        result = _cursor.fetchall()
        
        return result
        
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête (sql_topo_explo):\033[0m {e}")
        error_count  += 1
        return retour


        
####################################################################################################################################
#            Retourne le nom de station (avec ou sans le préfix)                                                                   #
####################################################################################################################################
def stationName(listEnt, station):
    global prefix
  
    for ligne in listEnt:
       if ligne[0] == station:
            return ligne[1]
    
    return  ( prefix + str(station) )
        
####################################################################################################################################
#    Lancer la conversion avec les paramètres définis par l'utilisateur                                                            #
####################################################################################################################################
def execute_conversion():
    global input_file_name, prefix, outputs_path

    # Récupération des valeurs de l'interface
    input_file_name = input_file_path_var.get()
    prefix = prefix_var.get()

    # Vérifications
    if not input_file_name:
        messagebox.showerror("Erreur", "Veuillez sélectionner un fichier d'entrée.")
        print(f"\033[91mErreur,Veuillez sélectionner un fichier d'entrée\033[0m")
        return
    
    if not os.path.isfile(input_file_name):
        messagebox.showerror("Erreur", f"Le fichier {input_file_name} est introuvable.")
        print(f"\033[91mErreur, le fichier \033[0m{input_file_name} est introuvable.\033[0m")
        return
    
    
    # Initialisation des chemins et des noms de fichiers
    maintenant = datetime.now()
    
    output_path = Path(os.path.join(os.path.dirname(input_file_name) , os.path.basename(input_file_name)[:-4] + "_Dat\\" ))
    output_file_dat = Path(os.path.join(output_path, os.path.basename(input_file_name)[:-4] + ".dat"))
    output_file_mak = Path(os.path.join(output_path, os.path.basename(input_file_name)[:-4] + ".mak"))
    imported_database = Path(os.path.join(output_path, os.path.basename(input_file_name)[:-4] + "_Dat.db"))
    
    # print("os.path.dirname(input_file_name) : " + os.path.dirname(input_file_name))
    # print("input_file_name : " + input_file_name)
    # print("os.path.basename [:-4]: " + os.path.basename(input_file_name)[:-4])
    # print("outputs_path : " + outputs_path)
    # print("output_file_dat : " + str(output_file_dat))
    # print("output_file_mak : " + str(output_file_mak))
    # print("output_path : " + str(output_path))
    # print("imported_database : " + str(imported_database))
    
    if not os.path.exists(output_path): os.makedirs(output_path)
    
    # Lancement des étapes de conversion
    try:
               
        # Exécution des fonctions de conversion
        Importation_sql_data(input_file_name, imported_database)
        Creation_dat_file(imported_database, output_file_dat)
        Creation_mak_file(imported_database, output_file_mak, os.path.basename(input_file_name)[:-4])

        messagebox.showinfo("Succès", "Conversion terminée avec succès.")
        
    except Exception as e:
        messagebox.showerror("Erreur", f"Une erreur est survenue : {str(e)}")

####################################################################################################################################
#    Ouvre une boite de dialogue pour sélectionner un fichier d'entrée.                                                            #
####################################################################################################################################
def select_file():
    file_path = filedialog.askopenfilename(
        title="Sélectionner un fichier SQL",
        filetypes=(("Fichiers SQL", "*.sql"), ("Tous les fichiers", "*.*"))
    )
    input_file_path_var.set(file_path)

####################################################################################################################################
#    Création de la fenêtre principale                                                                                             #
####################################################################################################################################
root = tk.Tk()
root.title("Conversion fichiers Therion (.SQL) vers Compass .dat/.mak")
root.geometry("500x100")

# Variables pour stocker les entrées utilisateur
input_file_path_var = tk.StringVar()
prefix_var = tk.StringVar(value="[Lonne]")
outputs_path = "./Outputs/"

# Interface utilisateur
frame = tk.Frame(root, padx=10, pady=10)
frame.pack(fill=tk.BOTH, expand=True)

# Champ pour sélectionner le fichier d'entrée
tk.Label(frame, text="Fichier d'entrée :").grid(row=0, column=0, sticky="w", padx=5, pady=5)
tk.Entry(frame, textvariable=input_file_path_var, width=50).grid(row=0, column=1, padx=5, pady=5)
tk.Button(frame, text="Parcourir...", command=select_file).grid(row=0, column=2, padx=5, pady=5)

# Champ pour définir le préfixe
tk.Label(frame, text="Préfixe :").grid(row=1, column=0, sticky="w", padx=5, pady=5)
tk.Entry(frame, textvariable=prefix_var, width=50).grid(row=1, column=1, padx=5, pady=5)

# Bouton pour lancer la conversion
tk.Button(frame, text="Lancer la conversion", command=execute_conversion).grid(row=1, column=2, pady=5)

# Gestion du redimensionnement
frame.columnconfigure(1, weight=1)

# Lancement de la boucle principale
root.mainloop()