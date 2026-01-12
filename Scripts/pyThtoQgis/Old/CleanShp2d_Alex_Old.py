######!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2020 Xavier Robert <xavier.robert@ird.fr>
# SPDX-License-Identifier: GPL-3.0-or-later


"""
#############################################################
#                                                        	#  
# Script to automatize data extraction of Therion databases #
#                                                        	#  
#                 By Xavier Robert                       	#
#               Grenoble, October 2022                   	#
#                                                        	#  
#############################################################

Written by Xavier Robert, October 2022
Modifié Alex 2025 01 31 

Inputs files (16):  (.dbf, .prj, .shp, .shx)
    - points2d
    - lines2d
    - areas2d
    - outlines


En cas d'erreur corriger manuellement (QGis) les topologies des fichiers : 
    - areas2d.shp
    - lines2d.shp

xavier.robert@ird.fr

"""

# Do divisions with Reals, not with integers
# Must be at the beginning of the file
from __future__ import division

# Import Python modules
#import numpy as np
import sys, os, copy, shutil
import fiona
import shapely
import geopandas as gpd
import pandas as pd
from fiona import Env
from shapely.geometry import Polygon, LineString, MultiPolygon
from shapely.geometry import shape, mapping, GeometryCollection
from shapely.ops import transform, unary_union, polygonize
from shapely.errors import TopologicalError
from shapely.validation import make_valid, explain_validity
from collections import Counter

#from functools import wraps
from alive_progress import alive_bar              # https://github.com/rsalmei/alive-progress	




###### TO DO #####

#	- 

##### End TO DO #####

#################################################################################################
#################################################################################################

#def validate(func):
    # """
    # Function to validate areas topology.
    # From https://shapely.readthedocs.io/en/latest/manual.html

    # Args:
    #     func (_type_): _description_

    # Raises:
    #     TopologicalError: Error of topology 
    #                         - area does not close
    #                         - inner ring
    #                         - boundaries intersects


    # Returns:
    #     _type_: _description_
    # """
    # @wraps(func)
    # def wrapper(*args, **kwargs):
    #     ob = func(*args, **kwargs)
    #     if not ob.is_valid:
    #         raise TopologicalError(
    #             "Given arguments do not determine a valid geometric object")
    #     return ob
    # return wrapper


def validate(inputfile, rec):

    rec2 = rec
    #print(rec['geometry']['coordinates'][0])   # il y a visiblement un soucis avec le nombre de []

    if not Polygon(rec['geometry']['coordinates'][0]).is_valid:
        print('Problem in %s geometry' %(inputfile))
        print('%s is not a valid geometric object' %(rec['properties']['_ID']))
        raise TopologicalError('\033[91mERROR:\033[00m Correction does not work...\n%s is not a valid geometric object\n\t The error is: %s' %(str(rec['properties']['_ID']), shapely.validation.explain_validity(rec)))
        #print('We try to correct it')
        #rec2b = shapely.validation.make_valid(Polygon(rec['geometry']['coordinates'][0]))
        # Check à améliorer, il faut que ce soit un Polygon, et non un MultiPolygon...
        #if not rec2b.is_valid:
        #    raise TopologicalError('ERROR: Correction failed...\n%s is not a valid geometric object\n\t The error is: %s' %(str(rec['properties']['_ID']), shapely.validation.explain_validity(rec)))
        #else:
        #    rec2['geometry']['coordinates'][0] = list(rec2b.exterior.coords)

    # Find where there is the error if possible  
    #Diagnostics
    #validation.explain_validity(ob):
    #Returns a string explaining the validity or invalidity of the object.
    #The messages may or may not have a representation of a problem point that can be parsed out.
    #coords = [(0, 0), (0, 2), (1, 1), (2, 2), (2, 0), (1, 1), (0, 0)]
    #p = Polygon(coords)
    #from shapely.validation import explain_validity
    #shapely.validation.explain_validity(p)
    #'Ring Self-intersection[1 1]'
    #shapely.validation.make_valid(ob)
    #Returns a valid representation of the geometry, if it is invalid. If it is valid, the input geometry will be returned.

    #In many cases, in order to create a valid geometry, the input geometry must be split into multiple parts or multiple geometries. If the geometry must be split into multiple parts of the same geometry type, then a multi-part geometry (e.g. a MultiPolygon) will be returned. if the geometry must be split into multiple parts of different types, then a GeometryCollection will be returned.
    #For example, this operation on a geometry with a bow-tie structure:
    #from shapely.validation import make_valid
    #coords = [(0, 0), (0, 2), (1, 1), (2, 2), (2, 0), (1, 1), (0, 0)]
    #p = Polygon(coords)
    #make_valid(p)
    #<MULTIPOLYGON (((1 1, 0 0, 0 2, 1 1)), ((2 0, 1 1, 2 2, 2 0)))>
    #Yields a MultiPolygon with two parts, and sometimes area + line:

    return rec2

