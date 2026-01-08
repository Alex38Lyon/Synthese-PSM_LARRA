# -*- coding: utf-8 -*-

########################################################################################################################################
#                                                        	                                                                           #  
#                                Script pour calculer les statistiques des entités jonctionnées                                        #
#                                      d'un fichier database (.sql) produit par Therion                                                #  
#                                         By Alexandre PONT  alexandre.pont@yahoo.fr                                                   # 
#                                                                                                                                      #
# Utilisation:                                                                                                                         #
#   Exporter le fichier sql avec therion, commande therion.thconfig : export database -o Outputs/database.sql                          #
#   Commande : python pythStat.py ./chemin/fichier.sql                                                                                 #   
#   ou : python pythStat.py  pour ouvrir une fenêtre                                                                                  #
#   Résultat : fichiers dans le dossier crée du fichier source                                                                         #
########################################################################################################################################


import sqlite3, sys, os, re, argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import filedialog
from alive_progress import alive_bar              # https://github.com/rsalmei/alive-progress	
from datetime import datetime

Version ="2026.01.09"  


"""#####################################################################################################################################
#                              Fonction pour importer un fichier SQL dans une base de données SQLite                                   #
#                                                                                                                                      #
#####################################################################################################################################"""
def importation_sql_data(fichier_sql):
    """
    Fonction pour importer un fichier SQL dans une base de données SQLite

    Args:
        fichier_sql (_type_): _description_
    """         
         
    global error_count
    
    try:
        # Si la base de données existe, supprimez-la pour forcer l'écriture
        print(f"\033[1;32mPhase 1: Importation de la base de données Therion \033[0m{safe_relpath(input_file_name)}\033[1;32m dans: \033[0m{safe_relpath(imported_database)}")
        if os.path.exists(imported_database):
            #print("Suppression de la Bd existante: " + imported_database)
            os.remove(imported_database)
            
        connection = sqlite3.connect(imported_database)
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
#                                    Fonction pour construire les tables JONCTION, SERIE, VISEE_FLAG et RESEAU                      #
#                                                                                                                                   #
#####################################################################################################################################
def construction_tables():
    """
    Fonction pour construire les tables JONCTION, SERIE, VISEE_FLAG et RESEAU
    """     
    global avt_compteur
    global error_count      
    # Principales requêtes
       
    #conn = sqlite3.connect(database)  # Connexion à la base de données SQLite
    #cursor = conn.cursor()
    # print(f"\033[1;32mConstruction des tables dans {imported_database}\033[0m")   
    
    try :   
        print(f"\033[1;32mPhase 2: Création des nouvelles tables, indexation\033[0m") 
        
        cursor.execute("DROP TABLE IF EXISTS JONCTION") # Créer et initialiser une nouvelle table de jonctions 
        cursor.execute("""
            CREATE TABLE JONCTION (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                STATION_ID INTEGER, 
                SERIE_ID INTEGER,
                SERIE_RANG INTEGER,
                SERIE_ENT INTEGER,
                STATION_ENT INTEGER,
                SERIE_JONC INTEGER,
                STATION_JONC INTEGER,
                STATION_TYPE varchar(4),
                ENTREE_ID INTEGER,
                RESEAU_ID INTEGER
                )
            """)
        cursor.execute("select STATION.ID from STATION")
        results = cursor.fetchall()
        Next_Station_ID = cursor.fetchall() # Pour forcer le type
        cursor.executemany("INSERT INTO JONCTION (STATION_ID) VALUES (?)", results) 
        conn.commit()
        
        cursor.execute("DROP TABLE IF EXISTS SERIE")  # Créer et initialiser une nouvelle table des Series 
        cursor.execute("""
            CREATE TABLE SERIE (
                SERIE_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                SERIE_DEP_ID INTEGER,
                STATION_DEP_ID INTEGER,
                SERIE_ARR_ID INTEGER,
                STATION_ARR_ID INTEGER,
                SERIE_NBRE_SHOT INTEGER,
                SERIE_LENGHT REAL,
                SERIE_LENGHT_SURFACE REAL,
                SERIE_LENGHT_DUPLICATE REAL,
                DIRECTION INTEGER,
                STATION_ENT_ID INTEGER,
                RESEAU_ID INTEGER)
            """)
        Current_Serie_ID = cursor.lastrowid
        conn.commit()  
        
        cursor.execute("DROP TABLE IF EXISTS RESEAU")  
        cursor.execute("""
            CREATE TABLE RESEAU (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                RESEAU_ID INTEGER,
                STATION_JONC INTEGER,
                ENT_1 INTEGER,
                ENT_2 INTEGER)
            """)
        conn.commit()      
        
        SHOT_equates_station()
        
        issue_SHOT()   
        duplicate_SHOT()
        
        cursor.execute("DROP TABLE IF EXISTS VISEE_FLAG") # Créer et initialiser une nouvelle table VISEE_FLAG (suivi des visées lues)
        cursor.execute("""
            CREATE TABLE VISEE_FLAG (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                SHOT_ID INTEGER,
                SERIE_ID INTEGER,
                ENTREE_ID INTEGER,
                RESEAU_ID INTEGER,
                SERIE_RANG INTEGER
                )
            """)
        cursor.execute("select SHOT.ID from SHOT")
        results = cursor.fetchall()
        cursor.executemany("INSERT INTO VISEE_FLAG (SHOT_ID) VALUES (?)", results)  # type: ignore
        conn.commit()
        
        print(f"\033[0m\t Création de l'index des tables principales et optimisation de la mémoire\033[0m")
        
        cursor.execute("CREATE INDEX INDEX_JONCTION_STATION_ID ON JONCTION(STATION_ID)")
        cursor.execute("PRAGMA index_list(SHOT)")
        result = cursor.fetchall()
        
        marquage_visee_station_habillage()   
        
        # print(result)
        if len(result)==0 :
            cursor.execute("CREATE INDEX INDEX_SHOT_FROM_ID ON SHOT(FROM_ID)")
            cursor.execute("CREATE INDEX INDEX_SHOT_TO_ID ON SHOT(TO_ID)")
            cursor.execute("CREATE INDEX INDEX_SHOT_FLAG_SHOT_ID ON SHOT_FLAG(SHOT_ID)")
            cursor.execute("CREATE INDEX INDEX_STATION_ID ON STATION(ID)")
            cursor.execute("CREATE INDEX INDEX_VISEE_FLAG_SHOT_ID ON VISEE_FLAG(SHOT_ID)")
            cursor.execute("CREATE INDEX INDEX_STATION_FLAG_STATION_ID ON STATION_FLAG(STATION_ID)")
          
        cursor.execute("VACUUM")
        conn.commit() 
       
    # A partir des entrées, remplir les tables des jonctions et des séries     
        results = sql_liste_entree() 
        print(f"\033[1;32mPhase 3: Remplissage des tables d'après les \033[0m{len(results)}\033[1;32m entrée(s)\033[0m")    # type: ignore
        for row in results:   # type: ignore
            # if row[0]==28548:
            #     print("debug point")
            
            cursor.execute(f"""
                        INSERT INTO SERIE (  
                                SERIE_DEP_ID,
                                STATION_DEP_ID, 
                                SERIE_ARR_ID , 
                                STATION_ARR_ID, 
                                SERIE_NBRE_SHOT, 
                                SERIE_LENGHT,
                                SERIE_LENGHT_SURFACE,
                                SERIE_LENGHT_DUPLICATE,
                                DIRECTION, 
                                STATION_ENT_ID,
                                RESEAU_ID) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (0, row[0], 0, row[0], -1, 0, 0, 0, 0, row[0], 0))
            Current_Serie_ID = cursor.lastrowid 
            
            cursor.execute(f"""
                        UPDATE JONCTION SET  
                                SERIE_ID = ?,
                                SERIE_ENT = ?,
                                STATION_ENT = ?,
                                SERIE_JONC = ?,
                                STATION_JONC = ?,
                                STATION_TYPE = ?,
                                SERIE_RANG = ?,
                                ENTREE_ID = ?,  
                                RESEAU_ID = ?
                        WHERE STATION_ID = ? 
                        """, (Current_Serie_ID, 0, row[0], 0,  0,'ent', 0, row[0], 0, row[0]))
            
            cursor.execute(f"""
                           UPDATE VISEE_FLAG SET 
                                SERIE_ID = {Current_Serie_ID}, 
                                ENTREE_ID = {row[0]},
                                RESEAU_ID = {0}
                            WHERE SHOT_ID = {Current_Serie_ID}
                            """)        
            conn.commit()
            
            # print(f"\tCréation Série: {Current_Serie_ID} depuis la station d'entrée Station_ID: {row[0]}")      
            
            
        # A partir des série vides, itération pour remplir les tables des JONCTION et des SERIE
        print(f"\033[1;32mPhase 4: Remplissage des tables d'après les séries vides jonctionnées aux\033[0m {Current_Serie_ID}\033[1;32m entrée(s)\033[0m")   
    
        results = sql_serie_vides()
        Count = 1
        New_Serie_IDOld = 0
        New_Serie_ID = cursor.lastrowid 
        Current_Station_ID_Old = 0
        Current_Station_ID = 0
        
        cursor.execute("SELECT COUNT(*) AS nbre FROM JONCTION WHERE STATION_TYPE IS NULL")
        _compteur = cursor.fetchall()
        compteur_ttl = int(_compteur[0][0])
        avt_compteur = 0
            
        with alive_bar(compteur_ttl, title = "\x1b[32;1m\t Progression\x1b[0m", length = 20) as bar: 
            while len(results) > 0: # type: ignore
                # print(f"\033[1;32mPhase 4.{Count}: Remplissage des tables JONCTION et SERIE itération: {Count}, séries créée(s): {New_Serie_ID} ajoutée(s): {New_Serie_ID-New_Serie_IDOld} à traiter: {len(results)}\033[0m")            # type: ignore
                bar.text(f"itération: {Count}, série(s) créée(s): {New_Serie_ID}")       # type: ignore
                cursor.execute("SELECT COUNT(*) AS nbre FROM JONCTION WHERE STATION_TYPE IS NULL")
                _compteur = cursor.fetchall()
                compteur = int(_compteur[0][0])
                if  ( compteur_ttl - compteur ) > avt_compteur : 
                        ajout =  compteur_ttl - compteur - avt_compteur 
                        bar(ajout)
                        avt_compteur =  compteur_ttl - compteur
                for row in results:         # type: ignore           
                    # Suivi de la série
                    Current_Serie_ID = int(row[0])
                    Current_Station_ID_Old = int(Current_Station_ID) # type: ignore   
                    Current_Station_ID = int(row[2])
                    Current_Nre_Shot = int(row[5])
                    # Current_Serie_Lenght = 0.0 + float(row[6])
                    # Current_Serie_Lenght_Surface = 0.0 + float(row[7])
                    # Current_Serie_Lenght_Duplicate = 0.0 + float(row[8])
                    Current_Ent = int(row[10])
                    Direction = int(row[9])
                    #print(f"\tSerie courante {Current_Serie_ID}  Station_ID: {Current_Station_ID} results: {results}")
                    Fin_Serie = False
                    while Fin_Serie is False:
                        if Direction == 1 :    
                            Next_Station_ID = sql_station_depart(Current_Station_ID)
                        elif Direction == -1 : 
                            Current_Station_ID = int(row[4])   
                            Next_Station_ID = sql_station_arrivee(Current_Station_ID)           
                        elif Direction == 0 :    
                            Next_Station_ID_1 = sql_station_depart(Current_Station_ID) 
                            Next_Station_ID_2 = sql_station_arrivee(Current_Station_ID)
                            if len(Next_Station_ID_1) == 0 and len(Next_Station_ID_2) == 0: # type: ignore
                                # Entrée sans départ et sans d'arrivée : fin de la série
                                cursor.execute(f"UPDATE SERIE SET SERIE_NBRE_SHOT = 0  WHERE SERIE_ID = {Current_Serie_ID};")
                                cursor.execute(f"UPDATE JONCTION SET SERIE_ENT = -1  WHERE STATION_ID = {Current_Station_ID};")
                                conn.commit()
                                Next_Station_ID = Next_Station_ID_1
                            elif len(Next_Station_ID_1) == 1 and len(Next_Station_ID_2) == 0: # type: ignore
                                # Un départ pas d'arrivée
                                Next_Station_ID = Next_Station_ID_1
                                Direction = 1
                                cursor.execute(f"UPDATE SERIE SET DIRECTION = 1  WHERE SERIE_ID = {Current_Serie_ID};")
                                conn.commit()
                            elif len(Next_Station_ID_1) == 0 and len(Next_Station_ID_2) == 1:  # type: ignore
                                # Une arrivée pas de départ
                                Next_Station_ID = Next_Station_ID_2
                                Direction = -1
                                cursor.execute(f"UPDATE SERIE SET DIRECTION = -1  WHERE SERIE_ID = {Current_Serie_ID};")
                                conn.commit()
                            else :
                                # A gérer nouvelles séries
                                nouvelles_series(Current_Station_ID, Current_Station_ID_Old, Current_Serie_ID, 1, Current_Ent) # type: ignore
                                # print (f"\033[34m\tA traiter création nouvelles séries inverses depuis l'entrée {Current_Station_ID} - {Next_Station_ID_2}, {Next_Station_ID_1}\033[0m")
                                nouvelles_series(Current_Station_ID, Current_Station_ID_Old, Current_Serie_ID, -1, Current_Ent)
                                Direction = 1 
                                Next_Station_ID = Next_Station_ID_1
                                                        
                        if len(Next_Station_ID) == 0 : # type: ignore
                            Next_Station_ID_1 = sql_station_depart(Current_Station_ID) # type: ignore
                            Next_Station_ID_2 = sql_station_arrivee(Current_Station_ID) # type: ignore
                            # print(f"\033[34m\tA gérer, fin de la Série: {Current_Serie_ID} à la Station_ID: {Current_Station_ID} nbre: {Current_Nre_Shot} Next station: {Next_Station_ID}, départs directs {len(Next_Station_ID_1)}, départs inverses {len(Next_Station_ID_2)}\033[0m") # type: ignore
                            # cursor.execute(f"UPDATE SERIE SET SERIE_DEP_ID = {Current_Serie_ID}  WHERE SERIE_ID = {Current_Serie_ID};") # type: ignore
                            # cursor.execute(f"UPDATE SERIE SET STATION_DEP_ID = {Current_Station_ID}  WHERE SERIE_ID = {Current_Serie_ID};") # type: ignore
                            # cursor.execute(f"UPDATE SERIE SET SERIE_NBRE_SHOT = 0  WHERE SERIE_ID = {Current_Serie_ID};") # type: ignore
                            cursor.execute(f"DELETE FROM SERIE WHERE SERIE_ID = {Current_Serie_ID};") 
                            conn.commit() # type: ignore          
                            Fin_Serie = True
                        elif len(Next_Station_ID) == 1 :  # type: ignore
                            suivi_serie(Current_Serie_ID, bar)
                            Fin_Serie = True
                        else : 
                            #print(f"Station_ID {Current_Station_ID} de la Serie {Current_Serie_ID}, départs à gérer: {len(Next_Station_ID)}, Next station: {Next_Station_ID}") # type: ignore
                            suivi_serie(Current_Serie_ID, bar)
                            # Création de X nouvelles séries et mise à jour de la table des jonctions
                            #nouvelles_series(Current_Station_ID, Current_Station_ID_Old, Current_Serie_ID, 1, Current_Ent)
                            Fin_Serie = True
                    # Exécution de la requête SQL       
                resultsOld = results
                results = sql_serie_vides() # type: ignore
                New_Serie_IDOld = New_Serie_ID
                New_Serie_ID = cursor.lastrowid  # type: ignore
                if resultsOld == results :
                        #print(f"Erreur sortie itération qté: {len(resultsOld)} - {resultsOld} - {results}")
                        print(f"\033[91mErreur sortie itération {Count}, séries restantes: {len(resultsOld)} - {results}\033[0m") # type: ignore
                        error_count  += 1
                        break
            
                Count += 1
                
            cursor.execute("SELECT COUNT(*) AS nbre FROM JONCTION WHERE STATION_TYPE IS NULL")
            _compteur = cursor.fetchall()
            compteur = int(_compteur[0][0])
            
            if  ( compteur_ttl ) > avt_compteur : 
                ajout =  compteur_ttl - avt_compteur 
                bar(ajout)
                avt_compteur =  compteur_ttl
                
                         
        orphelines_shot()
        jonction_RESEAU()
        
        if compteur > 0 :            
            print(f"\033[1;32mPhase 4: Fin du remplissage des tables,\033[91m attention \033[0m{compteur}\033[91m station(s) non comptabilisé(s)\033[0m")
            error_count  += 1
        # else :
        #     print(f"\033[1;32mPhase 4: Fin du remplissage des tables voir {imported_database}\033[0m")      
        

    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution d'une des requêtes (construction_tables) code:\033[0m {e}")
        error_count  += 1
    return

#####################################################################################################################################
#         Création des séries entres les visées orphelines -> visées d'une visées entre 2 points marqués                            #
#####################################################################################################################################
def orphelines_shot():
    global error_count     
    
    try:
        
        cursor.execute("""
                        -- Visées orphelines
                        SELECT 
                            VISEE_FLAG.SHOT_ID,
                            VISEE_FLAG.SERIE_ID,
                            VISEE_FLAG.ENTREE_ID,
                            SHOT_FLAG.FLAG,
                            SHOT.FROM_ID,
                            -- STATION_FROM.NAME,
                            JONCTION_FROM.SERIE_ID,
                            JONCTION_FROM.STATION_TYPE,
                            JONCTION_FROM.ENTREE_ID,
                            SHOT.TO_ID,
                            -- STATION_TO.NAME,
                            JONCTION_TO.SERIE_ID,
                            JONCTION_TO.STATION_TYPE,
                            JONCTION_TO.ENTREE_ID,
                            SHOT.LENGTH
                            --sum (SHOT.LENGTH)
                        FROM VISEE_FLAG
                        JOIN SHOT ON SHOT.ID = VISEE_FLAG.SHOT_ID
                        LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                        JOIN STATION AS STATION_FROM ON SHOT.FROM_ID = STATION_FROM.ID
                        JOIN STATION AS STATION_TO ON SHOT.TO_ID = STATION_TO.ID
                        JOIN JONCTION AS JONCTION_FROM ON SHOT.FROM_ID = JONCTION_FROM.ID
                        JOIN JONCTION AS JONCTION_TO ON SHOT.TO_ID = JONCTION_TO.ID
                        WHERE VISEE_FLAG.SERIE_ID is NULL and  JONCTION_TO.SERIE_ID is not null and JONCTION_FROM.SERIE_ID is not null
                    """)
        conn.commit() 
        orphelines = cursor.fetchall()
        
        print(f"\t Intégrations des visées orphelines (entre 2 stations existantes) nbre: {len(orphelines)}")
        
        for row in orphelines:
            _SERIE_LENGHT = 0
            _SERIE_LENGHT_SURFACE = 0
            _SERIE_LENGHT_DUPLICATE = 0
            
            if row[3] == 'dpl':
                _SERIE_LENGHT_DUPLICATE = row[12]
            elif row[3] == 'srf':    
                _SERIE_LENGHT_SURFACE = row[12]
            else :
                _SERIE_LENGHT = row[12]     
                
            cursor.execute(f"""
                INSERT INTO SERIE (  
                        SERIE_DEP_ID,
                        STATION_DEP_ID, 
                        SERIE_ARR_ID , 
                        STATION_ARR_ID, 
                        SERIE_NBRE_SHOT, 
                        SERIE_LENGHT,
                        SERIE_LENGHT_SURFACE,
                        SERIE_LENGHT_DUPLICATE,
                        DIRECTION,
                        STATION_ENT_ID)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", ( row[5], row[4], row[9], row[8], 1, _SERIE_LENGHT, _SERIE_LENGHT_SURFACE, _SERIE_LENGHT_DUPLICATE, 1, row[7] ))
            _Current_Serie_ID = cursor.lastrowid   
            
            cursor.execute(f"""
                           UPDATE VISEE_FLAG SET 
                                SERIE_ID = {_Current_Serie_ID}, 
                                ENTREE_ID = {row[7]},
                                SERIE_RANG  = {1}  
                            WHERE SHOT_ID = {row[0]}
                            """)                
        
            if row[7] != row[11] :
                cursor.execute(f"INSERT INTO RESEAU (STATION_JONC, ENT_1, ENT_2) VALUES (?, ?, ?)", (row[8], row[7], row[11]))  
                # print (f"\033[36m\t Jonction des entrées à la Station_ID: {row[8]} entre: {row[7]} et: {row[11]}\033[0m")
            
            conn.commit()

    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête orphelines_shot code:\033[0m {e}" )
        error_count  += 1
    
    return

#####################################################################################################################################
#         Fonction pour joindre les reseaux                                                                                         #
#####################################################################################################################################
def jonction_RESEAU():
    global error_count     
    
    try:
        cursor.execute("""
                        --Recherche des doublons dans les jonctions réseau
                        SELECT   
                            ID
                            --GROUP_CONCAT(RESEAU.ID) as DUPP_SHOT 
                        FROM RESEAU 
                        GROUP BY RESEAU.ENT_1, RESEAU.ENT_2, RESEAU.STATION_JONC
                        HAVING COUNT(RESEAU.ENT_1)>1 AND COUNT(RESEAU.ENT_2)>1 AND COUNT(RESEAU.STATION_JONC)>1 
                    """)
        conn.commit() 
        doublons = cursor.fetchall()
        
        # print(f"\t Table des RESEAUX doublons nbre: {len(doublons)}")
        for row in doublons : cursor.execute(f"DELETE FROM RESEAU WHERE RESEAU.ID = {row[0]}")  
        conn.commit()   
         
        index_reseau = 0
        
        while True:
            index_reseau += 1         
            cursor.execute("""
                            -- Liste des entrée dans la table RESEAU 
                            SELECT 
                                RESEAU.ENT_1 AS ENT,
                                RESEAU.RESEAU_ID,
                                STATION.NAME,
                                STATION.Z
                            FROM RESEAU 
                            JOIN STATION ON RESEAU.ENT_1 = STATION.ID 
                            WHERE RESEAU.RESEAU_ID IS NULL
                            UNION --ALL
                            SELECT 
                                RESEAU.ENT_2 AS ENT,
                                RESEAU.RESEAU_ID,
                                STATION.NAME,
                                STATION.Z
                            FROM RESEAU
                            JOIN STATION ON RESEAU.ENT_2 = STATION.ID 
                            WHERE RESEAU.RESEAU_ID IS NULL
                            ORDER BY STATION.Z DESC 
                        """)
            conn.commit() 
            entrees = cursor.fetchall()
            
            if len(entrees) == 0:
                break   # Sortie boucle while si plus d'entrées à traiter...
              
            cursor.execute(f"UPDATE RESEAU SET RESEAU_ID = {index_reseau}  WHERE RESEAU.ENT_1 = {entrees[0][0]} ")  
            cursor.execute(f"UPDATE RESEAU SET RESEAU_ID = {index_reseau}  WHERE RESEAU.ENT_2 = {entrees[0][0]} ")     
            conn.commit()
                  
            liste_entrees_reseau = []
            liste_entrees_reseau.append(entrees[0][0])
                        
            nbre_entree_reseau_old= 0
            nbre_entree_reseau=len(liste_entrees_reseau)
                
            while nbre_entree_reseau_old != nbre_entree_reseau : 
                nbre_entree_reseau_old = nbre_entree_reseau
                for row in liste_entrees_reseau :
                    cursor.execute(f"""
                        -- Recherche entrée jonctionnées
                        SELECT RESEAU.ENT_1 FROM RESEAU WHERE RESEAU.ENT_2 = {row} -- AND RESEAU.RESEAU_ID IS NULL
                        UNION 
                        SELECT RESEAU.ENT_2 FROM RESEAU WHERE RESEAU.ENT_1 = {row} -- AND RESEAU.RESEAU_ID IS NULL
                        """)  
                    jonction = cursor.fetchall()
                           
                    for row2 in jonction:  # type: ignore
                        if row2[0] not in liste_entrees_reseau:
                            # print(f"\t Jonction de l'entrée: {row2[0]} au reseau ID: {index_reseau}")
                            cursor.execute(f"UPDATE RESEAU SET RESEAU_ID = {index_reseau}  WHERE RESEAU.ENT_1 = {row2[0]} ")  
                            cursor.execute(f"UPDATE RESEAU SET RESEAU_ID = {index_reseau}  WHERE RESEAU.ENT_2 = {row2[0]} ")
                            liste_entrees_reseau.append(row2[0])  
                    conn.commit()
                nbre_entree_reseau=len(liste_entrees_reseau)
                for row2 in liste_entrees_reseau :   
                    cursor.execute(f"UPDATE JONCTION SET RESEAU_ID = {index_reseau}  WHERE JONCTION.ENTREE_ID = {row2} ")  
                    cursor.execute(f"UPDATE SERIE SET RESEAU_ID = {index_reseau}  WHERE SERIE.STATION_ENT_ID = {row2} ") 
                    cursor.execute(f"UPDATE VISEE_FLAG SET RESEAU_ID = {index_reseau}  WHERE VISEE_FLAG.ENTREE_ID = {row2} ") 
                conn.commit()
        
            print(f"\t Réseau: {index_reseau}, entrées jonctionnées: {len(liste_entrees_reseau)}, {liste_entrees_reseau}")
        
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête Jonction_RESEAU code:\033[0m {e}")
        error_count  += 1
        
    return

#####################################################################################################################################
#         Fonction pour joindre les equates dans la table des SHOT                                                                  #          #
#####################################################################################################################################
def SHOT_equates_station():
    global error_count  
    # Requête 8: recherche des equates
    
    try:
        cursor.execute(f"""
                        -- Requête 8, recherche des equates --
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
                        --WHERE  STATION.X = STATION_BIS.X
                        GROUP BY STATION.X, STATION.Y, STATION.Z
                        HAVING COUNT(STATION.X)>1 AND COUNT(STATION.Y)>1 AND COUNT(STATION.Y)>1
                    """)    
        equate = cursor.fetchall()
        
        print(f"\t Jonction de SHOT equates nbre: {len(equate)}")
        for row in equate :
            sous_valeurs = row[0].split(',')
            # print(f": {sous_valeurs[0]} = ", end="")
            for val in range (1, len(sous_valeurs)) :
                # print(f"{sous_valeurs[val]},", end=" ")    
                cursor.execute(f"SELECT SHOT.ID FROM SHOT WHERE SHOT.FROM_ID = {sous_valeurs[val]}")  
                filtre = cursor.fetchall()
    
                for row in filtre :  
                    cursor.execute(f"UPDATE SHOT SET FROM_ID = {sous_valeurs[0]} WHERE ID = {row[0]};")      
                    
                cursor.execute(f"SELECT SHOT.ID FROM SHOT WHERE SHOT.TO_ID = {sous_valeurs[val]}")  
                filtre = cursor.fetchall()
    
                for row in filtre :  
                    cursor.execute(f"UPDATE SHOT SET TO_ID = {sous_valeurs[0]} WHERE ID = {row[0]};")
                
                cursor.execute(f"UPDATE JONCTION SET STATION_TYPE = ? WHERE id = ?",  ('equ', sous_valeurs[val]))
                cursor.execute(f"UPDATE JONCTION SET STATION_JONC = ? WHERE id = ?",  (sous_valeurs[0], sous_valeurs[val]))          
            #print("  ", end="")          
        conn.commit()              
        
        # print("")               
                         
        # if len(equate) == 0 : print(f"\tAucun 'equate'")
    
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête 8 (sql_8_equates) code:\033[0m {e}")
        error_count  += 1
        
    return
            
#####################################################################################################################################
#         Fonction pour supprimer les visées en double (même départs arrivée lg, az et pente)                                       #
#####################################################################################################################################
def duplicate_SHOT():  
    global error_count 
    # Requête 10, recherche des doublons de visées
    
    try:
        cursor.execute(f"""
                    -- Requête 10, recherche des doublons de visées --
                    SELECT   
                        SHOT.FROM_ID,
                        SHOT.TO_ID, 
                        SHOT.LENGTH,
                        -- SHOT.BEARING, 
                        -- SHOT.GRADIENT, 
                        GROUP_CONCAT(SHOT.ID) as DUPP_SHOT 
                    FROM SHOT 
                    GROUP BY SHOT.FROM_ID, SHOT.TO_ID --, SHOT.BEARING, SHOT.GRADIENT, SHOT.LENGTH
                    HAVING COUNT(SHOT.FROM_ID)>1 AND COUNT(SHOT.TO_ID)>1 --AND COUNT(SHOT.BEARING)>1 AND COUNT(SHOT.GRADIENT)>1 AND COUNT(SHOT.LENGTH)>1
                    """)    
        duplicate = cursor.fetchall()
        
        _total_length_err = 0.0
        for row in duplicate :
            sous_valeurs = row[3].split(',')
            cursor.execute(f"""
                        SELECT 
                            SHOT.ID, 
                            SHOT_FLAG.FLAG,
                            round(SHOT.LENGTH, 2) 
                        FROM SHOT 
                        LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                        WHERE  SHOT.ID = {int(sous_valeurs[0])}
                    """)    
            shot_flag = cursor.fetchall()
            # print("\t " + str(shot_flag))
            
            cursor.execute(f"""
                        SELECT 
                            SHOT.ID, 
                            SHOT_FLAG.FLAG,
                            round(SHOT.LENGTH, 2) 
                        FROM SHOT 
                        LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                        WHERE  SHOT.ID = {int(sous_valeurs[1])}
                    """)    
            shot_flag2 = cursor.fetchall()
            # print("\t " + str(shot_flag2)) 
            # _total_length += int(row[2])
            if shot_flag[0][1] is None and shot_flag2[0][1]== 'dpl':
                cursor.execute("SELECT COUNT(*) AS nombre_enregistrements FROM STATION")
                Current_Station_ID = cursor.fetchall()
                _Current_Station_ID = int(Current_Station_ID[0][0]) + 1
                cursor.execute(f"INSERT INTO STATION (ID, NAME) VALUES ({_Current_Station_ID}, 'isu')")   
                cursor.execute(f"UPDATE SHOT SET TO_ID = {_Current_Station_ID} WHERE SHOT.ID = {shot_flag2[0][0]}")
                cursor.execute(f"INSERT INTO JONCTION (STATION_ID) VALUES ({_Current_Station_ID})")  
            elif shot_flag2[0][1] is None and shot_flag[0][1]== 'dpl':
                cursor.execute("SELECT COUNT(*) AS nombre_enregistrements FROM STATION")
                Current_Station_ID = cursor.fetchall()
                _Current_Station_ID = int(Current_Station_ID[0][0]) + 1
                cursor.execute(f"INSERT INTO STATION (ID, NAME) VALUES ({_Current_Station_ID}, 'isu')")   
                cursor.execute(f"UPDATE SHOT SET TO_ID = {_Current_Station_ID} WHERE SHOT.ID = {shot_flag[0][0]}")
                cursor.execute(f"INSERT INTO JONCTION (STATION_ID) VALUES ({_Current_Station_ID})")
            else :               
                _total_length_err += float(shot_flag2[0][2])
                cursor.execute("SELECT COUNT(*) AS nombre_enregistrements FROM STATION")
                Current_Station_ID = cursor.fetchall()
                _Current_Station_ID = int(Current_Station_ID[0][0]) + 1
                cursor.execute(f"INSERT INTO STATION (ID, NAME) VALUES ({_Current_Station_ID}, 'isu')")   
                cursor.execute(f"UPDATE SHOT SET TO_ID = {_Current_Station_ID} WHERE SHOT.ID = {shot_flag2[0][0]}")
                cursor.execute(f"INSERT INTO JONCTION (STATION_ID) VALUES ({_Current_Station_ID})")  
                print(f"\033[91m\t Table des SHOT, visées en double à traiter à la source : \033[0m{shot_flag}, {shot_flag2}" +
                      f"\033[91m, station crée : \033[0m{_Current_Station_ID}" + 
                      f"\033[91m, long. en double : \033[0m{"{:.2f}".format(_total_length_err)} m")
                                
            conn.commit()
            
            
            # for val in range (1, len(sous_valeurs)) :    
            #     cursor.execute(f"DELETE FROM SHOT WHERE SHOT.ID = {sous_valeurs[val]}")  
            #     filtre = cursor.fetchall()
                      
        if len(duplicate) > 0:
            print(f"\t Table des SHOT, visées dupliquées traités nbre: {len(duplicate)}")
            # print(f"\t Visées dupliqués supprimés {duplicate}")
        else :
            print(f"\t Table des SHOT, aucune visée dupliquée")     
            
            
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête (duplicate_SHOT) code:\033[0m {e}")
        error_count  += 1
        
    return
                
#####################################################################################################################################
#         Fonction pour supprimer les visées en de longueur null sur elle même (même départ et arrivée et longueur nulle            #
#####################################################################################################################################
def issue_SHOT():  
    global error_count 

    try:
        cursor.execute(f"""
                        SELECT   
                            SHOT.ID
                            --SHOT.FROM_ID,
                            --SHOT.TO_ID, 
                            --SHOT.LENGTH 
                        FROM SHOT 
                        WHERE SHOT.FROM_ID =  SHOT.TO_ID AND SHOT.LENGTH = 0
                    """)    
        issue = cursor.fetchall()
        
        for row in issue :  
            cursor.execute(f"DELETE FROM SHOT WHERE ID = {row[0]}")
            # cursor.execute(f"UPDATE SHOT SET LENGTH = 0.01 WHERE ID = {row[0]}")    
        conn.commit()              
       
        
        if len(issue) > 0:
            print(f"\t Table des SHOT, visée(s) bloquante(s), même départ et arrivée, longueur nulle supprimée(s) nbre: {len(issue)}")
            # print(f"\t Visée(s) bloquante(s) supprimée(s) {issue}")
        else :
            print(f"\t Table des SHOT, aucune visée bloquante")     
            
            
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête (Issue_SHOT) code:\033[0m {e}")
        error_count  += 1
        
    return      
        
#####################################################################################################################################
#         Fonction pour marquer les stations d'habillage                                                                            #
#####################################################################################################################################
def marquage_visee_station_habillage() :
    global error_count 
    
    try:         
        cursor.execute(f"""
                       SELECT 
                            STATION.ID AS STATION_ID,
                            SHOT.ID	AS SHOT_ID
                        FROM STATION 
                        JOIN SHOT ON SHOT.TO_ID = STATION.ID
                        WHERE STATION.NAME = '.' or STATION.NAME = '-'
                       """ )  
        
        filtre = cursor.fetchall()
        print(f"\t Marquage des visées et des stations d'habillage nbre: {len(filtre)}") 
        for row in filtre :
            cursor.execute(f"UPDATE JONCTION SET STATION_TYPE = 'hab' WHERE STATION_ID = {row[0]}")
            cursor.execute(f"UPDATE VISEE_FLAG SET SERIE_ID = -1 WHERE SHOT_ID = {row[1]}")
        conn.commit()
        
        
        
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête (marquage_station_habillage):\033[0m {e}")
        error_count += 1
        
    return

#####################################################################################################################################
#         Fonction pour suivre une série jusqu'au prochain départ ou une jonction                                                   #
#####################################################################################################################################
def suivi_serie( _Current_Serie_ID, bar) :
    global avt_compteur
    global error_count 
    
    try: 
        cursor.execute(f"SELECT * FROM SERIE WHERE SERIE_ID = {_Current_Serie_ID}")  
        _Serie = cursor.fetchall()
        
    
        # if _Current_Serie_ID == 2 or _Current_Serie_ID == 3:
        #         print("Debug, a suivre")
                 
        _Current_Next_Station = 0
        _Current_Shot = 0
        _Current_Nre_Shot = int(_Serie[0][5]) # type: ignore
        _Current_Serie_Lenght = float(_Serie[0][6]) # type: ignore
        _Current_Serie_Lenght_Surface = float(_Serie[0][7]) # type: ignore
        _Current_Serie_Lenght_Duplicate = float(_Serie[0][8]) # type: ignore
        _Direction = int(_Serie[0][9])
        _Current_Ent = int(_Serie[0][10])
    
        if _Direction == 0 :
            # print(f"\t\033[34mA gérer séries sans direction station série: {_Current_Serie_ID}\033[0m") # type: ignore
            _Current_Station_ID = int(_Serie[0][2])
            Next_Station_ID_1 = sql_station_depart(_Current_Station_ID)
            Next_Station_ID_2 = sql_station_arrivee(_Current_Station_ID)
            if len(Next_Station_ID_1) == 0 and len(Next_Station_ID_2) == 0: # type: ignore
                # Pas de départ fin  et pas d'arrivée : fin de la série
                Next_Station_ID = Next_Station_ID_1
                cursor.execute(f"UPDATE SERIE SET SERIE_NBRE_SHOT = 0  WHERE SERIE_ID = {_Current_Serie_ID};")
                conn.commit()
                return
            elif len(Next_Station_ID_1) == 1 and len(Next_Station_ID_2) == 0: # type: ignore
                # Un départ pas d'arrivée
                Next_Station_ID = Next_Station_ID_1
                Direction = 1
                cursor.execute(f"UPDATE SERIE SET DIRECTION = 1  WHERE SERIE_ID = {_Current_Serie_ID};")
                conn.commit()
            elif len(Next_Station_ID_1) == 0 and len(Next_Station_ID_2) == 1:  # type: ignore
                # Une arrivée pas de départ
                Next_Station_ID = Next_Station_ID_2
                _Serie[0][4] = _Serie[0][2]
                Direction = -1
                cursor.execute(f"UPDATE SERIE SET DIRECTION = -1  WHERE SERIE_ID = {_Current_Serie_ID};")
                conn.commit()
            else :
                # A gérer nouvelles séries
                # nouvelles_series(_Current_Station_ID, _Current_Station_ID_Old, _Current_Serie_ID, 1, _Current_Ent) # type: ignore
                # print (f"\033[34m\tA vérifier dans suivi_serie nouvelles séries inverses depuis {_Current_Station_ID} - {Next_Station_ID_2}, {Next_Station_ID_1}\033[0m")
                # nouvelles_series(_Current_Station_ID, _Current_Station_ID_Old, _Current_Serie_ID, -1, _Current_Ent)
                return  
                
        elif _Direction == -1 :
            _Current_Station_ID = int(_Serie[0][4])
            _Next_Station_ID = sql_station_arrivee(_Current_Station_ID) # type: ignore
            _Current_Nre_Shot = 0
            #print(f"\tDébut suivi serie inverse {_Current_Serie_ID}  Station_ID: {_Current_Station_ID} Nre: {_Current_Nre_Shot} Next station: {_Next_Station_ID}") # type: ignore
        
            _ID_Suite = 0
            _Force = False
            if len(_Next_Station_ID) > 1: # type: ignore
                while int(_Next_Station_ID[_ID_Suite][0]) != int(_Serie[0][2]) : # type: ignore
                    _ID_Suite += 1        
                    if _ID_Suite >= len(_Next_Station_ID): # type: ignore
                        # print(f"\t \033[34mA vérifier, pas de suite trouvée à la serie inverse: {_Current_Serie_ID} station:{_Current_Station_ID}, shot: {_Current_Shot}\033[0m")
                        #error_count  += 1
                        return    
                                            
            while (len(_Next_Station_ID)==1) or (_Force == False) : # type: ignore        
                # if _Current_Station_ID == 12074:
                #     print("Debug, a suivre")
                
                _Force = True
                _Current_Nre_Shot += 1
                _Current_Serie_Lenght += _Next_Station_ID[_ID_Suite][1]  # type: ignore
                _Current_Serie_Lenght_Surface += _Next_Station_ID[_ID_Suite][2]  # type: ignore
                _Current_Serie_Lenght_Duplicate += _Next_Station_ID[_ID_Suite][3]  # type: ignore
                _Current_Shot= _Next_Station_ID[_ID_Suite][4] # type: ignore
                _Current_Next_Station = int(_Next_Station_ID[_ID_Suite][0])  # type: ignore    
                _Current_Old_Station = int(_Current_Station_ID)
                test_jonction(_Current_Next_Station, _Current_Serie_ID, _Current_Ent)   # type: ignore     
                
                cursor.execute(f"""
                            UPDATE SERIE SET 
                                    SERIE_DEP_ID = {_Current_Serie_ID}, 
                                    STATION_DEP_ID = {_Current_Next_Station},
                                    SERIE_NBRE_Shot = {_Current_Nre_Shot},
                                    SERIE_LENGHT = {_Current_Serie_Lenght},
                                    SERIE_LENGHT_SURFACE = {_Current_Serie_Lenght_Surface},
                                    SERIE_LENGHT_DUPLICATE = {_Current_Serie_Lenght_Duplicate}    
                                WHERE SERIE_ID = {_Current_Serie_ID};
                            """)
                
                    
                cursor.execute(f"""
                            UPDATE JONCTION SET 
                                    STATION_TYPE = 'inv',
                                    ENTREE_ID = {_Current_Ent},
                                    SERIE_RANG = {_Current_Nre_Shot},
                                    SERIE_ID = {_Current_Serie_ID}
                                WHERE STATION_ID = {_Current_Station_ID}
                                """)    
                
                cursor.execute(f"""
                            UPDATE VISEE_FLAG SET 
                                SERIE_ID = {_Current_Serie_ID}, 
                                ENTREE_ID = {_Current_Ent}, 
                                SERIE_RANG  = {_Current_Nre_Shot} 
                            WHERE SHOT_ID = {_Current_Shot}
                            """)         
                
                #print(f"\tSuivi serie inverse {_Current_Serie_ID}  Station_ID: {_Current_Station_ID} Nre: {_Current_Nre_Shot}, long: {_Current_Serie_Lenght:.2f}, Next station: {_Next_Station_ID}")
                conn.commit()
                depart =  sql_station_depart(_Current_Station_ID)

                if (len(depart) >= 1 ) : # type: ignore
                    #print(f'Départ direct à gérer station: {_Current_Station_ID} série: {_Current_Serie_ID}, nbre shot: {_Current_Nre_Shot},  long: {_Current_Serie_Lenght:.2f}, Arrivée(s) {depart}')  
                    nouvelles_series(_Current_Station_ID, _Current_Old_Station, _Current_Serie_ID, 1, _Current_Ent) # type: ignore  
                        
                _Current_Station_ID = int(_Next_Station_ID[_ID_Suite][0])  # type: ignore  
                _Next_Station_ID = sql_station_arrivee(_Current_Next_Station)
                _ID_Suite = 0
                
            cursor.execute(f"""
                            UPDATE SERIE SET 
                                    SERIE_DEP_ID = {_Current_Serie_ID}, 
                                    STATION_DEP_ID = {_Current_Next_Station}, 
                                    SERIE_NBRE_Shot = {_Current_Nre_Shot},
                                    SERIE_LENGHT = {_Current_Serie_Lenght},
                                    SERIE_LENGHT_SURFACE = {_Current_Serie_Lenght_Surface},
                                    SERIE_LENGHT_DUPLICATE = {_Current_Serie_Lenght_Duplicate}    
                                WHERE SERIE_ID = {_Current_Serie_ID};
                            """)   
            
            # if _Current_Station_ID == 5047 :
            #     print("debug point")
                
            cursor.execute(f"""
                            UPDATE JONCTION SET 
                                    STATION_TYPE = 'arv',
                                    ENTREE_ID = {_Current_Ent},
                                    SERIE_RANG = {_Current_Nre_Shot},
                                    SERIE_ID = {_Current_Serie_ID}
                                WHERE STATION_ID = {_Current_Station_ID}
                                """)    
            
            cursor.execute(f"""
                        UPDATE VISEE_FLAG SET 
                           SERIE_ID = {_Current_Serie_ID}, 
                           ENTREE_ID = {_Current_Ent}, 
                           SERIE_RANG  = {_Current_Nre_Shot} 
                           WHERE SHOT_ID = {_Current_Shot}
                        """)    
                
            conn.commit()
            
            if _Current_Nre_Shot > 1 :
                avt_compteur = avt_compteur + _Current_Nre_Shot - 1
                bar(_Current_Nre_Shot-1)
                
            #_Current_Next_Station = int(_Next_Station_ID[0][0])  # type: ignore        
            depart =  sql_station_depart(_Current_Station_ID) # type: ignore     
            if (len(_Next_Station_ID)==0): # type: ignore
                # fin de la série
                # print (f"\tFin de la série inverse: {_Current_Serie_ID} (pas de suite) station: {_Current_Station_ID}, nbre de shot: {_Current_Nre_Shot}, long: {_Current_Serie_Lenght:.2f}")    
                nouvelles_series(_Current_Station_ID, _Current_Old_Station, _Current_Serie_ID, 1, _Current_Ent) # type: ignore     
                if (len(depart)>=1):# type: ignore
                    nouvelles_series(_Current_Station_ID, _Current_Old_Station, _Current_Serie_ID, -1, _Current_Ent) # type: ignore   
            else :
                nouvelles_series(_Current_Station_ID, _Current_Old_Station, _Current_Serie_ID, -1, _Current_Ent) # type: ignore     
                # print (f"\tFin de la série inverse: {_Current_Serie_ID} station: {_Current_Station_ID}, nbre de shot: {_Current_Nre_Shot}, long: {_Current_Serie_Lenght:.2f}")
                if (len(depart)>=1):# type: ignore
                    nouvelles_series(_Current_Station_ID, _Current_Old_Station, _Current_Serie_ID, 1, _Current_Ent) # type: ignore  
        elif _Direction == 1 :
            _Current_Station_ID = int(_Serie[0][2])          
            _Next_Station_ID = sql_station_depart(_Current_Station_ID)
            _Current_Nre_Shot = 0
            #print(f"\tDébut suivi serie directe {_Current_Serie_ID}  Station_ID: {_Current_Station_ID} Nre: {_Current_Nre_Shot} Next station: {_Next_Station_ID}")
            
            _ID_Suite = 0
            _Force = False
            if len(_Next_Station_ID) > 1: # type: ignore
                while int(_Next_Station_ID[_ID_Suite][0]) != int(_Serie[0][4]) : # type: ignore
                    _ID_Suite += 1     
                    if _ID_Suite >= len(_Next_Station_ID): # type: ignore
                        # print(f"\t \033[34mA vérifier, pas de suite trouvée à la serie directe: {_Current_Serie_ID}, Station: {_Current_Station_ID}, shot: {_Current_Shot}\033[0m")
                        # error_count  += 1
                        return    
                                            
            while (len(_Next_Station_ID)==1) or (_Force == False) : # type: ignore
                # if _Current_Station_ID == 12074:
                #         print("Debug, a suivre")
                _Force = True
                _Current_Nre_Shot += 1
                _Current_Serie_Lenght += _Next_Station_ID[0][1]  # type: ignore
                _Current_Serie_Lenght_Surface += _Next_Station_ID[_ID_Suite][2]  # type: ignore
                _Current_Serie_Lenght_Duplicate += _Next_Station_ID[_ID_Suite][3]  # type: ignore
                _Current_Shot= _Next_Station_ID[_ID_Suite][4] # type: ignore
                _Current_Next_Station = int(_Next_Station_ID[0][0])  # type: ignore
                _Current_Old_Station = int(_Current_Station_ID)  
                test_jonction(_Current_Next_Station, _Current_Serie_ID, _Current_Ent)   # type: ignore   
                
                cursor.execute(f"""
                            UPDATE SERIE SET 
                                    SERIE_DEP_ID = {_Current_Serie_ID}, 
                                    STATION_DEP_ID = {_Current_Next_Station},
                                    SERIE_NBRE_Shot = {_Current_Nre_Shot},
                                    SERIE_LENGHT = {_Current_Serie_Lenght},
                                    SERIE_LENGHT_SURFACE = {_Current_Serie_Lenght_Surface},
                                    SERIE_LENGHT_DUPLICATE = {_Current_Serie_Lenght_Duplicate}    
                                WHERE SERIE_ID = {_Current_Serie_ID};
                            """)
                
                # if _Current_Station_ID == 5035 :
                #     print("debug point")
                
                
                cursor.execute(f"""
                            UPDATE JONCTION SET 
                                STATION_TYPE = 'dir',
                                ENTREE_ID = {_Current_Ent},
                                SERIE_RANG = {_Current_Nre_Shot},
                                SERIE_ID = {_Current_Serie_ID}
                            WHERE STATION_ID = {_Current_Station_ID}
                                """)    
                
                cursor.execute(f"""
                            UPDATE VISEE_FLAG SET 
                                SERIE_ID = {_Current_Serie_ID}, 
                                ENTREE_ID = {_Current_Ent},
                                SERIE_RANG  = {_Current_Nre_Shot} 
                            WHERE SHOT_ID = {_Current_Shot}
                                """)    
                
                conn.commit()
                #print(f"\tSuivi serie directe {_Current_Serie_ID}  Station_ID: {_Current_Station_ID} Nre: {_Current_Nre_Shot} Next station: {_Next_Station_ID}")
                
                arrivee =  sql_station_arrivee(_Current_Station_ID)
                    
                if (len(arrivee) >= 1 ) : # type: ignore
                    #print(f'Arrivée à gérer station: {_Current_Station_ID} série: {_Current_Serie_ID}, nbre shot: {_Current_Nre_Shot},  long: {_Current_Serie_Lenght:.2f}, Arrivée(s) {arrivee}')  
                    nouvelles_series(_Current_Station_ID, _Current_Old_Station, _Current_Serie_ID, -1, _Current_Ent) # type: ignore
                    
                _Current_Station_ID = int(_Next_Station_ID[0][0])  # type: ignore  
                _Next_Station_ID = sql_station_depart(_Current_Next_Station)
                _ID_Suite = 0
                
            cursor.execute(f"""
                            UPDATE SERIE SET 
                                SERIE_DEP_ID = {_Current_Serie_ID}, 
                                STATION_DEP_ID = {_Current_Next_Station},
                                SERIE_NBRE_Shot = {_Current_Nre_Shot},
                                SERIE_LENGHT = {_Current_Serie_Lenght},
                                SERIE_LENGHT_SURFACE = {_Current_Serie_Lenght_Surface},
                                SERIE_LENGHT_DUPLICATE = {_Current_Serie_Lenght_Duplicate}    
                            WHERE SERIE_ID = {_Current_Serie_ID};
                            """) # type: ignore  
            
            cursor.execute(f"""
                            UPDATE JONCTION SET 
                                STATION_TYPE = 'end',
                                ENTREE_ID = {_Current_Ent},
                                SERIE_RANG = {_Current_Nre_Shot},
                                SERIE_ID = {_Current_Serie_ID}
                            WHERE STATION_ID = {_Current_Station_ID}
                            """)   
            
            cursor.execute(f"""
                           UPDATE VISEE_FLAG SET 
                                SERIE_ID = {_Current_Serie_ID},
                                ENTREE_ID = {_Current_Ent},
                                SERIE_RANG  = {_Current_Nre_Shot}     
                            WHERE SHOT_ID = {_Current_Shot}
                            """)    
            
            conn.commit()
            
            if  _Current_Nre_Shot > 1:
                avt_compteur = avt_compteur + _Current_Nre_Shot - 1
                bar(_Current_Nre_Shot-1)
            
            arrivee = sql_station_arrivee(_Current_Next_Station) # type: ignore     
            if (len(_Next_Station_ID)==0): # type: ignore
                # fin de la série
                # print (f"\tFin de la série directe: {_Current_Serie_ID} (pas de suite) à la station: {_Current_Station_ID}, nbre de shot: {_Current_Nre_Shot}, long: {_Current_Serie_Lenght:.2f}")           
                nouvelles_series(_Current_Station_ID, _Current_Old_Station, _Current_Serie_ID, -1, _Current_Ent) # type: ignore
                if (len(arrivee)>=1): # type: ignore
                    nouvelles_series(_Current_Station_ID, _Current_Old_Station, _Current_Serie_ID, 1, _Current_Ent) # type: ignore
            else :
                nouvelles_series(_Current_Station_ID, _Current_Old_Station, _Current_Serie_ID, 1, _Current_Ent) # type: ignore
                # print (f"\tFin de la série directe: {_Current_Serie_ID} station: {_Current_Station_ID}, nbre de shot: {_Current_Nre_Shot}, long: {_Current_Serie_Lenght:.2f}")
                if (len(arrivee)>=1): # type: ignore
                    nouvelles_series(_Current_Station_ID, _Current_Old_Station, _Current_Serie_ID, -1, _Current_Ent) # type: ignore  
       
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête de lecture de la série\033[0m {_Current_Serie_ID}\033[91m, suivi_serie:\033[0m {e}")
        error_count  += 1
        return        
    
    return

#####################################################################################################################################
#         Fonction pour créer les nouvelles séries à une station                                                                    #
#####################################################################################################################################
def nouvelles_series(_Current_Station_ID, _Current_Old_Station, _Current_Serie_ID, _DIRECTION, _STATION_ENT_ID) :       
    global error_count 
    
    # if _Current_Serie_ID == 2 or _Current_Serie_ID == 3:
    #         print("Debug, a suivre")

    
    try:
        if _DIRECTION == 1:
            _Next_Station = sql_station_depart(_Current_Station_ID)     
            # cursor.execute(f"""
            #     SELECT SHOT.TO_ID as TO_ID_RESULT
            #     FROM SHOT 
            #     WHERE SHOT.FROM_ID = {_Current_Station_ID} 
            #     -- AND ( SELECT SHOT.TO_ID FROM SHOT WHERE SHOT.FROM_ID = TO_ID_RESULT)
            #     """)  
            # _Next_Station = cursor.fetchall()
        elif _DIRECTION == -1:
            _Next_Station = sql_station_arrivee(_Current_Station_ID)
            # cursor.execute(f"""
            #     SELECT SHOT.FROM_ID as FROM_ID_RESULT  
            #     FROM SHOT 
            #     WHERE SHOT.TO_ID = {_Current_Station_ID}
            #     -- AND ( SELECT SHOT.FROM_ID FROM SHOT WHERE SHOT.TO_ID = FROM_ID_RESULT )
            #     """)    
            # _Next_Station = cursor.fetchall()
    
        if _Next_Station is None: # type: ignore
                print(f"Pas de série crées à la station: {_Current_Station_ID}")
                return
    #  boucle sur liste _Next_Station
        for Depart in _Next_Station:  # type: ignore
            if _Current_Old_Station !=  Depart[0] : # type: ignore
                cursor.execute(f"UPDATE JONCTION SET SERIE_JONC = {_Current_Serie_ID}  WHERE STATION_ID = {_Current_Station_ID};")
                cursor.execute(f"UPDATE JONCTION SET ENTREE_ID = {_STATION_ENT_ID}  WHERE STATION_ID = {_Current_Station_ID};")
                cursor.execute(f"UPDATE JONCTION SET STATION_JONC = {Depart[0]}  WHERE STATION_ID = {_Current_Station_ID};")
                cursor.execute(f"UPDATE JONCTION SET STATION_TYPE = ? WHERE id = ?",  ('jon', _Current_Station_ID))
                if _DIRECTION == 1 :
                    cursor.execute(f"""
                            INSERT INTO SERIE (  
                                SERIE_DEP_ID,
                                STATION_DEP_ID, 
                                SERIE_ARR_ID , 
                                STATION_ARR_ID, 
                                SERIE_NBRE_SHOT, 
                                SERIE_LENGHT,
                                SERIE_LENGHT_SURFACE,
                                SERIE_LENGHT_DUPLICATE,
                                DIRECTION, 
                                STATION_ENT_ID) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (_Current_Serie_ID, _Current_Station_ID, -1, Depart[0], -1, 0.0, 0.0, 0.0, 1,_STATION_ENT_ID))
                    conn.commit() 
                    # print(f"\tCréation Série directe: {cursor.lastrowid} depuis la station: {_Current_Station_ID} vers {Depart[0]} ")
                elif _DIRECTION == -1 :
                    cursor.execute(f"""
                        INSERT INTO SERIE (  
                            SERIE_DEP_ID,
                            STATION_DEP_ID, 
                            SERIE_ARR_ID , 
                            STATION_ARR_ID, 
                            SERIE_NBRE_SHOT, 
                            SERIE_LENGHT,
                            SERIE_LENGHT_SURFACE,
                            SERIE_LENGHT_DUPLICATE,
                            DIRECTION, 
                            STATION_ENT_ID) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (-1, Depart[0], _Current_Serie_ID, _Current_Station_ID, -1, 0.0, 0.0, 0.0, -1,_STATION_ENT_ID))
                    conn.commit() 
                    
                    # print(f"\tCréation Série inv.: {cursor.lastrowid} depuis {Depart[0]} vers la station: {_Current_Station_ID}")
                   
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de la requête (nouvelle_serie):\033[0m {e}")
        error_count  += 1
        
    return
          
#####################################################################################################################################
#         Fonction pour tester si la station a déjà été lue                                                                         #
#####################################################################################################################################
def test_jonction(station, serie, entree) :    
    global error_count 
    
    try:
        
        cursor.execute(f"""
                        -- Requête 6: Détection des départs depuis une station (visée directe)
                        SELECT 
                            SHOT.TO_ID as TO_ID_RESULT, 
                            --JONCTION.STATION_TYPE, 
                            SHOT.LENGTH, 
                            CASE 
                                WHEN SHOT_FLAG.FLAG  = 'srf' THEN SHOT.LENGTH
                                ELSE 0
                            END AS LENGTH_SRF,	
                            CASE 
                                WHEN SHOT_FLAG.FLAG  = 'dpl' THEN SHOT.LENGTH
                                ELSE 0
                            END AS LENGTH_DPL,
                            SHOT.ID	
                            -- SHOT_FLAG.FLAG as Type_Flag 
                        FROM SHOT  
                        --JOIN JONCTION ON SHOT.TO_ID = JONCTION.STATION_ID
                        LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                        WHERE SHOT.FROM_ID =  {station} -- AND JONCTION.STATION_TYPE IS NULL
                        -- AND ( SELECT SHOT.TO_ID FROM SHOT WHERE SHOT.FROM_ID = TO_ID_RESULT)
                        """)  
        depart = cursor.fetchall()
        
        cursor.execute(f"""
                        -- Requête 7: Détection des arrivées depuis une station (Visée inverse)
                        SELECT 
                            SHOT.FROM_ID as FROM_ID_RESULT, 
                            --JONCTION.STATION_TYPE, 
                            SHOT.LENGTH, 
                            CASE 
                                WHEN SHOT_FLAG.FLAG  = 'srf' THEN SHOT.LENGTH 
                                ELSE 0
                            END AS LENGTH_SRF,	
                            CASE 
                                WHEN SHOT_FLAG.FLAG  = 'dpl' THEN SHOT.LENGTH
                                ELSE 0
                            END AS LENGTH_DPL,
                            SHOT.ID	
                            -- SHOT_FLAG.FLAG  
                        FROM SHOT 
                        --JOIN JONCTION ON SHOT.FROM_ID = JONCTION.STATION_ID
                        LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                        WHERE SHOT.TO_ID = {station} --AND JONCTION.STATION_TYPE IS NULL
                        --AND ( SELECT JONCTION.STATION_TYPE FROM JONCTION WHERE SHOT.TO_ID = FROM_ID_RESULT 
                    """)    
        arrivee = cursor.fetchall()
        
        total = arrivee + depart # type: ignore
        for row in total:   # type: ignore  
            cursor.execute(f"SELECT JONCTION.STATION_TYPE FROM JONCTION WHERE JONCTION.STATION_ID = {row[0]}")
            
            
            # if row[1] == 5017:
            #         print('Debug point')
                    
            retour = cursor.fetchall()
            val = str(retour[0])
            
            if val != '(None,)' : 
                cursor.execute(f"UPDATE JONCTION SET STATION_TYPE = ? WHERE id = ?",  ('jon', row[0]))
                cursor.execute(f"SELECT JONCTION.ENTREE_ID FROM JONCTION WHERE JONCTION.STATION_ID = {row[0]}")
                retour = cursor.fetchall()
                cursor.execute(f"SELECT JONCTION.SERIE_ID FROM JONCTION WHERE JONCTION.STATION_ID = {row[0]}")
                _serie = cursor.fetchall()
                # print (f"\tJonction à proximité de la Station_ID: {row[0]}, retour: {str(val)}, serie {serie} - {_serie[0][0]},  entrée {entree} - {retour[0][0]}")
                if (retour[0][0] != entree) and (retour[0][0] != None) :
                    print (f"\033[36m\t Jonction à la Station_ID: {row[0]} entre les entrées {entree} et {retour[0][0]}\033[0m")
                    cursor.execute(f"INSERT INTO RESEAU ( STATION_JONC, ENT_1, ENT_2) VALUES (?, ?, ?)", (row[0], entree, retour[0][0]))   
                    conn.commit() 
                # if _serie[0][0] != serie and (_serie[0][0] != None):
                    # print (f"\033[34m\tJonction à la Station_ID: {row[0]} entre les series {serie} et {_serie[0][0]}\033[0m")     
                       
                                 
        cursor.execute(f"SELECT JONCTION.STATION_TYPE FROM JONCTION WHERE JONCTION.STATION_ID = {station}")
        retour = cursor.fetchall()
        val = str(retour[0])
        
        if val == '(None,)' : 
            #print (f"\tPas de jonction à la Station_ID: {station}, retour: {val}")
            return False
        else :
            cursor.execute(f"UPDATE JONCTION SET STATION_TYPE = ? WHERE id = ?",  ('jon', station))
            cursor.execute(f"SELECT JONCTION.ENTREE_ID FROM JONCTION WHERE JONCTION.STATION_ID = {station}")
            retour = cursor.fetchall()
            cursor.execute(f"SELECT JONCTION.SERIE_ID FROM JONCTION WHERE JONCTION.STATION_ID = {station}")
            _serie = cursor.fetchall()
            # print (f"\tJonction à proximité de la Station_ID: {row[0]}, retour: {str(val)}, serie {serie} - {_serie[0][0]},  entrée {entree} - {retour[0][0]}")
            if retour[0][0] != entree :
                print (f"\033[0m\t Jonction à la Station_ID: {station} entre les entrées {entree} et {retour[0][0]}\033[0m") 
            if _serie[0][0] != serie :
                print (f"\033[0m\t Jonction à la Station_ID: {station} entre les series {serie} et {_serie[0][0]}\033[0m")            
            return True
        
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requêtes (test_jonction): {e}\033[0m")
        error_count  += 1    
    
    return
      
#####################################################################################################################################
#         Fonction pour exécuter une requête et sauvegarder les résultats dans un fichier texte                                     #
#                                                                                                                                   #
#####################################################################################################################################
def calcul_stats(output_file):
    global error_count
    global _largeurCol
    global _largeurColTete
    
    try:
        print(f"\033[1;32mPhase 5: Écriture des statistiques dans fichier \033[0m{safe_relpath(output_file)}")    
       # Enregistrement des résultats dans un fichier texte
        output_file_ligne_md = []
        output_file_ligne_csv = []
            
        for i in range(9): 
            output_file_ligne_csv.append(titre[i].ljust(120)+"*\n")  
            
        output_file_ligne_md.extend([
            f"--------------\n",
            f"- **Script :** {titre[1].strip()}\n",
            f"- **Version :** `{titre[2].strip()}`\n",
            f"- **Fichier source :** `{titre[3].strip()}`\n",
            f"- **Dossier destination :** `{titre[4].strip()}`\n",
            f"- **Date :** `{titre[5].strip()}`\n",
            f"- **Durée du calcul :** `{titre[6].strip()}`\n",
            f"--------------\n",
        ])

        
        sql_query1 = ("""
                Select 
                       round(sum(LENGTH), 2) as Lg,
                       round(sum(DUPLICATE_LENGTH),2) as Duplicate,
                       round(sum(SURFACE_LENGTH),2) as Surface
                       -- round(sum(LENGTH) + sum(DUPLICATE_LENGTH), 2)  as Total
                from CENTRELINE length 
                 """)
        
        cursor.execute(sql_query1)     
        results = cursor.fetchall()            
        vide ="-".ljust(_largeurCol)
                                                                                                                                                                                                        
        output_file_ligne_csv.append(
                f"**Développement total centerline:**\t%s\t%s\t%s\t%s\t%s\tDev.(m), Dupl.(m), Surf.(m)\n" 
                %(str("{:.2f}".format(results[0][0]).ljust(_largeurCol)), 
                str("{:.2f}".format(results[0][1]).ljust(_largeurCol)),
                str("{:.2f}".format(results[0][2]).ljust(_largeurCol)),
                str(vide), 
                str(vide)))    

        output_file_ligne_md.append(
                    f"**Développement total des centerlines (m):**  "
                    f"**, Développement:** {results[0][0]:.2f} "
                    f"**, Dupliqué:** {results[0][1]:.2f} "
                    f"**, Surface:** {results[0][2]:.2f}\n"
                )

        cursor.execute("SELECT COUNT(*) AS nbre FROM JONCTION WHERE STATION_TYPE IS NULL")
        _compteur = cursor.fetchall()
        compteur = int(_compteur[0][0])
        
        if compteur > 0 : # type: ignore
            output_file_ligne_md.append(f"!!Attention, {compteur} station(s) non comptabilisée(s) et raccordée(s)\n\n")
            output_file_ligne_csv.append(f"Attention, {compteur} station(s) non comptabilisée(s) et raccordée(s)\n\n")
        
        results=sql_bilan_reseaux()
        
        if results[0][0] != None :# type: ignore
            output_file_ligne_md.append(f"--------------\n")
            output_file_ligne_md.append("**Développement total par réseaux**\n")
            output_file_ligne_csv.append("Développement total par réseaux\n")
            for row in results: # type: ignore
                formatted_row = '\t'.join(map(str, row))
                output_file_ligne_csv.append('\t' + formatted_row + '\n')
                
                formatted_row = '| ' + ' | '.join(map(str, row)) + ' |'
                output_file_ligne_md.append(formatted_row + '\n')
                #print('Développement total: ' + formatted_row + 'm') 
        
        results=sql_bilan_annee()
        if results[0][0] != None :# type: ignore
            output_file_ligne_md.append(f"\n--------------\n")
            output_file_ligne_md.append("**Développement total topographié par année(s)**\n") 
            output_file_ligne_csv.append("\nDéveloppement total topographié par année(s)**\n") 
            for row in results: # type: ignore
                if row[1].strip() != "0.00" or row[3].strip() != "0.00" or row[5].strip() != "0.00" :                
                    formatted_row = '\t'.join(map(str, row))
                    output_file_ligne_csv.append('\t' + formatted_row + '\n')
                    
                    formatted_row = '| ' + ' | '.join(map(str, row)) + ' |'
                    output_file_ligne_md.append(formatted_row + '\n')
                    #print('Développement total: ' + formatted_row + 'm') 
                    
            def format_markdown_row(row_data):
                return '| ' + ' | '.join(f"{str(item):>10}" for item in row_data) + ' |'
                    
            output_file_ligne_md.append("\n**Développement total topographié par année(s)**\n") 
            headers = ["Année", "Dev.(m)", "Cumul (m)", "Dupl.(m)", "Cumul (m)", "Surf.(m)", "Cumul (m)"]

            output_file_ligne_md.append("| " + " | ".join(headers) + " |\n")
            output_file_ligne_md.append("|" + "|".join(["---"] * len(headers)) + "|\n")

            for row in results[1:]:  # type: ignore
                if row[1].strip() != "0.00" or row[3].strip() != "0.00" or row[5].strip() != "0.00" :                
                    formatted_row = [str(v) for v in row]
                    output_file_ligne_md.append("| " + " | ".join(formatted_row) + " |\n")

                
        Rose(output_file_name_rose)        
        
        Shot_lengths_histogram(output_file_name_histo)   
        
        
        findetraitement = datetime.now()

        duree = findetraitement - maintenant        
        jours, secondes = divmod(duree.seconds, 86400)    # 86400 secondes dans une journée
        heures, secondes = divmod(secondes, 3600)         # 3600 secondes dans une heure
        minutes, secondes = divmod(secondes, 60)          # 60 secondes dans une minute
        if duree.seconds > 3600: 
            duree_formatee = "{:02}(h){:02}(m){:02}(s)".format(heures, minutes, secondes)
        elif duree.seconds > 60: 
            duree_formatee = "{:02}(m){:02}(s)".format(minutes, secondes)
        else :
            duree_formatee = "{:02}(s)".format(secondes)
            
        if error_count == 0:   
                output_file_ligne_csv[7] = "*       Durée calcul: " + duree_formatee + " sans erreur"
                output_file_ligne_md[7] = "- **Durée calcul : ** `" + duree_formatee + " sans erreur `\n"
                output_file_ligne_csv[7] = output_file_ligne_csv[7].ljust(120)+"*\n"
                        
        else :
                output_file_ligne_csv[7] = "*       Durée calcul: " + duree_formatee + " avec erreur(s): " + str(error_count)
                output_file_ligne_md[7] = "- **Durée calcul : ** `" + duree_formatee + "!! avec erreur(s):`" + str(error_count) + "`\n"
                output_file_ligne_csv[7] = output_file_ligne_csv[7].ljust(120)+"*\n"
        
        with open(output_file + ".md", 'w',  encoding='utf-8') as file:
            file.writelines(output_file_ligne_md)
            
        with open(output_file + ".csv", 'w',  encoding='utf-8') as file:
            file.writelines(output_file_ligne_csv)

        if error_count == 0 :
            print(f"\033[1;32mPhase 6: Fin de traitement en \033[0m" + duree_formatee + f"\033[1;32m, résultats enregistrés dans \033[0m{safe_relpath(output_file)}") 
        
        else :
            print(f"\033[1;32mPhase 6: Fin de traitement en \033[0m" + duree_formatee 
                + f",\033[91m avec \033[0m{error_count}\033[91m erreur(s), \033[1;32mrésultats enregistrés dans \033[0m{safe_relpath(output_file)}")  
            
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution des requêtes calcul_stats:\033[0m {e}")
        error_count  += 1
        output_file_ligne_md.append(f"!!! Erreur lors de l'exécution des requêtes calcul_stats: {e}\n")
        output_file_ligne_csv.append(f"Erreur lors de l'exécution des requêtes calcul_stats: {e}\n")
        
        with open(output_file + ".md", 'w',  encoding='utf-8') as file:
            file.writelines(output_file_ligne_md)
            
        with open(output_file + ".csv", 'w',  encoding='utf-8') as file:
            file.writelines(output_file_ligne_csv)
            
        return
        
    except FileNotFoundError:
        print(f"\033[91mErreur d'ouverture du fichier: \033[0m{safe_relpath(output_file)} ")
        error_count  += 1
        
        return
    
    except Exception as e:
        print(f"\033[91mErreur lors de l'exécution de calcul_stats:\033[0m {e}")
        error_count  += 1
        output_file_ligne_md.append(f"!! Erreur lors de l'exécution de calcul_stats: {e}\n")
        output_file_ligne_csv.append(f"Erreur lors de l'exécution de calcul_stats: {e}\n")
        
        with open(output_file + ".md", 'w',  encoding='utf-8') as file:
            file.writelines(output_file_ligne_md)
            
        with open(output_file + ".csv", 'w',  encoding='utf-8') as file:
            file.writelines(output_file_ligne_csv)
        
        return
        
    return

#####################################################################################################################################
#        # Requête : Table des entrées  (Liste des entrées avec coordonnées)                                                       #
#####################################################################################################################################
def sql_liste_entree():
    global error_count
         
    sql_query=  ("""
                    select 
                        STATION.ID, 
                        STATION.NAME, 
                        /*SURVEY.NAME, SURVEY.PARENT_ID, SURVEY.FULL_NAME, SURVEY.TITLE,*/ 
                        round(STATION.X, 1), 
                        round(STATION.Y, 1), 
                        round(STATION.Z, 1) 
                        /*, STATION_FLAG.FLAG , count(STATION.NAME) AS Nombre_Occurrences */
                    from STATION 
                    join STATION_FLAG on STATION_FLAG.STATION_ID = STATION.ID
                    join SURVEY on SURVEY.ID = STATION.SURVEY_ID
                    where STATION_FLAG.FLAG='ent' or STATION_FLAG.FLAG='fix' --and STATION.ID = 28548
                    group by STATION.NAME , STATION.Y, STATION.Z 
                    order by STATION.NAME ASC 
                """)
    
    # sql_query2 = ("""
    #                 select 
    #                     STATION.ID, 
    #                     STATION.NAME, 
    #                     /*SURVEY.NAME, SURVEY.PARENT_ID, SURVEY.FULL_NAME, SURVEY.TITLE,*/ 
    #                     round(STATION.X, 1), 
    #                     round(STATION.Y, 1), 
    #                     round(STATION.Z, 1) 
    #                     /*, STATION_FLAG.FLAG , count(STATION.NAME) AS Nombre_Occurrences */
    #                 from STATION 
    #                 join STATION_FLAG on STATION_FLAG.STATION_ID = STATION.ID
    #                 join SURVEY on SURVEY.ID = STATION.SURVEY_ID
    #                 where STATION_FLAG.FLAG='fix' --and STATION.ID = 28548
    #                 --group by STATION.NAME
    #                 order by STATION.NAME ASC 
    #             """)
    try:
        cursor.execute(sql_query)    
        result_ent = cursor.fetchall()
        # cursor.execute(sql_query)    
        # result_fix = cursor.fetchall()
        if len(result_ent) == 0 :
            error_count  += 1 
            print(f"\t \033[91mAttention aucune entrée ou point fix comptabilisé\033[0m")
        else :
            print(f"\t \033[32mTable des STATION, entrée et fix nbre: \033[0m{len(result_ent)}")
        
        return result_ent
    
        # if len(result_ent) == 0:
        #     print(f"\033[91mPas d'entrées\033[0m")
        #     if len(result_fix) == 0:
        #         print(f"\033[91mPas de points fixes\033[0m")
        #         return None
        #     else :
        #         print(f"\tTable des STATION, point fixe nbre: {len(result_fix)}")     
        #         return result_fix
        # elif len(result_ent) == len(result_fix) :
        #     print(f"\tTable des STATION, entrée nbre: {len(result_ent)}")
        #     # print(f"\tTable des STATION, point fixe nbre: {len(result_fix)}")
        #     return result_ent
        # elif len(result_ent) > len(result_fix) :
        #     print(f"\033[91mA gérer Points fixes > entrées, traitement uniquement des entrées\033[0m")
        #     return result_ent
        # elif len(result_ent) < len(result_fix) :
        #     print(f"\033[91mA gérer Points fixes < entrées, traitement uniquement des points fixes\033[0m")
        #     return result_fix
        
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête 4 (sql_liste_entree):\033[0m {e}")
        error_count  += 1
        return None
    return

#####################################################################################################################################
#           # Requête : Table des séries vides                                                                                     #
#####################################################################################################################################
def sql_serie_vides():
    global error_count   
        
    sql_query5 = ("""
                 SELECT *                          
                    FROM SERIE
                 WHERE SERIE.SERIE_NBRE_SHOT = -1""")
    try:
        cursor.execute(sql_query5)     # Exécution de la requête SQL
        retour = cursor.fetchall()
        # if len(retour) == 0 :
        #     print(f"Aucune séries vides {len(retour)}")
        return retour
    
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête (sql_serie_vides): {e}\033[0m")
        error_count  += 1
        return None
    
    return

#####################################################################################################################################
#           # Requête: From_To (recherche si il y a un départ dans le sens From vers To depuis la station Current_Station_ID)     #
#####################################################################################################################################
def sql_station_depart(station):
    global error_count   
    
    try:
        cursor.execute(f"""
                        -- Requête 6: Détection des départs depuis une station (visée directe)
                        SELECT 
                            SHOT.TO_ID as TO_ID_RESULT, 
                            --JONCTION.STATION_TYPE, 
                            SHOT.LENGTH, 
                            CASE 
                                WHEN SHOT_FLAG.FLAG  = 'srf' THEN SHOT.LENGTH
                                ELSE 0
                            END AS LENGTH_SRF,	
                            CASE 
                                WHEN SHOT_FLAG.FLAG  = 'dpl' THEN SHOT.LENGTH
                                ELSE 0
                            END AS LENGTH_DPL,	
                            -- SHOT_FLAG.FLAG as Type_Flag
                            SHOT.ID 
                        FROM SHOT  
                        JOIN JONCTION ON SHOT.TO_ID = JONCTION.STATION_ID
                        LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                        WHERE SHOT.FROM_ID =  {station} AND JONCTION.STATION_TYPE IS NULL
                        -- AND ( SELECT SHOT.TO_ID FROM SHOT WHERE SHOT.FROM_ID = TO_ID_RESULT)
            """)  
        retour = cursor.fetchall()
        # if len(retour) == 0 : print(f"\tAucun départ depuis la station: {station}")
        return retour
    
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête 6 (sql_station_depart) code:\033[0m {e}")
        error_count  += 1
        return None
    
    return

#####################################################################################################################################
#           # Requête : To_From (recherche si il y a un départ dans le sens To vers From depuis la station Current_Station_ID)     #
#####################################################################################################################################
def sql_station_arrivee(station):
    global error_count  
     
    try:
        cursor.execute(f"""
                        -- Requête 7: Détection des arrivées depuis une station (Visée inverse)
                        SELECT 
                            SHOT.FROM_ID as FROM_ID_RESULT, 
                            --JONCTION.STATION_TYPE, 
                            SHOT.LENGTH, 
                            CASE 
                                WHEN SHOT_FLAG.FLAG  = 'srf' THEN SHOT.LENGTH
                                ELSE 0
                            END AS LENGTH_SRF,	
                            CASE 
                                WHEN SHOT_FLAG.FLAG  = 'dpl' THEN SHOT.LENGTH
                                ELSE 0
                            END AS LENGTH_DPL,
                            SHOT.ID
                            -- SHOT_FLAG.FLAG  
                        FROM SHOT 
                        JOIN JONCTION ON SHOT.FROM_ID = JONCTION.STATION_ID
                        LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                        WHERE SHOT.TO_ID = {station} AND JONCTION.STATION_TYPE IS NULL
                        --AND ( SELECT JONCTION.STATION_TYPE FROM JONCTION WHERE SHOT.TO_ID = FROM_ID_RESULT 
                    """)    
        retour = cursor.fetchall()
        # if len(retour) == 0 print(f"\tAucune arrivée depuis  la station: {station}")
        return retour
    
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête 7 (sql_station_arrivee) code:\033[0m {e}")
        error_count  += 1
        return None
    
    return

#####################################################################################################################################
#            #-- Bilan table série                                                                                                  #
#####################################################################################################################################
def sql_bilan_serie():
    global error_count
    
    try:
        cursor.execute(f"""
                        -- Bilan table série
                        select 
                            --STATION.NAME,
                            -- sum(SERIE.SERIE_LENGHT) as Total,
                            round(sum(SERIE.SERIE_LENGHT) - sum(SERIE.SERIE_LENGHT_SURFACE)- sum(SERIE.SERIE_LENGHT_DUPLICATE), 2) as Long,
                            round(sum(SERIE.SERIE_LENGHT_DUPLICATE),2) as Duplicate, 
                            round(sum(SERIE.SERIE_LENGHT_SURFACE),2) as Surface, 
                            sum(SERIE.SERIE_NBRE_SHOT) as Nbre_Shot,
                            COUNT(*) AS Nbre_serie
                        FROM SERIE	
                        JOIN STATION ON SERIE.STATION_ENT_ID = STATION.ID
                        """)
        retour = cursor.fetchall()
        return retour
    
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête 11 (sql_bilan_serie):\033[0m {e}")
        error_count  += 1
        return None
    
    return

#####################################################################################################################################
#            #--  Bilan table série By Réseaux                                                                                      #
#####################################################################################################################################
def sql_bilan_reseaux():
    global error_count 
    global _largeurCol
    global _largeurColTete
    retour = []
    
    try:
        
                    
        ###############################################################################################################
        #  Liste des réseaux
        ###############################################################################################################    
        
        cursor.execute(f"""
                            -- Bilan table série By Réseaux
                            select 
                                --SURVEY_RESEAU.TITLE as Réseau,
                                --SURVEY_RESEAU.NAME,
                                --SURVEY_RESEAU.ID,
                                RESEAU_ID,
                                --STATION.NAME as Nom,
                                -- sum(SERIE.SERIE_LENGHT) as Total,
                                round(sum(SERIE.SERIE_LENGHT) - sum(SERIE.SERIE_LENGHT_SURFACE)- sum(SERIE.SERIE_LENGHT_DUPLICATE), 2) as Long,
                                round(sum(SERIE.SERIE_LENGHT_DUPLICATE),2) as Duplicate, 
                                round(sum(SERIE.SERIE_LENGHT_SURFACE),2) as Surface, 
                                sum(SERIE.SERIE_NBRE_SHOT) as Nbre_Shot
                                --COUNT(*) AS Nbre_serie
                                --round(max(STATION.Z),2) as Max_Z,
                                --round(min(STATION.Z),2) as Min_Z,
                                --max(STATION.Z) - min(STATION.Z) as Delta_Z
                            FROM SERIE	
                            JOIN STATION ON SERIE.STATION_ENT_ID = STATION.ID
                            JOIN SURVEY AS SURVEY_JONCTION ON STATION.SURVEY_ID = SURVEY_JONCTION.ID
                            JOIN SURVEY AS SURVEY_RESEAU ON SURVEY_JONCTION.PARENT_ID = SURVEY_RESEAU.ID
                            WHERE RESEAU_ID is not NULL and RESEAU_ID !=0
                            GROUP BY SERIE.RESEAU_ID
                            ORDER BY Long DESC
                        """)
        result = cursor.fetchall()
             
        if len(result) >0 : 
            # _ligne = [ ' - ', " - ", " - ", " - ", " - ", " - ", " - ", " - ", " - ", " - ", " - "] 
            # _ligne[0]= 'Aucun réseau'.ljust(_largeurColTete)
            # retour.append(_ligne)
            # return retour
        
            for row in result:
                ligne = [ ' - ', " - ", " - ", " - ", " - ", " - ", " - ", " - ", " - ", " - ", " - "] 
                
                result_shot = 0
            
                cursor.execute(f"""
                                    select 
                                        COALESCE(round(sum(SHOT.length), 2), 0) as ttl,
                                        count(VISEE_FLAG.ID) as count,
                                        STATION_TO.NAME as To_Name	
                                    from VISEE_FLAG 
                                    JOIN SHOT ON SHOT.ID = VISEE_FLAG.SHOT_ID
                                    JOIN STATION AS STATION_TO ON SHOT.TO_ID = STATION_TO.ID
                                    LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                                    WHERE To_Name!='.' AND To_Name!='-' AND SHOT_FLAG.FLAG is null and VISEE_FLAG.RESEAU_ID ={row[0]}
                                """)
                _result_length = cursor.fetchall()
                result_length = float(_result_length[0][0])
                result_shot = int(_result_length[0][1])
            
                cursor.execute(f"""
                                    select 
                                        COALESCE(round(sum(SHOT.length), 2), 0) as ttl,
                                        count(VISEE_FLAG.ID) as count,
                                        STATION_TO.NAME as To_Name	
                                    from VISEE_FLAG 
                                    JOIN SHOT ON SHOT.ID = VISEE_FLAG.SHOT_ID
                                    JOIN STATION AS STATION_TO ON SHOT.TO_ID = STATION_TO.ID
                                    LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                                    WHERE To_Name!='.' AND To_Name!='-' AND SHOT_FLAG.FLAG ='dpl' and VISEE_FLAG.RESEAU_ID ={row[0]}
                                """)
                
                _result_length_dpl = cursor.fetchall()
                result_length_dpl = float(_result_length_dpl[0][0])
                result_shot += int(_result_length_dpl[0][1]) 
            
                cursor.execute(f"""
                                    select 
                                        COALESCE(round(sum(SHOT.length), 2), 0) as ttl,
                                        count(VISEE_FLAG.ID) as count,
                                        STATION_TO.NAME as To_Name	
                                    from VISEE_FLAG 
                                    JOIN SHOT ON SHOT.ID = VISEE_FLAG.SHOT_ID
                                    JOIN STATION AS STATION_TO ON SHOT.TO_ID = STATION_TO.ID
                                    LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                                    WHERE To_Name!='.' AND To_Name!='-' AND SHOT_FLAG.FLAG ='srf' and VISEE_FLAG.RESEAU_ID ={row[0]}
                                """)
                
                _result_length_srf = cursor.fetchall()
                result_length_srf = float(_result_length_srf[0][0])
                result_shot += int(_result_length_srf[0][1])  

                
                # ligne = [ 'none', 0, 0, 0, 0, 0, 0, 'none', 0, 'none', 0, 0]     
                cursor.execute(f""" 
                                -- Liste des entrée dans la table RESEAU 
                                SELECT 
                                    --RESEAU.ENT_1 AS ENT_ID,
                                    --RESEAU.RESEAU_ID,
                                    STATION.NAME
                                    --STATION.Z
                                FROM RESEAU 
                                JOIN STATION ON RESEAU.ENT_1 = STATION.ID
                                WHERE RESEAU_ID = {row[0]}
                                UNION --ALL
                                SELECT 
                                    --RESEAU.ENT_2 AS ENT_ID,
                                    --RESEAU.RESEAU_ID,
                                    STATION.NAME
                                    --STATION.Z
                                FROM RESEAU
                                JOIN STATION ON RESEAU.ENT_2 = STATION.ID 
                                WHERE RESEAU_ID =  {row[0]}
                                GROUP BY STATION.NAME
                                ORDER BY STATION.NAME 
                                --ORDER BY STATION.Z DESC
                            """)
                liste_entree = cursor.fetchall()
                
            
                _liste_ent = liste_entree[0][0]
                
                index = 1
                while index < len(liste_entree):
                    _liste_ent += ", " +  liste_entree[index][0]
                    index += 1
                        
                if len(_liste_ent) > _largeurColTete :
                    _largeurColTete = len(_liste_ent) + 2
                    
        
                ligne[0] =_liste_ent.ljust(_largeurColTete)          # Liste Entrées
                ligne[1] = str(len(liste_entree))                    # Nre Ent.
                ligne[2] = str("{:.2f}".format(result_length))       # Dev.
                ligne[4] = str("{:.2f}".format(result_length_dpl))   # Dupl.
                ligne[5] = str("{:.2f}".format(result_length_srf))   # Surf.
                ligne[6] = str(result_shot)                          # Visées
                
                cursor.execute(f""" 
                                -- Requête pour rechercher le point bas d'un réseau / entrée
                                SELECT
                                    STATION.name,
                                    STATION.Z as Min
                                from STATION 
                                join (
                                    select Min(STATION.Z) as Val_Min
                                    from STATION
                                    join JONCTION on STATION.ID = JONCTION.STATION_ID
                                    WHERE JONCTION.RESEAU_ID = {row[0]}
                                ) min on STATION.Z = min.Val_Min
                                LIMIT 1
                            """)
                altitude_min = cursor.fetchall()
                
                ligne[7] = altitude_min[0][0]
                ligne[8] = str("{:.2f}".format(altitude_min[0][1])) 
                
                cursor.execute(f""" 
                                -- Requête pour rechercher le point haut  d'un réseau / entrée
                                SELECT
                                    STATION.name,
                                    STATION.Z as Max
                                from STATION 
                                join (
                                    select Max(STATION.Z) as Val_Max
                                    from STATION
                                    join JONCTION on STATION.ID = JONCTION.STATION_ID
                                    WHERE JONCTION.RESEAU_ID = {row[0]}
                                ) max on STATION.Z = max.Val_Max
                                LIMIT 1
                            """)
                altitude_max = cursor.fetchall()
                
                ligne[9] = altitude_max[0][0]
                ligne[10] = str("{:.2f}".format(altitude_max[0][1])) 
                ligne[3] =  "{:.2f}".format(altitude_max[0][1] - altitude_min[0][1]) 
                
                for i in range(9): ligne[i+1] = ligne[i+1].ljust(_largeurCol)  
                retour.append(ligne)
                
                # print(f"Reseau num {row[0]}, {len(liste_entree)} entrée(s): {_liste_ent} ")
        
            
        ###############################################################################################################
        #  Liste des visées non raccordées 
        ###############################################################################################################
        cursor.execute(f"""
                            SELECT 
                                sum (SHOT.LENGTH) as Long
                            FROM VISEE_FLAG
                            JOIN SHOT ON SHOT.ID = VISEE_FLAG.SHOT_ID
                            LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                            JOIN STATION AS STATION_FROM ON SHOT.FROM_ID = STATION_FROM.ID
                            JOIN STATION AS STATION_TO ON SHOT.TO_ID = STATION_TO.ID
                            JOIN JONCTION AS JONCTION_FROM ON SHOT.FROM_ID = JONCTION_FROM.ID
                            JOIN JONCTION AS JONCTION_TO ON SHOT.TO_ID = JONCTION_TO.ID
                            WHERE VISEE_FLAG.SERIE_ID is NULL and SHOT_FLAG.FLAG is NULL 
                        """)
        result_long = cursor.fetchall()
        
        if result_long[0][0] is None : 
            _result_long = 0.0
        else :
            _result_long = result_long[0][0]
        
        cursor.execute(f"""
                            SELECT 
                                sum (SHOT.LENGTH) as Long
                            FROM VISEE_FLAG
                            JOIN SHOT ON SHOT.ID = VISEE_FLAG.SHOT_ID
                            LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                            JOIN STATION AS STATION_FROM ON SHOT.FROM_ID = STATION_FROM.ID
                            JOIN STATION AS STATION_TO ON SHOT.TO_ID = STATION_TO.ID
                            JOIN JONCTION AS JONCTION_FROM ON SHOT.FROM_ID = JONCTION_FROM.ID
                            JOIN JONCTION AS JONCTION_TO ON SHOT.TO_ID = JONCTION_TO.ID
                            WHERE VISEE_FLAG.SERIE_ID is NULL and SHOT_FLAG.FLAG ='dpl' 
                        """)
        result_dpl = cursor.fetchall()
        
        if result_dpl[0][0] is None : 
            _result_dpl = 0.0
        else :
            _result_dpl = result_dpl[0][0]
        
        cursor.execute(f"""
                            SELECT 
                                sum (SHOT.LENGTH) as Long
                            FROM VISEE_FLAG
                            JOIN SHOT ON SHOT.ID = VISEE_FLAG.SHOT_ID
                            LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                            JOIN STATION AS STATION_FROM ON SHOT.FROM_ID = STATION_FROM.ID
                            JOIN STATION AS STATION_TO ON SHOT.TO_ID = STATION_TO.ID
                            JOIN JONCTION AS JONCTION_FROM ON SHOT.FROM_ID = JONCTION_FROM.ID
                            JOIN JONCTION AS JONCTION_TO ON SHOT.TO_ID = JONCTION_TO.ID
                            WHERE VISEE_FLAG.SERIE_ID is NULL and SHOT_FLAG.FLAG ='srf' 
                        """)
        result_srf = cursor.fetchall()
        if result_srf[0][0] is None : 
            _result_srf = 0.0
        else :
            _result_srf = result_srf[0][0]
        
        cursor.execute(f"""
                            SELECT 
                                count (SHOT.LENGTH) as Long
                            FROM VISEE_FLAG
                            JOIN SHOT ON SHOT.ID = VISEE_FLAG.SHOT_ID
                            LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                            JOIN STATION AS STATION_FROM ON SHOT.FROM_ID = STATION_FROM.ID
                            JOIN STATION AS STATION_TO ON SHOT.TO_ID = STATION_TO.ID
                            JOIN JONCTION AS JONCTION_FROM ON SHOT.FROM_ID = JONCTION_FROM.ID
                            JOIN JONCTION AS JONCTION_TO ON SHOT.TO_ID = JONCTION_TO.ID
                            WHERE VISEE_FLAG.SERIE_ID is NULL --and SHOT_FLAG.FLAG ='srf' 
                        """)
        result_count = cursor.fetchall()
        
        if result_count[0][0] is None : 
            _result_count = 0.0
        else :
            _result_count = result_count[0][0]
        
        ligne = [ ' - ', " - ", " - ", " - ", " - ", " - ", " - ", " - ", " - ", " - ", " - "] 
        _liste_ent = "Visée(s) non raccordées" 
        _liste_ent = _liste_ent.ljust(_largeurColTete)           
        ligne[0] = _liste_ent
        ligne[1] = str("0") 
        ligne[2] = str("{:.2f}".format(_result_long)) 
        ligne[4] = str("{:.2f}".format(_result_dpl)) 
        ligne[5] = str("{:.2f}".format(_result_srf)) 
        ligne[6] = str(_result_count) 
        
        cursor.execute(f""" 
                        -- Requête pour rechercher le point bas d'un réseau / entrée
                        SELECT
                            STATION.name,
                            STATION.Z as Min
                        from STATION 
                        join (
                            select Min(STATION.Z) as Val_Min
                            from STATION
                            join JONCTION on STATION.ID = JONCTION.STATION_ID
                            WHERE JONCTION.SERIE_ID is null 
                        ) min on STATION.Z = min.Val_Min
                        LIMIT 1
                    """)
        altitude_min = cursor.fetchall()
        
        if len(altitude_min) == 0 : 
            _altitude_min = 0.0
            _altitude_min_name = 'None'
        else :
            _altitude_min = altitude_min[0][1]
            _altitude_min_name =  str(altitude_min[0][0])
        
        ligne[7] = str(_altitude_min_name)
        ligne[8] = str("{:.2f}".format(_altitude_min))
        
        cursor.execute(f""" 
                        -- Requête pour rechercher le point haut d'un réseau / entrée
                        SELECT
                            STATION.name,
                            STATION.Z as Max
                        from STATION 
                        join (
                            select Max(STATION.Z) as Val_Max
                            from STATION
                            join JONCTION on STATION.ID = JONCTION.STATION_ID
                            WHERE JONCTION.SERIE_ID is null 
                        ) max on STATION.Z = max.Val_Max
                        LIMIT 1
                    """)
        altitude_max = cursor.fetchall()
        
        if len(altitude_max) == 0 : 
            _altitude_max = 0.0
            _altitude_max_name = 'None'
        else :
            _altitude_max = altitude_max[0][1]
            _altitude_max_name =  str(altitude_max[0][0])
        
        ligne[7] = str(_altitude_max_name)
        ligne[8] = str("{:.2f}".format(_altitude_max)) 
        ligne[3] =  "-"  #"{:.2f}".format(altitude_max[0][1] - altitude_min[0][1])
        
        
        for i in range(9): ligne[i+1] = ligne[i+1].ljust(_largeurCol)  
        if  _result_long !=0 or _result_dpl != 0 or _result_srf !=0 or _result_count !=0:
            retour.append(ligne)    
        
        ###############################################################################################################
        #  Totaux
        ###############################################################################################################
       
        result_shot = 0
    
        cursor.execute(f"""
                            select 
                                COALESCE(round(sum(SHOT.length), 2), 0) as ttl,
                                count(VISEE_FLAG.ID) as count,
                                STATION_TO.NAME as To_Name	
                            from VISEE_FLAG 
                            JOIN SHOT ON SHOT.ID = VISEE_FLAG.SHOT_ID
                            JOIN STATION AS STATION_TO ON SHOT.TO_ID = STATION_TO.ID
                            LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                            WHERE To_Name!='.' AND To_Name!='-' AND SHOT_FLAG.FLAG is null 
                        """)
        _result_length = cursor.fetchall()
        
        result_length = float(_result_length[0][0])
        result_shot = int(_result_length[0][1])
    
        cursor.execute(f"""
                            SELECT 
                                COALESCE(round(sum(SHOT.length), 2), 0) as ttl,
                                count(VISEE_FLAG.ID) as count,
                                STATION_TO.NAME as To_Name	
                            FROM VISEE_FLAG 
                            JOIN SHOT ON SHOT.ID = VISEE_FLAG.SHOT_ID
                            JOIN STATION AS STATION_TO ON SHOT.TO_ID = STATION_TO.ID
                            LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                            WHERE To_Name!='.' AND To_Name!='-' AND SHOT_FLAG.FLAG ='dpl' 
                        """)
        _result_length_dpl = cursor.fetchall()
        
        result_length_dpl = float(_result_length_dpl[0][0])
        result_shot += int(_result_length_dpl[0][1]) 
    
        cursor.execute(f"""
                            SELECT 
                                COALESCE(round(sum(SHOT.length), 2), 0) as ttl,
                                count(VISEE_FLAG.ID) as count,
                                STATION_TO.NAME as To_Name	
                            FROM VISEE_FLAG 
                            JOIN SHOT ON SHOT.ID = VISEE_FLAG.SHOT_ID
                            JOIN STATION AS STATION_TO ON SHOT.TO_ID = STATION_TO.ID
                            LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                            WHERE To_Name!='.' AND To_Name!='-' AND SHOT_FLAG.FLAG ='srf' 
                        """)
        _result_length_srf = cursor.fetchall()
        
        result_length_srf = float(_result_length_srf[0][0])
        result_shot += int(_result_length_srf[0][1])  
        
        cursor.execute(f"""
                            -- Bilan table VISEE_FLAG By entrées
                            select 
                                ENTREE_ID
                                --STATION.NAME
                            FROM VISEE_FLAG	
                            JOIN STATION ON VISEE_FLAG.ENTREE_ID = STATION.ID
                            WHERE SERIE_ID >0
                            GROUP BY VISEE_FLAG.ENTREE_ID
                        """)
        _result_entrees = cursor.fetchall()
        
        _total_entrees_topo = len(_result_entrees)
        
        result2 =  sql_liste_entree()
        _total_entrees_non_topo = len(result2) - _total_entrees_topo    # type: ignore
        
        
        if _result_length[0][1] != None :
            ligne = [ ' - ', " - ", " - ", " - ", " - ", " - ", " - ", " - ", " - ", " - ", " - "] 
    
            ligne[0] = "Totaux (entrées et points fixes)".ljust(_largeurColTete)   # Liste Entrées
            ligne[1] = str("{:.0f}".format(len(result2)))        # type: ignore    # Nre Ent.
            ligne[2] = str("{:.2f}".format(result_length))       # Dev.
            ligne[4] = str("{:.2f}".format(result_length_dpl))   # Dupl.
            ligne[5] = str("{:.2f}".format(result_length_srf))   # Surf.
            ligne[6] = str(result_shot)                          # Visées
            
            cursor.execute(f""" 
                            -- Requête pour rechercher le point bas d'un réseau / entrée
                            SELECT
                                STATION.name,
                                STATION.Z as Min
                            from STATION 
                            join (
                                select Min(STATION.Z) as Val_Min
                                from STATION
                                join JONCTION on STATION.ID = JONCTION.STATION_ID
                            ) min on STATION.Z = min.Val_Min
                            LIMIT 1
                            """)
            altitude_min = cursor.fetchall()
            
            ligne[7] = altitude_min[0][0]
            ligne[8] = str(altitude_min[0][1]) 
            
            cursor.execute(f""" 
                            -- Requête pour rechercher le point haut d'un réseau / entrée
                            SELECT
                                STATION.name,
                                STATION.Z as Max
                            from STATION 
                            join (
                                select Max(STATION.Z) as Val_Max
                                from STATION
                                join JONCTION on STATION.ID = JONCTION.STATION_ID
                            ) max on STATION.Z = max.Val_Max
                            LIMIT 1
                        """)
            altitude_max = cursor.fetchall()
            
            ligne[9] = altitude_max[0][0]
            ligne[10] = str("{:.2f}".format(altitude_max[0][1])) 
            ligne[3] =  "{:.2f}".format(altitude_max[0][1] - altitude_min[0][1]) 
            
            for i in range(9): ligne[i+1] = ligne[i+1].ljust(_largeurCol)  
            retour.append(ligne)
        else :
            _total_entrees_non_topo = 0
            _total_entrees_topo = 0
                
        
        ###############################################################################################################
        #  Liste des entrées uniques
        ###############################################################################################################
        cursor.execute(f"""
                        -- Bilan table VISEE_FLAG By entrées
                        select 
                            ENTREE_ID,
                            STATION.NAME
                        FROM VISEE_FLAG	
                        JOIN STATION ON VISEE_FLAG.ENTREE_ID = STATION.ID
                        WHERE RESEAU_ID ==0 or RESEAU_ID is null and SERIE_ID >0
                        GROUP BY VISEE_FLAG.ENTREE_ID
                        """)
        result = cursor.fetchall()
        
        for row in result :
            ligne = [ ' - ', " - ", " - ", " - ", " - ", " - ", " - ", " - ", " - ", " - ", " - "]            
            
            result_shot = 0
        
            cursor.execute(f"""
                                select 
                                    COALESCE(round(sum(SHOT.length), 2), 0) as ttl,
                                    count(VISEE_FLAG.ID) as count,
                                    STATION_TO.NAME as To_Name	
                                from VISEE_FLAG 
                                JOIN SHOT ON SHOT.ID = VISEE_FLAG.SHOT_ID
                                JOIN STATION AS STATION_TO ON SHOT.TO_ID = STATION_TO.ID
                                LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                                WHERE To_Name!='.' AND To_Name!='-' AND SHOT_FLAG.FLAG is null and VISEE_FLAG.ENTREE_ID ={row[0]}
                            """)
            _result_length = cursor.fetchall()
            
            result_length = float(_result_length[0][0])
            result_shot = int(_result_length[0][1])
        
            cursor.execute(f"""
                                select 
                                    COALESCE(round(sum(SHOT.length), 2), 0) as ttl,
                                    count(VISEE_FLAG.ID) as count,
                                    STATION_TO.NAME as To_Name	
                                from VISEE_FLAG 
                                JOIN SHOT ON SHOT.ID = VISEE_FLAG.SHOT_ID
                                JOIN STATION AS STATION_TO ON SHOT.TO_ID = STATION_TO.ID
                                LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                                WHERE To_Name!='.' AND To_Name!='-' AND SHOT_FLAG.FLAG ='dpl' and VISEE_FLAG.ENTREE_ID ={row[0]}
                            """)
            _result_length_dpl = cursor.fetchall()
            
            result_length_dpl = float(_result_length_dpl[0][0])
            result_shot += int(_result_length_dpl[0][1]) 
        
            cursor.execute(f"""
                                select 
                                    COALESCE(round(sum(SHOT.length), 2), 0) as ttl,
                                    count(VISEE_FLAG.ID) as count,
                                    STATION_TO.NAME as To_Name	
                                from VISEE_FLAG 
                                JOIN SHOT ON SHOT.ID = VISEE_FLAG.SHOT_ID
                                JOIN STATION AS STATION_TO ON SHOT.TO_ID = STATION_TO.ID
                                LEFT JOIN SHOT_FLAG ON SHOT.ID = SHOT_FLAG.SHOT_ID
                                WHERE To_Name!='.' AND To_Name!='-' AND SHOT_FLAG.FLAG ='srf' and VISEE_FLAG.ENTREE_ID ={row[0]}
                            """)
            _result_length_srf = cursor.fetchall()
            
            result_length_srf = float(_result_length_srf[0][0])
            result_shot += int(_result_length_srf[0][1])  
            
            if result_length_srf == 0.0 and result_length == 0.0 and result_length_dpl == 0.0 :
                _total_entrees_non_topo+=1
            else :         
                ligne[0] = str((row[1])).ljust(_largeurColTete)  
                ligne[1] = str("1") 
                ligne[2] = str("{:.2f}".format(result_length))       # Dev.
                ligne[4] = str("{:.2f}".format(result_length_dpl))   # Dupl.
                ligne[5] = str("{:.2f}".format(result_length_srf))   # Surf.
                ligne[6] = str(result_shot)                          # Visées
                
                cursor.execute(f""" 
                                -- Requête pour rechercher le point bas d'un réseau / entrée
                                SELECT
                                    STATION.name,
                                    STATION.Z as Min
                                from STATION 
                                join (
                                    select Min(STATION.Z) as Val_Min
                                    from STATION
                                    join JONCTION on STATION.ID = JONCTION.STATION_ID
                                    WHERE JONCTION.ENTREE_ID = {row[0]}
                                ) min on STATION.Z = min.Val_Min
                                LIMIT 1
                            """)
                altitude_min = cursor.fetchall()
                
                ligne[7] = altitude_min[0][0]
                ligne[8] = str("{:.2f}".format(altitude_min[0][1])) 
                
                cursor.execute(f""" 
                                -- Requête pour rechercher le point haut d'un réseau / entrée
                                SELECT
                                    STATION.name,
                                    STATION.Z as Max
                                from STATION 
                                join (
                                    select Max(STATION.Z) as Val_Max
                                    from STATION
                                    join JONCTION on STATION.ID = JONCTION.STATION_ID
                                    WHERE JONCTION.ENTREE_ID = {row[0]}
                                ) max on STATION.Z = max.Val_Max
                                LIMIT 1
                            """)
                altitude_max = cursor.fetchall()
                
                ligne[9] = altitude_max[0][0]
                ligne[10] = str("{:.2f}".format(altitude_max[0][1]))
                ligne[3] =  "{:.2f}".format(altitude_max[0][1] - altitude_min[0][1])
                
                
                for i in range(9): ligne[i+1] = ligne[i+1].ljust(_largeurCol)  
                retour.append(ligne)    
                
        ###############################################################################################################
        #  Entrées sans topo 
        ###############################################################################################################
        
        ligne = [ ' - ', " - ", " - ", " - ", " - ", " - ", " - ", " - ", " - ", " - ", " - "] 
        
        if _total_entrees_non_topo >=1 :
            ligne[0] = "Entrée(s) sans topographie".ljust(_largeurColTete)
            ligne[1] = str(_total_entrees_non_topo)    
            ligne[2] = "0.00"
            ligne[3] = "0.00"
            ligne[4] = "0.00" 
            ligne[5] = "0.00"  
            ligne[6] = "0"  
            
            cursor.execute(f""" 
                            -- Requête pour rechercher le points bas d'un réseau / entrée
                            SELECT
                                STATION.name,
                                STATION.Z as Min
                            from STATION 
                            join (
                                select Min(STATION.Z) as Val_Min
                                from STATION
                                join JONCTION on STATION.ID = JONCTION.STATION_ID
                                WHERE JONCTION.SERIE_ENT = -1 AND JONCTION.STATION_TYPE = 'ent' 
                            ) min on STATION.Z = min.Val_Min
                            LIMIT 1
                        """)
            altitude_min = cursor.fetchall()
            
            ligne[7] = altitude_min[0][0]
            ligne[8] = str(altitude_min[0][1]) 
            
            cursor.execute(f""" 
                            -- Requête pour rechercher le point haut d'un réseau / entrée
                            SELECT
                                STATION.name,
                                STATION.Z as Max
                            from STATION 
                            join (
                                select Max(STATION.Z) as Val_Max
                                from STATION
                                join JONCTION on STATION.ID = JONCTION.STATION_ID
                                WHERE JONCTION.SERIE_ENT = -1 AND JONCTION.STATION_TYPE = 'ent' 
                            ) max on STATION.Z = max.Val_Max
                            LIMIT 1
                        """)
            altitude_max = cursor.fetchall()
            
            ligne[9] = altitude_max[0][0]
            ligne[10] = str("{:.2f}".format(altitude_max[0][1])) 
            ligne[3] =  "{:.2f}".format(altitude_max[0][1] - altitude_min[0][1]) 

            for i in range(9): ligne[i+1] = ligne[i+1].ljust(_largeurCol)  
            retour.append(ligne)
        
        
            
        ###############################################################################################################
        #  Tri et résultats
        ###############################################################################################################     
            
        entetes = [ 'Entrée(s)', "Nbre", "Dev.(m)", "Prof.(m)", "Dupl.(m)", "Surf.(m)", "Visées", "ID Sta.", "Alt. min(m)", "ID Sta.", "Alt. max(m)" ]  
        entetes[0] = entetes[0].ljust(_largeurColTete)  
        for i in range(9): entetes[i+1] = entetes[i+1].ljust(_largeurCol)  
        
        _corps_retour = sorted(retour, key=cle_tri, reverse=True)
        
        _retour = [entetes] + _corps_retour
                
        return _retour  # type: ignore
    
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête (sql_bilan_reseaux):\033[0m {e}")
        error_count  += 1
        return retour
    
    return


#####################################################################################################################################
#            Optimisation, création des indexes                                                                                     #
#####################################################################################################################################
def sql_optimisation():
    """
    Création des index d’optimisation pour les requêtes de synthèse Therion.
    Compatible SQLite / PostgreSQL / MySQL.

    Parameters
    ----------
    cursor : DB cursor
        Curseur SQL actif
    verbose : bool
        Affiche les index créés
    """ 
    global error_count 
    
    try:
        
        indexes = [
            # SERIE
            ("idx_serie_reseau", """
                CREATE INDEX IF NOT EXISTS idx_serie_reseau
                ON SERIE (RESEAU_ID)
            """),

            ("idx_serie_station", """
                CREATE INDEX IF NOT EXISTS idx_serie_station
                ON SERIE (STATION_ENT_ID)
            """),

            ("idx_serie_reseau_station", """
                CREATE INDEX IF NOT EXISTS idx_serie_reseau_station
                ON SERIE (RESEAU_ID, STATION_ENT_ID)
            """),

            # STATION
            ("idx_station_survey", """
                CREATE INDEX IF NOT EXISTS idx_station_survey
                ON STATION (SURVEY_ID)
            """),

            # SURVEY
            ("idx_survey_parent", """
                CREATE INDEX IF NOT EXISTS idx_survey_parent
                ON SURVEY (PARENT_ID)
            """),
        ]

        for name, sql in indexes:
                cursor.execute(sql)
             
             
        return             
    
    except Exception as e:
        print(f"\033[91mErreur lors de l'exécution de la requête (sql_optimisation):\033[0m {e}")
        error_count  += 1
        return 
    
    
    return

#####################################################################################################################################
#            # Clé de tri                                                                                                           #
#####################################################################################################################################        
def cle_tri(element):
    return float(element[2])
     
#####################################################################################################################################
#            #--  Bilan topo par années                                                                                             #
#####################################################################################################################################
def sql_bilan_annee():
    global error_count 
    global _largeurCol
    global _largeurColTete
    
    try:
        retour = []
                   
        cursor.execute(f"""
                        select strftime('%Y', TOPO_DATE) as annee
                        from CENTRELINE 
                        Where TOPO_DATE is not NULL
                        order by TOPO_DATE
                        """)
        result = cursor.fetchall()
        
        entetes = [ "Année" , "Dev.(m)", "Cumul (m)", "Dupl.(m)",  "Cumul (m)",  "Surf.(m)", "Cumul (m)" ]  
        cumul = 0.0
        cumul_dpl = 0.0
        cumul_srf = 0.0
        
        for i in range(6): entetes[i] = entetes[i].ljust(_largeurCol)         
        retour.append(entetes)
        
        #            topo sans année
        cursor.execute(f"""
                        select 
                            COALESCE( sum(LENGTH), 0), 
                            COALESCE (sum(DUPLICATE_LENGTH), 0),
                            COALESCE( sum(SURFACE_LENGTH), 0) 
                        from CENTRELINE 
                        where TOPO_DATE IS NULL 
                """)
        bilan_annee = cursor.fetchall()
        
        if ( len(bilan_annee) >=  1 ) and (( float(bilan_annee[0][0]) > 0.0)  or (float(bilan_annee[0][1]) > 0.0 ) or (float(bilan_annee[0][2]) > 0.0 )):
            ligne =   [ " - ", " - ", " - ", " - ", " - ", " - ", " - " ]
        
            
            cumul += bilan_annee[0][0]
            cumul_dpl += bilan_annee[0][1]
            cumul_srf += bilan_annee[0][2]
            ligne[0] = "-"
            ligne[1] = str("{:.2f}".format(bilan_annee[0][0]))
            ligne[2] = str("{:.2f}".format(cumul)) 
            ligne[3] = str("{:.2f}".format(bilan_annee[0][1]))
            ligne[4] = str("{:.2f}".format(cumul_dpl)) 
            ligne[5] = str("{:.2f}".format(bilan_annee[0][2]))
            ligne[6] = str("{:.2f}".format(cumul_srf))     
                
            for i in range(6): ligne[i] = ligne[i].ljust(_largeurCol)  
            retour.append(ligne)
        
        #            années standard
        debut = int(result[0][0])
        fin = int(result[len(result)-1][0])
        
        PlotExploYears(output_file_name_year, [debut, fin])
        
        for annee in range(debut, fin + 1, 1 ): 
            cursor.execute(f"""
                            select 
                                COALESCE (sum(LENGTH), 0), 
                                COALESCE (sum(DUPLICATE_LENGTH), 0), 
                                COALESCE (sum(SURFACE_LENGTH), 0)
                            from CENTRELINE 
                            where TOPO_DATE between '{annee}-01-01' and '{annee}-12-31';
                    """)
            bilan_annee = cursor.fetchall()
            
            ligne =   [ " - ", " - ", " - ", " - ", " - ", " - ", " - " ]
            
            cumul += bilan_annee[0][0]
            cumul_dpl += bilan_annee[0][1]
            cumul_srf += bilan_annee[0][2]
            ligne[0] = str("{:.0f}".format(annee))
            ligne[1] = str("{:.2f}".format(bilan_annee[0][0]))
            ligne[2] = str("{:.2f}".format(cumul)) 
            ligne[3] = str("{:.2f}".format(bilan_annee[0][1]))
            ligne[4] = str("{:.2f}".format(cumul_dpl)) 
            ligne[5] = str("{:.2f}".format(bilan_annee[0][2]))
            ligne[6] = str("{:.2f}".format(cumul_srf))  

            for i in range(6): ligne[i] = ligne[i].ljust(_largeurCol)  
            retour.append(ligne)
                
        return retour  # type: ignore
        
        
    except sqlite3.Error as e:
        print(f"\033[91mErreur lors de l'exécution de la requête (sql_bilan_annee):\033[0m {e}")
        error_count  += 1
        return None
    
    except Exception as e:
        print(f"\033[91mErreur lors de l'exécution de sql_bilan_annee:\033[0m {e}")
        error_count  += 1
    
    return None
     
#####################################################################################################################################
#            diagramme de "rose"                                                                                                     #
#####################################################################################################################################     
def Rose(graph_name, bins = 72):
	"""
	Plot a Rose diagram of the entire database

	Args:
		conn (sqlite_db): database sqlite
		graph_name (str): path and name of the graph to save
		bins (int, optional): bins for the plot. Defaults to 72.
	"""
	
	# Extract the right data
	df = pd.read_sql_query("select * from SHOT;", conn)

	# Built the histogram
	#h, e = np.histogram(df["BEARING"] * np.pi/180., weights = df["LENGTH"], bins = bins)
	# Pour enlever les visées verticales (et donc de bearing systématiquement à 0°...)
	h, e = np.histogram(df["BEARING"] * np.pi/180., weights = df["LENGTH"]* (90-np.abs(df["GRADIENT"]))/100, bins = bins)
	
	# Plot the rose diagram
	ax = plt.subplot(111, projection = "polar")
	ax.set_theta_zero_location("N")    # type: ignore
	ax.set_theta_direction(-1)          # type: ignore
	ax.bar(e[:-1], h, align = "edge", width = e[1]-e[0])
	
	# Save the rose diagram
	plt.savefig(graph_name)
	# Close the graph
	plt.close(plt.figure(1))
	
	return

#####################################################################################################################################
#            diagramme de longueurs de visées                                                                                       #
#####################################################################################################################################  
def Shot_lengths_histogram(graph_name, bins = 72, log = None):
	"""
	Plot the histogram of the lengths of the shots for the entire database

	Args:
		conn (sqlite_db): database sqlite
		graph_name (str): path and name of the graph to save
		bins (int, optional): bins for the plot. Defaults to 72.
		log (str, optional): set it to 'log' to use a y-logscale. Defaults to None.
	"""
	
	# Extract the right data
	df = pd.read_sql_query("select * from SHOT;", conn)
	
	# plot the histogram
	plt.hist(df["LENGTH"], bins = bins)
	plt.xlabel("Longueur de visée (m)")
	plt.ylabel("Nombre")
	plt.xlim(0,50)
	
	# If log y-scale, set it
	if log:
		plt.yscale("log")
		
	# save
	plt.savefig(graph_name)
	plt.close(plt.figure(1))
	
	return
     
#####################################################################################################################################
#            diagrammes par années                                                                                                  #
#####################################################################################################################################  
def PlotExploYears(graph_name, rangeyear = [1959, datetime.now().year], systems = None):
	"""
	Args:
		conn (sqlite_db): database sqlite
		graph_name (str): path and name of the graph to save
		rangeyear (np.array of integers, optional): 2 elements numpy array that gives the range of the years to analyse. Defaults to [1959, datetime.date.today().year].
		systems (list of str, optional): list of specific systems to plot if needed. Defaults to None.
	"""

	# define colors to use; You may add colors if needed
	colores = ['tab:blue', 'tab:red', 'tab:green', 'tab:orange', 'tab:purple', 
			   'tab:marron', 'tab:olive', 'tab:pink', 'tab:cyan']
	
	if systems:
		# Initiate variables
		#somme = pd.DataFrame(columns = ['System', 'Year', 'Longueur'])
		Sy = []
		Yr = []
		Lg = []
		# Loop on the systems and the years
		for system in systems:
			for date in range(rangeyear[0], rangeyear[1]+1):
				# Define SQL query
				lquery = "select sum(LENGTH) from CENTRELINE where SURVEY_ID in (select ID from SURVEY where FULL_NAME LIKE '%s%s%s') and TOPO_DATE between '%s-01-01' and '%s-12-31';" %(chr(37), str(system),chr(37), str(date), str(date))
				junk = pd.read_sql_query(lquery, conn)
				# Update the DataFrame line to line; DEPRECIATED since pandas 2.0
				#somme = somme.append({'System' : system,
				#				  'Year' : int(date),
				#			 	  'Longueur' : junk.to_numpy()[0][0]}, ignore_index = True)
				Sy.append(system)
				Yr.append(int(date))
				Lg.append(junk.to_numpy()[0][0])
				#print(junk)
		somme = pd.DataFrame(list(zip(Sy, Yr, Lg)), columns = ['System', 'Year', 'Longueur'])
		print(max(somme['Longueur']))

		# plot the histogram since the first survey
		fig = plt.figure(1)
		ax1 = fig.add_subplot(111)
		
		fig2 = plt.figure(2)
		ax2 = fig2.add_subplot(111)
		
		# Extract the values for the first system
		sommesys = somme[somme['System'] == systems[0]]
		# Change None values to 0
		sommeplot = sommesys.fillna(0)
		# Remove the column with the names of the systems
		del sommeplot["System"]
		print(sommeplot)

		ax1.bar(sommeplot["Year"], 
		        sommeplot["Longueur"], 
				width = 0.5,
				color = colores[0],
				label = systems[0])
		ax2.bar(sommeplot["Year"], 
		        np.cumsum(sommeplot["Longueur"])/1000, 
				width = 0.5,
				color = colores[0],
				label = systems[0])
		
		# Skip the loop on systems if there is only one system requested --> stacked barplot not needed
		if len(systems) > 1:
			# Check if the number of colors is enough for the number of systems
			if len(systems)>len(colores):
				raise NameError('\033[91mERROR:\033[00m Number of colors lower than the number of systems!\n\tedit the code to add colors in the list, or lower the number of systems to plot')
			# Copy the length column in an other column to trace of it
			sommeplot[systems[0]] = sommeplot["Longueur"]

			for system in systems[1:]:
				# Extract the length for the system
				temp = somme[somme['System'] == system]
				# Replace NaN values by 0 to avoid None values in the sums
				tempplot = temp.fillna(0)
				# Reset the indexes to permit the sum of the length per year
				tempplot.reset_index(inplace = True)
				
				del tempplot["System"]
				# Update the barplot
				ax1.bar(tempplot["Year"],
			    	    tempplot["Longueur"], 
						bottom = sommeplot["Longueur"], 
						width = 0.5,
						color = colores[systems.index(system)], 
						label = system)				

				# Print the cumulative barplot
				ax2.bar(tempplot["Year"], 
			    	    np.cumsum(tempplot["Longueur"])/1000, 
						bottom = np.cumsum(sommeplot["Longueur"])/1000, 
						width = 0.5,
						color = colores[systems.index(system)],  
						label = system)

				# Do the sum of the length, and write it in the length column
				sommeplot["Longueur"] = sommeplot["Longueur"] + tempplot["Longueur"]
				# Copy the length of the system in a new column
				sommeplot[systems[systems.index(system)]] = tempplot["Longueur"]
				

		# Plot mean line
		ax1.axhline(y = somme["Longueur"].mean(), color='red', linestyle='--', label = 'Moy. annuelle')
		ax1.set_xlabel("Année")
		ax1.set_ylabel("Longueur topographiée (m)")
		ax1.legend(loc = 'best')
		# Save the histogram
		fig.savefig(graph_name + "_Reseau.pdf")
		plt.close(plt.figure(1))

		# plot the cumulative histogram since the first survey
		ax2.set_xlabel("Année")
		ax2.set_ylabel("Longueur topographiée cumulée (km)")
		ax2.legend(loc = 'best')
		# Save the cumulative histogram
		fig2.savefig(graph_name + "Cum_Reseau.pdf")
		plt.close(plt.figure(1))

	else:
		#somme = pd.DataFrame(columns = ['Year', 'Longueur'])
		Yr = []
		Lg = []
		for date in range(rangeyear[0], rangeyear[1]):
			lquery = "select sum(LENGTH) from CENTRELINE where TOPO_DATE between '%s-01-01' and '%s-12-31';" %(str(date), str(date))	
			junk = pd.read_sql_query(lquery, conn)
			## Depreciated depuis Pandas 2.0
			#somme = somme.append({'Year' : int(date),
			#				 	  'Longueur' : junk.to_numpy()[0][0]}, ignore_index = True)
			Yr.append(int(date))
			Lg.append(junk.to_numpy()[0][0])
		
		somme = pd.DataFrame(list(zip(Yr, Lg)), columns = ['Year', 'Longueur'])


		# plot the histogram since the first survey
		plt.bar(somme["Year"], somme["Longueur"], width = 0.5)
		# plot mean
		plt.axhline(y = somme["Longueur"].mean(), color='red', linestyle='--', label = 'Moy. annuelle')
		plt.xlabel("Année")
		plt.ylabel("Longueur topographiée (m)")
		# Save the histogram
		plt.savefig(graph_name + ".pdf")
		plt.close(plt.figure(1))

		# plot the cumulative histogram since the first survey
		plt.bar(somme["Year"], np.cumsum(somme["Longueur"].fillna(0))/1000, width = 0.5)
		plt.xlabel("Année")
		plt.ylabel("Longueur topographiée cumulée (km)")
		# Save the cumulative histogram
		plt.savefig(graph_name + "Cum.pdf")
		plt.close(plt.figure(1))

	return    
     
#################################################################################################
# fonction pour réduire l'affichage des chemins long                                            #
#################################################################################################
def safe_relpath(path, base_dir=None, max_depth=3, max_name_len=50, prefix="~"):
    """
    Retourne un chemin lisible et sûr pour affichage (logs / UI).

    - Compatible Windows / Linux / macOS
    - Tronque la profondeur du chemin
    - Tronque le nom de fichier si trop long
    - Ne lève jamais d'exception
    """

    try:
        path = Path(path).expanduser().resolve()
    except Exception:
        return str(path)

    try:
        base = Path(base_dir).expanduser().resolve() if base_dir else Path.cwd().resolve()
    except Exception:
        base = None

    name = path.name or str(path)
    if len(name) > max_name_len:
        stem = path.stem[: max(1, max_name_len - 6)]
        name = f"{stem}...{path.suffix}"

    try:
        if base:
            rel = path.relative_to(base)
            parts = list(rel.parts)
        else:
            raise ValueError
    except Exception:
        parts = list(path.parts)

    if not parts:
        parts = ["."]

    if isinstance(max_depth, int) and max_depth > 0 and len(parts) > max_depth:
        parts = parts[-max_depth:]
        parts.insert(0, prefix)

    if parts and parts[-1] not in (".", os.sep):
        parts[-1] = name

    try:
        return os.path.join(*parts)
    except Exception:
        return name

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
    colored_help_text = help_text.replace(
        'usage:', f'\033[91musage:\033[0m'
    ).replace(
        'options:', f'\033[92moptions:\033[0m'
    ).replace('positional arguments:', f'\033[94mpositional arguments:\033[0m'
    ).replace(', --help', f'\033[94m, --help:\033[0m'
    ).replace('elp:', f'\033[94melp\033[0m')

    # Surligner les arguments
    for action in parser._actions:
        if action.option_strings:
            # Colorer les options (--xyz)
            for opt in action.option_strings:
                colored_help_text = colored_help_text.replace(opt, f'\033[94m{opt}\033[0m').replace('--help', f'\033[94m--help:\033[0m')
    
    # Imprimer le texte coloré
    print(colored_help_text)
    sys.exit(1)
  
#####################################################################################################################################
#                                                                                                                                   #
#                                                           Main                                                                    #
#                                                                                                                                   #
#####################################################################################################################################
if __name__ == '__main__':
    _largeurColTete = 30
    _largeurCol = 10
    avt_compteur = 0
    error_count = 0
    visee_suprimmees= [ 0.0, 0.0, 0.0, 0]    # Lg, Lg dpl, Lg surf
    input_file_name = ""
    outputs_path = "./Test/"
    inputs_path = "./Test/"
    # if not os.path.exists(outputs_path): os.makedirs(outputs_path)

    if os.name == 'posix':  os.system('clear') # Linux, MacOS
    elif os.name == 'nt':  os.system('cls')# Windows
    else: print("\n" * 100) 
    
    maintenant = datetime.now()
    
    parser = argparse.ArgumentParser(
        description=f"Calcul des statistiques par entrées d'une BD Therion", 
        formatter_class=argparse.RawTextHelpFormatter)
    parser.print_help = colored_help.__get__(parser)
    parser.add_argument(
        '--option',
        default="sync",
        choices=["sync", "update"],
        help=(
            f"Options d'execution de pythStat.py\nsync\t-> Synchronisation des données depuis une nouvelle base de données(défaut)\n"
            f"update\t-> Mise à jour des statistiques de la base de données\n"
        )
    )
    
    parser.add_argument("--file", help="Chemin vers le fichier SQL d'entrée (pas de d'option : fenêtre de choix)")
    parser.epilog = (f"Commande therion (fichier .thconfig) : export database -o Outputs/database.sql")
   
    # Analyser les arguments de ligne de commande
    args = parser.parse_args()

    if not args.file:    # Si aucun fichier n'est fourni en ligne de commande, ouvrir une fenêtre Tkinter pour sélectionner un fichier
        # input_file = "rabbit.sql"                        # Erreur car pas de point fix ou d'entrée python
        # input_file_name = inputs_path + input_file

        root = tk.Tk()
        root.withdraw()  # Cacher la fenêtre principale de Tkinter
        input_file_name = filedialog.askopenfilename( title="Sélectionnez le fichier SQL", filetypes=(("Fichiers SQL", "*.sql"), ("Tous les fichiers", "*.*"))        )
        
        if not input_file_name:
            print("Aucun fichier sélectionné. Le programme va se terminer.")
            sys.exit()    
        
        outputs_path = os.path.dirname(input_file_name) + "/"
        input_file = os.path.basename(input_file_name)

        
    else :         # Si le fichier est fourni en ligne de commande 
        input_file_name = args.file
        # print("Le paramètre fourni est:", input_file_name) 
        if os.path.isfile(input_file_name) is False :
            print(f"\033[91mErreur : fichier \033[0m{input_file_name}\033[91m inexistant\033[0m")      
            print(f"\033[92mCommande : \033[0mpython pythStat.py votre_fichier_therion.sql")
            sys.exit()  
        else :
            outputs_path = os.path.dirname(input_file_name) + "/"
            input_file = os.path.basename(input_file_name)
            if os.name == 'posix':  os.system('clear') # Linux, MacOS
            elif os.name == 'nt':  os.system('cls')# Windows
            else: print("\n" * 100)
        

    outputfolder = outputs_path + "stat_" + input_file[:-4] + "_" + maintenant.strftime("%Y-%m-%d") + "/"
    
    if not os.path.exists(outputfolder): os.makedirs(outputfolder)
            
    output_file_name = outputfolder + input_file[:-4]+"_stats"
    output_file_name_rose = outputfolder + input_file[:-4]+"_rose.pdf"
    output_file_name_histo = outputfolder + input_file[:-4]+"_histo.pdf"
    output_file_name_year = outputfolder + input_file[:-4]+"_year"
    imported_database = outputfolder + input_file[:-4]+"_stats.db"

    _titre =['\033[1;32m************************************************************************************************************************\033[0m', 
            '\033[1;32m* Calcul des statistiques par entrées d\'une BD Therion\033[0m',
            '\033[1;32m*       Script pythStat par alexandre.pont@yahoo.fr\033[0m',
            '\033[1;32m*       Version : \033[0m' + Version,
            '\033[1;32m*       Fichier source : \033[0m' + safe_relpath(input_file_name),           
            '\033[1;32m*       Dossier destination : \033[0m' + safe_relpath(outputfolder),
            '\033[1;32m*       Date : \033[0m' + maintenant.strftime("%Y-%m-%d %H:%M:%S"), 
            '\033[1;32m*      \033[0m', 
            '\033[1;32m************************************************************************************************************************\033[0m']


    for i in range(9): print(_titre[i].ljust(131)+"\033[1;32m*\033[0m")
    
    titre = [ligne.replace("\033[1;32m", "").replace("\033[0m", "") for ligne in _titre]  

    if args.option == "sync" : 
        importation_sql_data(input_file_name)

        conn = sqlite3.connect(imported_database)  # Connexion à la base de données SQLite
        cursor = conn.cursor()
        
        construction_tables()
        
        sql_optimisation()
        
        calcul_stats(output_file_name)

    elif args.option == "update" :
        
        conn = sqlite3.connect(imported_database)  # Connexion à la base de données SQLite
        cursor = conn.cursor()
        
        calcul_stats(output_file_name)
    
    conn.close()
    
    