#################################################################################################
def cutareas(pathshp, outlines, outputspath):
    """
    Function to cut shapefiles areas with the outline to only keep the lines inside the outline

    Args:
        pathshp (str)           : path where are stored output shp from Therion
        outlines (geopandas obj): the outline shapefile
        outputspath (str)       : path where to copy the gpkg files
    """

    print('\033[1;32mWorking with areas...\033[0m')
    # 2- Validate the outline and Areas shapefile
    #for rec in outlines:
    #    rec2 = validate('outline2d.shp', rec)
    #    # update correction --> To do ?
    #    #if rec2 != rec:
    #for rec in areas:
    #    rec2 = validate('areas2d.shp', rec)
    #    # update correction
    #    #if rec2 != rec:

    #   Read the Line Shapefile
    # areas = gpd.read_file(pathshp + 'areas2d.shp', driver = 'ESRI shapefile')
    areas = gpd.read_file(pathshp + 'areas2d.gpkg')

   # Corriger les erreurs de topologie dans les lignes avant traitement
    # areas = fix_topology(areas)

    # Extract the intersections between outlines and lines
    # be careful, for this operation, geopandas needs to work with rtree and not pygeos
    #   --> uninstall pygeos and install rtree
    try:
        areasIN = areas.overlay(outlines, how = 'intersection')
    except:
        print('ERROR: 1) uninstall pygeos and install rtree\n\t2) check your polygons validity')
        import rtree
        print ('\tYou may check the validity of your polygons with the verify function in QGIS')
        areasIN = areas.overlay(outlines, how = 'intersection')
        
    # Removes inner lines that have different id and scrap_id
    areasIN = areasIN[areasIN['_SCRAP_ID'] == areasIN ['_ID']]

    # Save output
    #areasIN.to_file("areas2dMasekd.gpkg", driver = "GPKG", encoding = 'utf8')
    areasIN.to_file(outputspath + "areas2dMasekd.gpkg", driver = "GPKG")

    return

#################################################################################################
def repair_geometry(geom):
    """Répare une géométrie en appliquant un buffer de zéro si elle est invalide."""
    if geom is None:
        return None  # Si la géométrie est déjà None, on ne fait rien.

    try:
        # Vérifier si la géométrie est valide
        if not geom.is_valid:
            # Appliquer un buffer de zéro pour corriger la géométrie
            return geom.buffer(0)            
        return geom
    except TopologicalError:
        # Gérer les erreurs topologiques si une géométrie est impossible à réparer
        print(f"Erreur topologique pour la géométrie: {geom}")
        return None  # Renvoie None pour les géométries non réparables

#################################################################################################
def fix_topology(geodf):
    """Fonction pour corriger les erreurs de topologie dans un GeoDataFrame"""
    
   # Compteur pour les géométries corrigées
    corrected_count = 0

    def count_and_repair(geom):
        """Compter et réparer les géométries invalides"""
        nonlocal corrected_count
        if geom and not geom.is_valid:
            corrected_count += 1
        return repair_geometry(geom)

    # Appliquer la réparation sur toutes les géométries du GeoDataFrame
    geodf['geometry'] = geodf['geometry'].apply(count_and_repair)

    # Filtrer les géométries invalides restantes
    geodf = geodf[geodf['geometry'].notnull()]  # Exclure les géométries None
    geodf = geodf[geodf.is_valid]  # Garder seulement les géométries valides

    # Afficher le nombre d'erreurs corrigées
    if corrected_count > 0 : print(f"Nombre d'erreurs topologiques corrigées: {corrected_count}")
    else : print(f"Aucune erreur de topologiques corrigée")
    

    return geodf



#################################################################################################
def cutLines(pathshp, outlines, outputspath):
    """
    Function to cut shapefiles lines with the outline to only keep the lines inside the outline

    Args:
        pathshp (str)           : path where are stored output shp from Therion
        outlines (geopandas obj): the outline shapefile
        outputspath (str)       : path where to copy the gpkg files
    """

    print('\033[1;32mWorking with lines...\033[0m')
    #   Read the Line Shapefile
    # lines = gpd.read_file(pathshp + 'lines2d.shp', driver = 'ESRI shapefile')  # [Note Alex]
    lines = gpd.read_file(pathshp + 'lines2d.gpkg')  # [Note Alex]
    
    # lines = fix_topology(lines)
    
       # Vérifier si outlines est un GeoDataFrame
    if not isinstance(outlines, gpd.GeoDataFrame):
        print("outlines n'est pas un GeoDataFrame. Tentative de conversion...")
        outlines = gpd.read_file(outlines)  # Lire un fichier shapefile si outlines est une chaine de caractères

    # Corriger les erreurs de topologie dans outlines avant traitement
    # outlines = fix_topology(outlines)
    
    # lines = gpd.read_file(pathshp + 'lines2d.shp')  # [Note Alex]
    # Extract lines that are not masked by the outline
    linesOUT = pd.concat((lines[lines['_TYPE'] == 'centerline'],
                          lines[lines['_TYPE'] == 'water_flow'],
                          lines[lines['_TYPE'] == 'label'],
                          lines[lines['_CLIP'] == 'off']),
                          ignore_index=True)

    # Extract lines will be masked by the outline
    linesIN = lines[lines['_CLIP'] != 'off']
    linesIN = linesIN[linesIN['_TYPE'] != 'centerline']
    linesIN = linesIN[linesIN['_TYPE'] != 'water_flow']
    linesIN = linesIN[linesIN['_TYPE'] != 'label']

    # Extract the intersections between outlines and lines
    # be careful, for this operation, geopandas needs to work with rtree and not pygeos
    #   --> uninstall pygeos and install rtree
    try:
        # outlines = outlines.buffer(0)  #  [Note Alex] Réparer les géométries invalides
        linesIN = linesIN.overlay(outlines, how = 'intersection', keep_geom_type=True)
    except:
        print('\033[91mERROR: 1\033[00m) uninstall pygeos and install rtree\n\t2) check your polygons validity')
        import rtree
        print ('\tYou may check the validity of your polygons with the verify function in QGIS')
        linesIN = linesIN.overlay(outlines, how = 'intersection', keep_geom_type=True)
        print('TEST')

    # Removes inner lines that have different id and scrap_id
    linesIN = linesIN[linesIN['_SCRAP_ID'] == linesIN ['_ID']]

    # Merge the IN and OUT database 
    linesTOT = pd.concat((linesOUT, linesIN),
                           ignore_index=True)

    # Save output
    #linesTOT.to_file("lines2dMasekd.gpkg", driver="GPKG", encoding = 'utf8')
    linesTOT.to_file(outputspath + "lines2dMasekd.gpkg", driver="GPKG")

    return

#################################################################################################
def AddAltPoint(pathshp, outputspath):
    """
    Function to add the altitude of the stations and entrances in the attribut table

    Args:
        pathshp (str)    : path where are stored output shp from Therion
        outputspath (str): path where to copy the gpkg files
    """


    print('\033[1;32mWorking with points...\033[1;32m')

    # Definition des altitudes des entrées supérieures des réseaux à plusieurs entrées
    EntreeSupp = {'JB'     : 2333,  # Entrée C37
                  'CP'     : 2136,  # Entrée CP16
                  'LP9'    : 2299,  # Entrée LP9
                  'CP6'    : 2182,  # Entrée CP53
                  'CP62'   : 1960,  # Entrée CP62
                  'A21'    : 1797,  # Entrée A21
                  'Mirolda': 2330   # Entrée Jockers
                  }
    # Définition des noms de réseau
    RNames = {'JB'     : 'Gouffre Jean Bernard',
              'CP'     : 'Réseau de la Combe aux Puaires',
              'LP9'    : 'LP9 - CP39',
              'CP6'    : 'CP6 - CP53',
              'CP62'   : 'CP62 - CP63',
              'A21'    : 'A21 -A24',
              'Mirolda': 'Réseau Lucien-Bouclier - Mirolda'  
              }
    # Définition des noms de systèmes
    SNames = {'SynclinalJB'    : 'Système du Jean-Bernard',
              'SystemeCP'      : 'Système de la Combe aux Puaires',
              'SystemeAV'      : 'Système des Avoudrues',
              'SystemeA21'     : 'Système du A21',
              'SystemMirolda'  : 'Système du Criou - Mirolda',
              'SystemeBossetan': 'Système de Bossetan',
              'sources'        : 'Résurgences',
              'tuet'           : 'Système du Tuet',
              'eauxfroides'    : 'Système des Eaux Froides'
              }
    # Open the text file with the coordinates of the caves
    #   This text file (Caves.txt) should be build with Therion compilation
    #   and stored in the output's shapefiles folder
    #      export cave-list -location on -o Outputs/SHP/Caves.txt
    f = open(pathshp + 'Caves.txt', 'r').readlines() 

    # Make a new shapefile instance
    with fiona.open(pathshp + 'points2d.shp', 'r') as inputshp:
        # Créer le nouveau schéma des shapefiles
        newschema = inputshp.schema
        newschema['properties']['_CAVE'] = 'str'
        newschema['properties']['_SYSTEM'] = 'str'
        newschema['properties']['_ALT'] = 'str:4'
        newschema['properties']['_DEPTH'] = 'float'
        newschema['properties']['_EASTING'] = 'float'
        newschema['properties']['_NORTHING'] = 'float'
        # Open the output shapefile
        #with fiona.open(inputfile[:-4] + 'Alt.shp', 'w', crs=inputshp.crs, driver='ESRI Shapefile', schema=newschema) as ouput:
        #with fiona.open('points2dAlt.gpkg', 'w', crs=inputshp.crs, driver='GPKG', schema=newschema, encoding = 'utf8') as ouput:
        with fiona.open(outputspath + 'points2dAlt.gpkg', 'w', crs=inputshp.crs, driver='GPKG', schema=newschema) as ouput:
            with alive_bar(len(inputshp), title = "\x1b[32;1m- Processing stations...\x1b[0m", length = 20) as bar:
                # do a loop on the stations
                for rec in inputshp:
                    # Copy the schema from the input data
                    g = rec
                    g['properties']['_CAVE'] = ''
                    g['properties']['_SYSTEM'] = ''
                    g['properties']['_DEPTH'] = ''

                    # Add Alt, Easting, Northing
                    g['properties']['_ALT'] = str(round(float(rec['geometry']['coordinates'][2])))
                    g['properties']['_EASTING'] = float(rec['geometry']['coordinates'][0])
                    g['properties']['_NORTHING'] = float(rec['geometry']['coordinates'][1])

                    if rec['properties']['_TYPE'] == 'station' and rec['properties']['_STSURVEY'] != None:
                        # Find system
                        system = rec['properties']['_STSURVEY'].split('.')[-2]
                        g['properties']['_SYSTEM'] = SNames[system]
                    
                        # Find Cave
                        xxx = rec['properties']['_STSURVEY'].split('.')
                        while len(xxx) < 4:
                    	    xxx.append('junk')
                        if 'trous' in xxx[0] or SNames[system] == 'Résurgences' or 'sources' in xxx[0]:
                    	    g['properties']['_CAVE'] = rec['properties']['_STNAME']
                    	    g['properties']['_DEPTH'] = 0
                    
                        elif 'eauxfroides' in xxx[-3]:
                    	    g['properties']['_CAVE'] = 'Résurgence des Eaux Froides'
                    	    g['properties']['_DEPTH'] = 0

                        elif 'tuet' in xxx[-4]:
                    	    g['properties']['_CAVE'] = 'Tuet'
                    	    g['properties']['_DEPTH'] = 0

                        elif 'ReseauCP' in xxx[-4]:
                    	    g['properties']['_CAVE'] = RNames['CP']
                    	    g['properties']['_DEPTH'] = EntreeSupp['CP'] - float(rec['geometry']['coordinates'][2])
                    
                        elif 'LP9' in xxx[-4]:
                    	    g['properties']['_CAVE'] = RNames['LP9']
                    	    g['properties']['_DEPTH'] = EntreeSupp['LP9'] - float(rec['geometry']['coordinates'][2])
                    
                        elif 'CP6' in xxx[-4]:
                    	    g['properties']['_CAVE'] = RNames['CP6']
                    	    g['properties']['_DEPTH'] = EntreeSupp['CP6'] - float(rec['geometry']['coordinates'][2])
                    
                        elif 'CP62' in xxx[-4]:
                    	    g['properties']['_CAVE'] = RNames['CP62']
                    	    g['properties']['_DEPTH'] = EntreeSupp['CP62'] - float(rec['geometry']['coordinates'][2])
                    
                        elif xxx[-3] == 'Jean-Bernard':
                            #g['pfileroperties']['_CAVE'] = rec['properties']['_STSURVEY'].split('.')[-3]
                            g['properties']['_CAVE'] = RNames['JB']
                            g['properties']['_DEPTH'] = EntreeSupp['JB'] - float(rec['geometry']['coordinates'][2])
                    
                        elif 'A21' in xxx[-4]:
                    	    g['properties']['_CAVE'] = RNames['A21']
                    	    g['properties']['_DEPTH'] = EntreeSupp['A21'] - float(rec['geometry']['coordinates'][2])

                        elif 'Mirolda' in xxx[-3]:
                    	    g['properties']['_CAVE'] = RNames['Mirolda']
                    	    g['properties']['_DEPTH'] = EntreeSupp['Mirolda'] - float(rec['geometry']['coordinates'][2])

                        else:
                            g['properties']['_CAVE'] = xxx[-4]
                            if g['properties']['_CAVE'] == 'A22':
                                g['properties']['_CAVE'] = 'A(V)22'
                            #g['properties']['_DEPTH'] = 0
                            # Trouver l'altitude de l'entrée !!!!
                            for line in f:
                                if g['properties']['_CAVE'] in line and line.split('\t')[6] != '\n':
                                    altmax = float(line.split('\t')[6])
                            g['properties']['_DEPTH'] = altmax - float(rec['geometry']['coordinates'][2])					
                    
                    # Write record
                    ouput.write (g)
                    # Update progress bar
                    bar()
    return


#################################################################################################
def shp2gpkg(pathshp, outputspath):
    """
    function to convert shp files into gpkg files

    Args:
        pathshp (str)    : path where are stored output shp from Therion
        outputspath (str): path where to copy the gpkg files
    """

    # files to be converted
    # files = ['outline2d', 'shots3d', 'walls3d']
    files = ['outline2d']


    print('shp2gpkg : ', files)
    
    with alive_bar(len(files), title = "\x1b[32;1m- Processing shp2gpkg...\x1b[0m", length = 20) as bar:
        for fname in files :
            if fname == 'walls3d':
                print('shp2gpkg does not support walls3d files...\n\t I am only copying the shp file into the right folder')
                for ftype in ['.shp', '.dbf', '.prj', '.shx']:
                    shutil.copy2(pathshp + fname + ftype, outputspath + fname + ftype)
                #pass
                #input = gpd.read_file(fname + '.shp', layer = 'walls3d', driver = 'ESRI shapefile')
                #input.to_file(fname + ".gpkg", driver="GPKG", encoding = 'utf8')
                #with fiona.open(fname + '.shp', 'r') as inputshp:
                #    with fiona.open(fname + '.gpkg', 'w', crs=inputshp.crs, driver='GPKG', schema=inputshp.schema, encoding = 'utf8') as ouput:
                #        for rec in inputshp:
                #            # Write record
                #            ouput.write (g)
            else:
                # input = gpd.read_file(pathshp + fname + '.shp', driver = 'ESRI shapefile')
                input = gpd.read_file(pathshp + fname + '.shp', encoding = 'utf8')
                #input.to_file(fname + ".gpkg", driver="GPKG", encoding = 'utf8')
                # input.to_file(outputspath + fname + ".gpkg", driver="GPKG")
                input.to_file(outputspath + fname + ".gpkg", encoding = 'utf8')
            #input.to_file(fname + ".gpkg", driver="GPKG")
            #update bar
            bar()

    return

#################################################################################################    
def file_shp2gpkg(pathshp, infile, outputspath, outfile ):
    """
    Function to convert shp files into gpkg files using Fiona.

    Args:
        pathshp (str): Path where the input shp files are stored.
        file (str): Name of the file to be converted (without extension).
        outputspath (str): Path where the output gpkg files will be saved.
    """
    try:
        # Configuration de l'environnement Fiona pour accepter les géométries non fermées
        with Env(OGR_GEOMETRY_ACCEPT_UNCLOSED_RING="YES"):

            input_shp = os.path.join(pathshp, infile + '.shp')
            output_gpkg = os.path.join(outputspath, outfile + '.gpkg')

            # Vérification que le fichier source existe
            if not os.path.exists(input_shp):
                raise FileNotFoundError(f"\t\033[91mError: the file \033[0m{input_shp}\033[91m did not exist.")

            # Lecture du fichier Shapefile
            with fiona.open(input_shp, 'r') as source:
                # Affichage du nombre d'objets et de leur type
                num_features = len(source)
                geometry_type = source.schema['geometry']

                # Vérification que le driver GPKG est disponible
                if 'GPKG' not in fiona.supported_drivers:
                    raise RuntimeError("\t\033[91mError: The GPKG dirver is not supported by Fiona.\033[0m")

                # Création du fichier GeoPackage
                with fiona.open(
                    output_gpkg,
                    'w',
                    driver='GPKG',
                    schema=source.schema,
                    crs=source.crs
                ) as destination:
                    for feature in source:
                        destination.write(feature)

            print(f'\033[1;32mConversion OK, \033[32m file : \033[0m{pathshp}{infile}.shp\033[32m to : \033[0m{outputspath}{outfile}.gpkg, type {geometry_type} : {num_features}')


    except FileNotFoundError as e:
        print(f"\t\033[91mError : \033[0m{e}", file=sys.stderr)
    except RuntimeError as e:
        print(f"\t\033[91mError : \033[0m{e}", file=sys.stderr)
    except fiona.errors.FionaError as e:
        print(f"\t\033[91mError read/write file : \033[0m{e}", file=sys.stderr)
    except Exception as e:
        print(f"\t\033[91mError unknow : \033[0m{e}", file=sys.stderr)

#################################################################################################
def count_topology_errors(file_path):
    """
    Analyzes a shapefile for topology errors and counts them by type,
    while listing the record numbers associated with each error.
    Also returns the total number of errors.

    Args:
        file_path (str): Path to the shapefile to analyze.

    Returns:
        tuple: 
            - dict: A dictionary with the error types as keys and a list of record indices as values.
            - int: The total number of errors found.
    """
    error_details = {}
    record_types = {'Point': 0, 'LineString': 0, 'Polygon': 0, 'MultiPoint': 0, 'MultiLineString': 0, 'MultiPolygon': 0}
    total_records = 0
    total_errors = 0

    try:
        # Open the shapefile in read mode
        with fiona.open(file_path, "r") as src:
            for i, record in enumerate(src):
                total_records += 1
                geometry = shape(record['geometry'])

                # Count the type of geometry
                geom_type = geometry.geom_type
                if geom_type in record_types:
                    record_types[geom_type] += 1
                else:
                    record_types[geom_type] = 1  # Add new geometry type if not found

                try:
                    # Validate the geometry and explain any issues
                    validity_explanation = explain_validity(geometry)

                    if validity_explanation != "Valid Geometry":
                        # Extract the type of error
                        error_type = validity_explanation.split(" ")[0]  # First word of the explanation
                        total_errors += 1  # Increment total errors

                        # Add the record index to the error details
                        if error_type in error_details:
                            error_details[error_type].append(i)
                        else:
                            error_details[error_type] = [i]

                except Exception as e:
                    print(f"\033[91mError processing record \033[0m{i}: {e}")
                    
          
        # Display the total number of records and their types
        if total_errors == 0 : print(f"\033[1;32mFile: \033[0m{file_path}\033[32m, records : \033[0m{total_records}\033[32m, no errors found: \033[0m")
        else : print(f"\n\033[1;32mFile: \033[0m{file_path}\033[32m, records : \033[0m{total_records},\033[91m errors found: \033[0m{total_errors}")
        for geom_type, count in record_types.items():
            if count != 0 : print(f"\tType {geom_type} : {count} records")
        
        # Print the results
        if error_details:
            print("\t\033[91mTopology errors found:\033[0m")
            for error_type, indices in error_details.items():
                print(f"\t\033[91mRecords : \033[0m{', '.join(map(str, indices))}\033[91m Erreur type : \033[0m{error_type}\033[91m : \033[0m{len(indices)}\033[91m occurrences\033[0m")
        
        # else:
        #     print("\t\033[1;32mNo topology errors found.\t\033[0m")


        return error_details, total_errors

    except Exception as e:
        print(f"\033[91mError analyzing shapefile: \033[0m{file_path}\033[91m Code : \033[0m{e}")
        return {}, 0
 
#################################################################################################
def fix_geometries_fiona(input_shp, output_shp):
    """
    Fixes geometries in a shapefile using Fiona and Shapely.
    
    Parameters:
    - input_shp (str): Path to the input shapefile.
    - output_shp (str): Path to the output corrected shapefile.
    
    Returns:
    - None (saves the corrected file).
    """
    try:
        with fiona.open(input_shp, "r") as src:
            schema = src.schema.copy()
            crs = src.crs
            records = list(src)

        fixed_records = []
        invalid_count = 0
        fixed_count = 0
        removed_count = 0
        error_details = []

        for record in records:
            geom = shape(record["geometry"])
            if geom is None or geom.is_empty:
                removed_count += 1
                continue  # Remove empty geometries
            try:
                if not geom.is_valid:
                    invalid_count += 1
                    repaired_geom = unary_union([geom])
                    
                    # Convert GeometryCollection into a valid geometry if possible
                    if isinstance(repaired_geom, GeometryCollection):
                        repaired_geom = list(polygonize(repaired_geom))
                        repaired_geom = repaired_geom[0] if repaired_geom else None
                    
                    if repaired_geom and repaired_geom.is_valid:
                        geom = repaired_geom
                        fixed_count += 1
                    else:
                        removed_count += 1
                        continue  # If still invalid, remove it
                
                new_record = record.copy()
                new_record["geometry"] = mapping(geom)
                fixed_records.append(new_record)
            except Exception as e:
                removed_count += 1
                error_details.append(str(e))
                continue  # Skip problematic geometries
            
        if error_details:
            print("\t⚠️ Error details:")
            for error in set(error_details):
                print(f"\t\t- {error}")

        with fiona.open(output_shp, "w", driver="ESRI Shapefile", schema=schema, crs=crs) as dst:
            dst.writerecords(fixed_records)

        print(f'\033[1;32mCorrection, \033[32m file : \033[0m{input_shp}.shp\033[32m to : \033[0m{output_shp}')
        print(f"\t🔍 Invalid geometries before correction: {invalid_count}")
        print(f"\t🔧 Fixed geometries: {fixed_count}")
        print(f"\t⚠️ \033[91m Removed geometries, check it ! : ⚠️ \033[0m {removed_count}")
        print(f"\t📊 Total objects after correction: {len(fixed_records)}")
    
    except Exception as e:
        print(f"\033[91mError processing the shapefile: \033[0m{e}")

def fix_geometries_pure_python(input_shp, output_shp):
    """
    Repairs geometries in a shapefile using Fiona and Shapely.

    Parameters:
    - input_shp (str): Path to the input shapefile.
    - output_shp (str): Path to the output shapefile after correction.

    Returns:
    - None (saves the corrected file).
    """
    try:
        # Configuration de l'environnement Fiona pour accepter les géométries non fermées
        with Env(OGR_GEOMETRY_ACCEPT_UNCLOSED_RING="YES"):
            print(f"✅ Loading file: {input_shp}")

            # Ouvrir le fichier Shapefile en lecture
            with fiona.open(input_shp, 'r') as source:
                # Vérifier le nombre d'objets et le type de géométrie
                num_features = len(source)
                geometry_type = source.schema['geometry']
                print(f"ℹ️ Number of objects in the file: {num_features}")
                print(f"ℹ️ Geometry type: {geometry_type}")

                # Initialisation des compteurs d'erreurs
                invalid_before = 0
                invalid_after = 0
                fixed_geometries = 0
                removed_geometries = 0

                # Préparer le schéma de sortie
                output_schema = source.schema

                # Ouvrir le fichier Shapefile en écriture
                with fiona.open(
                    output_shp,
                    'w',
                    driver=source.driver,
                    schema=output_schema,
                    crs=source.crs
                ) as output:
                    # Parcourir chaque objet dans le fichier source
                    for feature in source:
                        geom = shape(feature['geometry'])

                        # Vérifier si la géométrie est invalide avant correction
                        if not geom.is_valid:
                            invalid_before += 1

                        # Fonction pour corriger la géométrie
                        def fix_geometry(geom):
                            if geom is None or geom.is_empty:
                                return None  # Supprimer les géométries vides
                            try:
                                if not geom.is_valid:
                                    geom = unary_union([geom])  # Corriger les chevauchements
                                    geom = next(polygonize(geom))  # Reformuler en polygones si nécessaire
                                return geom
                            except Exception:
                                return None  # Si impossible à réparer, retourner None

                        # Appliquer la correction
                        fixed_geom = fix_geometry(geom)

                        # Vérifier si la géométrie est invalide après correction
                        if fixed_geom is None or fixed_geom.is_empty:
                            removed_geometries += 1
                            continue  # Ignorer les géométries irrécupérables

                        if not fixed_geom.is_valid:
                            invalid_after += 1
                        else:
                            fixed_geometries += 1

                        # Mettre à jour la géométrie dans l'objet
                        feature['geometry'] = mapping(fixed_geom)
                        output.write(feature)

                # Afficher les résultats de la correction
                print(f"🔍 Invalid geometries before correction: {invalid_before}")
                print(f"🔍 Fixed geometries: {fixed_geometries}")
                print(f"🔍 Invalid geometries after correction: {invalid_after}")
                print(f"🔍 Removed geometries (irreparable): {removed_geometries}")
                print(f"📊 Total objects after correction: {num_features - removed_geometries}")

                print(f"✅ Corrected file saved to: {output_shp}")

    except FileNotFoundError:
        print(f"❌ Error: Input file not found: {input_shp}", file=sys.stderr)
    except fiona.errors.FionaError as e:
        print(f"❌ Error reading/writing the file: {e}", file=sys.stderr)
    except Exception as e:
        print(f"❌ Unexpected error during processing: {e}", file=sys.stderr)


def OLD2fix_geometries_pure_python(input_shp, output_shp):
    """
    Repairs geometries in a shapefile using Fiona and Shapely.

    Parameters:
    - input_shp (str): Path to the input shapefile.
    - output_shp (str): Path to the output shapefile after correction.

    Returns:
    - None (saves the corrected file).
    """
    try:
        # Configuration de l'environnement Fiona pour accepter les géométries non fermées
        with Env(OGR_GEOMETRY_ACCEPT_UNCLOSED_RING="YES"):
            print(f"✅ Loading file: {input_shp}")

            # Ouvrir le fichier Shapefile en lecture
            with fiona.open(input_shp, 'r') as source:
                # Vérifier le nombre d'objets et le type de géométrie
                num_features = len(source)
                geometry_type = source.schema['geometry']
                print(f"ℹ️ Number of objects in the file: {num_features}")
                print(f"ℹ️ Geometry type: {geometry_type}")

                # Initialisation des compteurs d'erreurs
                invalid_before = 0
                invalid_after = 0
                fixed_geometries = 0
                removed_geometries = 0

                # Préparer le schéma de sortie
                output_schema = source.schema

                # Ouvrir le fichier Shapefile en écriture
                with fiona.open(
                    output_shp,
                    'w',
                    driver=source.driver,
                    schema=output_schema,
                    crs=source.crs
                ) as output:
                    # Parcourir chaque objet dans le fichier source
                    for feature in source:
                        geom = shape(feature['geometry'])

                        # Vérifier si la géométrie est invalide avant correction
                        if not geom.is_valid:
                            invalid_before += 1

                        # Fonction pour corriger la géométrie
                        def fix_geometry(geom):
                            if geom is None or geom.is_empty:
                                return None  # Supprimer les géométries vides
                            try:
                                if not geom.is_valid:
                                    geom = unary_union([geom])  # Corriger les chevauchements
                                    geom = next(polygonize(geom))  # Reformuler en polygones si nécessaire
                                return geom
                            except Exception:
                                return None  # Si impossible à réparer, retourner None

                        # Appliquer la correction
                        fixed_geom = fix_geometry(geom)

                        # Vérifier si la géométrie est invalide après correction
                        if fixed_geom is None or fixed_geom.is_empty:
                            removed_geometries += 1
                            continue  # Ignorer les géométries irrécupérables

                        if not fixed_geom.is_valid:
                            invalid_after += 1
                        else:
                            fixed_geometries += 1

                        # Mettre à jour la géométrie dans l'objet
                        feature['geometry'] = mapping(fixed_geom)
                        output.write(feature)

                # Afficher les résultats de la correction
                print(f"🔍 Invalid geometries before correction: {invalid_before}")
                print(f"🔍 Fixed geometries: {fixed_geometries}")
                print(f"🔍 Invalid geometries after correction: {invalid_after}")
                print(f"🔍 Removed geometries (irreparable): {removed_geometries}")
                print(f"📊 Total objects after correction: {num_features - removed_geometries}")

                print(f"✅ Corrected file saved to: {output_shp}")

    except FileNotFoundError:
        print(f"❌ Error: Input file not found: {input_shp}", file=sys.stderr)
    except fiona.errors.FionaError as e:
        print(f"❌ Error reading/writing the file: {e}", file=sys.stderr)
    except Exception as e:
        print(f"❌ Unexpected error during processing: {e}", file=sys.stderr)


def fix_geometries_pure_python(input_shp, output_shp):
    """
    Corrige les erreurs de géométrie d'un fichier Shapefile et enregistre uniquement
    les objets du même type que le fichier source.
    Affiche une synthèse des modifications et un bilan des géométries par type avant et après le traitement.

    :param input_shp: Chemin du fichier Shapefile d'entrée
    :param output_shp: Chemin du fichier Shapefile de sortie
    """
    with fiona.open(input_shp, 'r') as src:
        meta = src.meta  # Métadonnées du fichier
        original_geom_type = meta['schema']['geometry'].upper()  # Type de géométrie attendu (en majuscules pour éviter les écarts de format)
        original_geom_type_simple = original_geom_type.replace('3D ', '')  # Suppression du préfixe '3D '
        fixed_features = []
        geom_counts_before = Counter()
        geom_counts_after = Counter()
        modifications = 0

        for feature in src:
            fixed_feature = dict(feature)  # Copie de l'entité
            geom = shape(feature['geometry'])
            geom_counts_before[geom.geom_type] += 1

            # Correction de la géométrie
            valid_geom = make_valid(geom)
            geom_type_fixed = valid_geom.geom_type.upper()
            geom_counts_after[geom_type_fixed] += 1

            # Vérification si la géométrie corrigée est du même type que l'original
            if geom_type_fixed == original_geom_type or geom_type_fixed == original_geom_type_simple:
                fixed_feature['geometry'] = mapping(valid_geom)
                fixed_features.append(fixed_feature)
            else:
                modifications += 1
                

    # Écriture du fichier de sortie avec uniquement les géométries du type d'origine
    if fixed_features:
        with fiona.open(output_shp, 'w', **meta) as dst:
            dst.writerecords(fixed_features)
        print(f"Correction terminée. Fichier sauvegardé sous: {output_shp}")
    else:
        print("Aucune entité valide trouvée correspondant au type original. Aucun fichier généré.")

    # Affichage de la synthèse
    print("\t--- Synthèse des corrections ---")
    print(f"\tNombre total de modifications ignorées : {modifications}")
    print("\tAvant correction :", dict(geom_counts_before))
    print("\tAprès correction (uniquement type original) :", dict(geom_counts_after))



#################################################################################################
def ThCutAreas(pathshp, outputspath):
    
    print(' ')
    print('\033[1;32m****************************************************************')
    print('Program to cut areas and lines that are intersecting the outline')
    print('        Original written by X. Robert, ISTerre')
    print('                   October 2022')
    print('                Updated by A. Pont')
    print('                   Febuary 2025')
    print('****************************************************************')
    print('\033[0m ')

    # Check if areas, lines, points2d and outline shapefiles exists...
    areaOK = True
    for fname in ['outline2d', 'lines2d', 'areas2d', 'points2d']:
        if not os.path.isfile(pathshp + fname + '.shp'):
            if fname == 'areas2d':
                areaOK = False
            else:
                print(f"\033[91mERROR:\033[00m File {(str(pathshp + fname + '.shp'))}\033[91m does not exist'\033[00m")
                return False
            
        err = count_topology_errors(pathshp + fname +  '.shp')    
        if err[1] != 0 :
            print (f'\033[91mERROR: in file \033[0m{(str(pathshp + fname + '.shp'))} \033[91m, try too fix it... \033[0m')
            fix_geometries_pure_python(pathshp + fname + '.shp', pathshp + fname +  '_fixed.shp')
            err2 = count_topology_errors(pathshp + fname +  '_fixed.shp')
            if err2[1] == 0 :
                # for ftype in ['.shp', '.dbf', '.prj', '.shx']:
                    # os.rename(pathshp + fname + ftype , pathshp + fname + '_Old' + ftype)
                    # os.rename(pathshp + fname + '_fixed' + ftype, pathshp + fname + ftype) 
                # count_topology_errors(pathshp + fname +  '.shp') 
                file_shp2gpkg(pathshp, fname + "_fixed", outputspath, fname)
            else :
                print (f'\033[91mERROR: in file \033[0m{(str(pathshp + fname + '.shp'))} \033[91m please fix it manualy with QGis... \033[0m')
                return False
        else :
            file_shp2gpkg(pathshp, fname, outputspath, fname)
            # print (f'\033[32mOK :\033[00m No erreur... {err[1]}, code {err[0]}')
       
    
    # Check if Outputs path exists
    if not os.path.exists(outputspath):
        print ('\033[91mWARNING:\033[00m ' + outputspath + ' does not exist, I am creating it...')
        os.mkdir(outputspath)

    #1- Read the outline shapefile
    
    
    # outlines = gpd.read_file(pathshp + 'outline2d.shp', driver = 'ESRI shapefile')
    outlines = gpd.read_file(outputspath + 'outline2d.gpkg')

    print('\033[1;32mCheck\033[0m')
    
    
    ## Change SHP to gpkg
    # shp2gpkg(pathshp, outputspath)
    ## Work with points
    #AddAltPoint(pathshp, outputspath)
    ## Work with lines
    cutLines(outputspath, outlines, outputspath)
    ## Work with Areas
    if areaOK:
        print ('\033[1;32mCuting areas...\033[0m')
        cutareas(outputspath, outlines, outputspath)
    else:
        print ("No areas to process...")
    
    #5- End ?

    print('')
    print('\033[1;32mUpdate point, areas and lines done.\033[0m')
    print('')

######################################################################################################
if __name__ == u'__main__':	
	###################################################
    # initiate variables
    #inputfile = 'stations3d.shp'
    pathshp = './Inputs/'
    outputspath = './Outputs/'
    ###################################################
    # Run the transformation
    
    ThCutAreas(pathshp, outputspath)
    # End...

