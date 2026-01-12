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

Written by Xavier Robert, October 2022x
Xavier.robert@ird.fr

Modifié Alex 2025 01 31 

Inputs files (16):  (.dbf, .prj, .shp, .shx)
    - points2d
    - lines2d
    - areas2d
    - outlines

En cas d'erreur corriger manuellement (QGis) les topologies des fichiers 

"""

# Do divisions with Reals, not with integers
# Must be at the beginning of the file
from __future__ import division

# Import Python modules
#import numpy as np
import sys, os, argparse, shutil 
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import filedialog
import fiona
from fiona import Env
import shapely
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, MultiPoint, Polygon, LineString, MultiLineString, MultiPolygon, Polygon
from shapely.geometry import shape, mapping, GeometryCollection
from shapely.ops import transform, unary_union, polygonize
from shapely.errors import TopologicalError
from shapely.validation import make_valid, explain_validity
from collections import Counter

#from functools import wraps
from alive_progress import alive_bar              # https://github.com/rsalmei/alive-progress	

import Lib.global_data as globalDat
from Lib.general_fonctions import setup_logger, Colors, safe_relpath, colored_help



#################################################################################################
def cutareas(pathshp, outlines, outputspath):
    """
    Function to cut shapefiles areas with the outline to only keep the lines inside the outline

    Args:
        pathshp (str)           : path where are stored output shp from Therion
        outlines (geopandas obj): the outline shapefile
        outputspath (str)       : path where to copy the gpkg files
    """

    print(f'{Colors.GREEN}Working with :{Colors.ENDC} areas2d.gpkg')
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
def cutLines(pathshp, outlines, outputspath):
    """
    Function to cut shapefiles lines with the outline to only keep the lines inside the outline

    Args:
        pathshp (str)           : path where are stored output shp from Therion
        outlines (geopandas obj): the outline shapefile
        outputspath (str)       : path where to copy the gpkg files
    """

    print(f'{Colors.GREEN}Working with :{Colors.ENDC} lines2d.gpkg')
    #   Read the Line Shapefile
    lines = gpd.read_file(pathshp + 'lines2d.gpkg')  
    # lines = fix_topology(lines)
    
       # Vérifier si outlines est un GeoDataFrame
    if not isinstance(outlines, gpd.GeoDataFrame):
        print(f"{Colors.GREEN}Outlines is not a GeoDataFrame. Attempting conversion...")
        outlines = gpd.read_file(outlines)  # Lire un fichier shapefile si outlines est une chaine de caractères
  
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
        print(f"{Colors.ERROR}ERROR: uninstall pygeos and install rtree\n\t2) check your polygons validity")
        print (f"{Colors.ERROR}You may check the validity of your polygons with the verify function in QGIS")
        linesIN = linesIN.overlay(outlines, how = 'intersection', keep_geom_type=True)
      

    # Removes inner lines that have different id and scrap_id
    linesIN = linesIN[linesIN['_SCRAP_ID'] == linesIN ['_ID']]

    # Merge the IN and OUT database 
    linesTOT = pd.concat((linesOUT, linesIN),ignore_index=True)

    # Save output
    linesTOT.to_file(outputspath + "lines2dMasekd.gpkg", driver="GPKG")

    return

#################################################################################################    
def shp2gpkg(pathshp, infile, outputspath, outfile ):
    """
    Function to convert shp files into gpkg files using Fiona.

    Args:
        pathshp (str): Path where the input shp files are stored.
        infile (str): Name of the file to be converted (without extension).
        outputspath (str): Path where the output gpkg files will be saved.
        outfile (str): Name of the output file (without extension).
    """
    try:
        # Configuration de l'environnement Fiona pour accepter les géométries non fermées
        with Env(OGR_GEOMETRY_ACCEPT_UNCLOSED_RING="YES"):

            input_shp = os.path.join(pathshp, infile + '.shp')
            output_gpkg = os.path.join(outputspath, outfile + '.gpkg')

            # Vérification que le fichier source existe
            if not os.path.exists(input_shp):
                raise FileNotFoundError(f"\t{Colors.ERROR}Error (shp2gpkg): the file {Colors.ENDC}{input_shp}{Colors.ERROR} did not exist.")


            # Lecture du fichier Shapefile
            with fiona.open(input_shp, 'r', encoding='utf-8') as source:
                
                geom_types = Counter()  # pour compter le nombre de chaque type
                has_z = set()

                for feat in source:
                    geom_type = feat["geometry"]["type"]
                    geom_types[geom_type] += 1

                    coords = feat["geometry"]["coordinates"]
                    
                    # Vérifie si la géométrie a un Z                    
                    def check_z(coords):
                        """
                        Détecte la présence d'une coordonnée Z
                        quelle que soit la profondeur de la géométrie
                        """
                        if isinstance(coords, (list, tuple)):
                            # Cas Point : (x,y) ou (x,y,z)
                            if len(coords) in (2, 3) and all(isinstance(c, (int, float)) for c in coords):
                                return len(coords) == 3

                            # Cas Line / Polygon / Multi*
                            for c in coords:
                                if check_z(c):
                                    return True

                        return False        

                    if check_z(coords):
                        has_z.add(True)
                    else:
                        has_z.add(False)

                print(
                    f"{Colors.GREEN}File conversion to GPKG: {Colors.ENDC}{input_shp}"
                    f"{Colors.GREEN}, geometries found: {Colors.ENDC}{dict(geom_types)}"
                    f"{Colors.GREEN}, with altitude: {Colors.ENDC}{has_z}"
                )


                # Affichage du nombre d'objets et de leur type
                num_features = len(source)
                geometry_type = source.schema['geometry']

                # Vérification que le driver GPKG est disponible
                if 'GPKG' not in fiona.supported_drivers:
                    raise RuntimeError(f"{Colors.ERROR}Error: The GPKG driver is not supported by Fiona{Colors.ENDC}")

                # Création du fichier GeoPackage
                with fiona.open( output_gpkg, 'w', driver='GPKG', schema=source.schema, crs=source.crs, encoding='utf-8') as destination:
                    for feature in source:
                        destination.write(feature)

            print(f'{Colors.GREEN}Conversion to GPKG OK, {Colors.GREEN} file : {Colors.ENDC}{pathshp}{infile}.shp{Colors.GREEN} to : {Colors.ENDC}{outputspath}{outfile}.gpkg, type {geometry_type} : {num_features}')


    except FileNotFoundError as e:
        print(f"{Colors.ERROR}Error (shp2gpkg): {Colors.ENDC}{e}", file=sys.stderr)
    
    except RuntimeError as e:
        print(f"{Colors.ERROR}Error (shp2gpkg): {Colors.ENDC}{e}", file=sys.stderr)
    
    except fiona.errors.FionaError as e:
        print(f"{Colors.ERROR}Error read/write file (shp2gpkg): {Colors.ENDC}{e}", file=sys.stderr)
    
    except Exception as e:
        print(f"{Colors.ERROR}Error unknown (shp2gpkg): {Colors.ENDC}{e}", file=sys.stderr)

#################################################################################################    
def poly_rock(infile, outfile):
    """
    Converts line features from the input GeoPackage file into closed polygons,
    and saves the valid ones to an existing layer in the output GeoPackage.
    Only features with the attribute _Type equal to 'rock-edge' or 'rock-border' are considered.
    """
    
    # Load the input layer (assumed to be a line layer)
    gdf = gpd.read_file(infile, encoding='utf-8')  # Adjust layer name if needed
    
    # Filter features based on _Type attribute
    gdf = gdf[gdf['_TYPE'].isin(['rock-edge', 'rock-border'])]
    
    # Attempt to convert LineStrings to Polygons
    polygons = []
    for _, row in gdf.iterrows():
        geom = row.geometry
        if isinstance(geom, LineString) and geom.is_ring:
            new_row = row.copy()
            new_row['geometry'] = Polygon(geom)
            polygons.append(new_row)
    
    # Create a GeoDataFrame from the valid polygons
    if polygons:
        poly_gdf = gpd.GeoDataFrame(polygons, geometry='geometry', crs=gdf.crs)
        
        # Load existing output data if it exists
        try:
            existing_gdf = gpd.read_file(outfile, encoding='utf-8')
            poly_gdf = gpd.pd.concat([existing_gdf, poly_gdf], ignore_index=True)
        except Exception:
            pass  # If file doesn't exist, create a new one
        
        # Save updated data to the output GeoPackage
        poly_gdf.to_file(outfile, driver='GPKG', encoding='utf-8')  # Adjust layer name if needed
        
        print(f"{Colors.GREEN}Added {Colors.ENDC}{len(polygons)} {Colors.GREEN}polygons to {Colors.ENDC}{outfile}.")
    else:
        print(f"{Colors.ERROR}No valid closed polylines found.")
    
#################################################################################################
def count_topology_errors(file_path):
    """
    Analyse un shapefile pour détecter les erreurs topologiques et compte les occurrences par type.
    
    Args:
        file_path (str): Chemin vers le shapefile à analyser.
    
    Returns:
        tuple:
            - dict: clé = type d'erreur, valeur = liste des indices de records concernés
            - int: nombre total d'erreurs détectées
    """
    error_details = {}
    record_types = {}
    total_records = 0
    total_errors = 0
    try:
        if not os.path.exists(file_path):
            print(f"{Colors.ERROR}File not found: {Colors.ENDC}{file_path}")
            return {}, -1
   
        with fiona.open(file_path, "r") as src:
            for i, record in enumerate(src):
                total_records += 1

                # Vérifier si la géométrie est présente
                if record is None or record.get('geometry') is None:
                    props = record.get('properties', {})
                    print(f"{Colors.ERROR}Error in file {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR}, record {Colors.ENDC}{i+1}{Colors.ERROR} has no geometry, correct it : "
                          f"_ID: {Colors.ENDC}{props.get('_ID')}{Colors.ERROR}, _NAME: {Colors.ENDC}{props.get('_NAME')}{Colors.ERROR}, _SURVEY: {Colors.ENDC}{props.get('_SURVEY')}{Colors.ENDC}")
                    continue

                # Créer l'objet Shapely
                try:
                    geometry = shape(record['geometry'])
                
                except Exception as e:
                    props = record.get('properties', {})
                    print(f"{Colors.ERROR}Error in file {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR},Cannot create shape for record {Colors.ENDC}{i+1}{Colors.ERROR}: {Colors.ENDC}{e}{Colors.ERROR}"
                          f"_ID: {Colors.ENDC}{props.get('_ID')}{Colors.ERROR}, _NAME: {Colors.ENDC}{props.get('_NAME')}{Colors.ERROR}, _SURVEY: {Colors.ENDC}{props.get('_SURVEY')}{Colors.ENDC}")
                    continue

                # Ignorer les géométries vides
                if geometry.is_empty:
                    print(f"{Colors.WARNING}Warning, file {Colors.ENDC}{safe_relpath(file_path)}{Colors.WARNING},Record {i+1} has empty geometry. Skipping.{Colors.ENDC}")
                    continue

                # Comptage des types de géométrie
                geom_type = geometry.geom_type
                record_types[geom_type] = record_types.get(geom_type, 0) + 1

                # Vérifier la validité topologique
                try:
                    validity_explanation = explain_validity(geometry)
                    
                    if validity_explanation != "Valid Geometry":
                        total_errors += 1
                        # Conserver l'explication complète comme type d'erreur
                        error_details.setdefault(validity_explanation, []).append(i)
                
                except Exception as e:
                    print(f"{Colors.ERROR}Error in file {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR}, validating geometry for record {Colors.ENDC}{i+1}{Colors.ERROR}: {Colors.ENDC}{e}{Colors.ENDC}")
                    
                
            print(f"{Colors.GREEN}Geometry num: {Colors.ENDC}{i+1}{Colors.YELLOW}, types found: {Colors.ENDC}{record_types}")

        # Affichage du résumé
        if total_errors == 0:
            print(f"{Colors.GREEN}File error check OK: {Colors.ENDC}{safe_relpath(file_path)}{Colors.GREEN}, "
                  f"records: {Colors.ENDC}{total_records}{Colors.GREEN}, no errors found")
        
        else:
            print(f"{Colors.ERROR}File error check NOK: {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR}, "
                  f"records: {Colors.ENDC}{total_records}{Colors.ERROR}, total errors: {Colors.ENDC}{total_errors}")
            
            # for err_type, indices in error_details.items():
            #     print(f"{Colors.ERROR}Detail error in file {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR}, {Colors.ENDC}{err_type} "
            #           f"{Colors.ERROR}occurrences: {Colors.ENDC}{len(indices)}{Colors.ENDC}")

        # Optionnel : afficher le détail des types de géométrie
        print(f"{Colors.GREEN}Geometry in file: {Colors.ENDC}{safe_relpath(file_path)}{Colors.GREEN}, types found: {Colors.ENDC}{record_types}")

        return error_details, total_errors

    except Exception as e:
        print(f"{Colors.ERROR}Topology error when analyzing the shapefile: {Colors.ENDC}"
              f"{safe_relpath(file_path)}{Colors.ERROR}, code: {Colors.ENDC}{e}")
        return {}, -1

#################################################################################################
def fix_geometries(input_shp, output_shp):
    """
    Fixes geometry errors in a Shapefile and saves only objects of the same type as the source file.
    Displays a summary of the modifications and a report of geometries by type before and after processing.

    :param input_shp: Path to the input Shapefile
    :param output_shp: Path to the output Shapefile
    """
    
    try :  
        with fiona.open(input_shp, 'r') as src:
            meta = src.meta  # File metadata
            original_geom_type = meta['schema']['geometry'].upper()  # Expected geometry type (in uppercase to avoid format discrepancies)
            original_geom_type_simple = original_geom_type.replace('3D ', '')  # Remove '3D ' prefix
            fixed_features = []
            geom_counts_before = Counter()
            geom_counts_after = Counter()
            modifications = 0
            error_details = {}
            corrected = 0
            i = 0

            for feature in src:
                fixed_feature = dict(feature)  # Copy the feature
                geom = shape(feature['geometry'])
                geom_type = geom.geom_type.upper()
                geom_counts_before[geom_type] += 1

                # Fix the geometry
                valid_geom = make_valid(geom)
                
                geom_type_fixed = valid_geom.geom_type.upper()
                
                geom_counts_after[geom_type_fixed] += 1

                # Check if the fixed geometry is of the same type as the original
                if geom_type_fixed == original_geom_type or geom_type_fixed == original_geom_type_simple:
                    fixed_feature['geometry'] = mapping(valid_geom)
                    fixed_features.append(fixed_feature)
                
                else:
                    modifications += 1
                    
                    try:
                        # Validate the geometry and explain any issues
                        validity_explanation = explain_validity(geom)

                        if validity_explanation != "Valid Geometry":
                            # Extract the type of error
                            error_type = validity_explanation.split(" ")[0]  # First word of the explanation

                            # Add the record index to the error details
                            if error_type in error_details:
                                error_details[error_type].append(i)
                            
                            else:
                                error_details[error_type] = [i]
                            
                            if error_type=="Too" : corrected += 1
                            
                            i += 1
                            
                        else :
                            props = feature.get('properties', {})
                            print(f"{Colors.ERROR}Error in file {Colors.ENDC}{safe_relpath(input_shp)}{Colors.ERROR},correct it manually, "
                                f"_ID: {Colors.ENDC}{props.get('_ID')}{Colors.ERROR}, _NAME: {Colors.ENDC}{props.get('_NAME')}{Colors.ERROR}, _SURVEY: {Colors.ENDC}{props.get('_SURVEY')}{Colors.ENDC}")
                                            

                    except Exception as e:
                        print(f"{Colors.ERROR}Error processing record {Colors.ENDC}: {e}")
                    

        # Write the output file with only geometries of the original type
        if fixed_features:
            with fiona.open(output_shp, 'w', **meta) as dst:
                dst.writerecords(fixed_features)
                
            # print(f"{Colors.GREEN}Correction completed{Colors.GREEN}, file {Colors.ENDC}{input_shp}{Colors.GREEN} saved as: {Colors.ENDC}{output_shp}")    
            
            if error_details:
                for error_type, indices in error_details.items():
                    if error_type=="Too" :
                        print(f"{Colors.GREEN}Correction completed{Colors.GREEN}, file {Colors.ENDC}{input_shp}{Colors.GREEN} saved as: {Colors.ENDC}{output_shp}{Colors.GREEN} Erreur type : {Colors.ENDC}{error_type} : {len(indices)}{Colors.GREEN} occurrences corrected{Colors.ENDC}")
                    
                    else :
                        print(f"{Colors.WARNING}Correction issue{Colors.ERROR}, file {Colors.ENDC}{input_shp}{Colors.ERROR} saved as: {Colors.ENDC}{output_shp}{Colors.ERROR} Erreur type : {Colors.ENDC}{error_type} : {len(indices)}{Colors.ERROR} occurrences{Colors.ENDC}")
        
        else:
            print(f"{Colors.ERROR}Error: No valid features found in {Colors.ENDC}{input_shp}.{Colors.ERROR}No file generated.{Colors.ENDC}")

        # Display the summary
        if modifications !=0 : print(f"{Colors.WARNING}Total number of geometries ignored: {Colors.ENDC}{modifications}")
        print(f"{Colors.INFO}Total number of geometries corrected : {Colors.ENDC}{corrected}")
        print(f"{Colors.INFO}Before correction: {Colors.ENDC}{dict(geom_counts_before)}")
        print(f"{Colors.INFO}After correction: {Colors.ENDC}{dict(geom_counts_after)}")

        
        # Return the number of modifications
        return modifications - corrected

    except Exception as e:
        print(f"{Colors.ERROR}Fix geometry error in the shapefile: {Colors.ENDC}"
              f"{safe_relpath(input_shp)}{Colors.ERROR}, code: {Colors.ENDC}{e}")
        return -1

#################################################################################################
def ThtoQGis(pathshp, outputspath):
    
    # Check if areas, lines, points2d and outline shapefiles exists...
        
    # Check if Outputs path exists
    if not os.path.exists(outputspath):
        print (f"{Colors.WARNING}WARNING: {Colors.ENDC}{safe_relpath(outputspath)}{Colors.WARNING} does not exist, I am creating it...")
        os.mkdir(outputspath)
    
    modifications = 0
    if os.path.isfile(pathshp + 'areas2d.shp') :
        file_list = ['outline2d', 'lines2d', 'areas2d', 'points2d']
        areaOK = True
    
    else :
        file_list = ['outline2d', 'lines2d', 'points2d']
        areaOK = False
        
    print(f"{Colors.HEADER}{Colors.UNDERLINE}Step 1: Test files and convert to GPKG format in the folder:{Colors.ENDC} {safe_relpath(outputspath)}")
    
    for fname in file_list:
        print(f"{Colors.HEADER}Working with file: {Colors.ENDC}{fname}.shp")
        
        if not os.path.isfile(pathshp + fname + '.shp'):
            if fname == 'areas2d':
                areaOK = False
            
            else:
                print(f"{Colors.ERROR}ERROR the file {Colors.ENDC}{(str(pathshp + fname + '.shp'))}{Colors.ERROR} does not exist'{Colors.ENDC}")
                return False
            
        err = count_topology_errors(pathshp + fname +  '.shp')
        
        if err[1] == -1 : return False    
        
        if err[1] != 0 :
            modifications += fix_geometries(pathshp + fname + '.shp', pathshp + fname +  '_fixed.shp')
            
            err2 = count_topology_errors(pathshp + fname +  '_fixed.shp')
            
            if err2[1] == -1 : return False
            
            if err2[1] == 0 : shp2gpkg(pathshp, fname + "_fixed", outputspath, fname)
            
            else :
                print(f'{Colors.ERROR}ERROR: in file {Colors.ENDC}{(str(pathshp + fname + '.shp'))} {Colors.ERROR} please fix it manually with QGis... {Colors.ENDC}')
                return False
        
        else :
            shp2gpkg(pathshp, fname, outputspath, fname)


    print(f"{Colors.HEADER}{Colors.UNDERLINE}Step 2: Adapte files for Qgis in the folder:{Colors.ENDC} {safe_relpath(outputspath)}")
    #1- Read the outline shapefile
    
    outlines = gpd.read_file(outputspath + 'outline2d.gpkg')
    
    ## Work with lines
    cutLines(outputspath, outlines, outputspath)
    
    ## Work with Areas

    if  areaOK == True : 
        cutareas(outputspath, outlines, outputspath)
        poly_rock(outputspath + "lines2d.gpkg", outputspath + "areas2dMasekd.gpkg")
        os.remove(outputspath + "areas2d.gpkg")      
        os.remove(outputspath + "lines2d.gpkg") 
        
        if modifications == 0 :
            print(f'{Colors.GREEN}Update point, areas and lines done without error {Colors.ENDC}')
        
        else :
            print(f'{Colors.GREEN}Update point, areas and lines done with warning {Colors.ENDC}{modifications}{Colors.GREEN} to be checked{Colors.ENDC}')
    
    else :
        os.remove(outputspath + "lines2d.gpkg")  
        
        if modifications == 0 :
            print(f'{Colors.HEADER}Update point and lines done without error {Colors.ENDC}')
        
        else :
            print(f'{Colors.GREEN}Update point and lines done with warning {Colors.ENDC}{modifications}{Colors.GREEN} to be checked{Colors.ENDC}')
    



#####################################################################################################################################
#                                                                                                                                   #
#                                                           Main                                                                    #
#                                                                                                                                   #
#####################################################################################################################################
if __name__ == u'__main__':	
	###################################################
    

    
    #################################################################################################
    # Parse arguments                                                                               #
    #################################################################################################
    parser = argparse.ArgumentParser(
        description=f"{Colors.HEADER}Script to generate QGis (.gpkg) files from Therion (.shp) files with auto-correction if possible", 
        formatter_class=argparse.RawTextHelpFormatter)
    parser.print_help = colored_help.__get__(parser)
    parser.add_argument(
        '--option',
        default="auto",
        choices=["auto", "manual", "test"],
        help=(
            f"Execution options for pyThtoQgis.py\n"
            f"auto\t-> Execution from the folder {globalDat.pathshp} (défaut)\n"
            f"manual\t-> Manual selection for the input folder\n"
            f"test\t-> Tests fonction (debug)\n"
        )
    )
    
    parser.epilog = (
        f"{Colors.HEADER}to generate shp files with therion, add in .thconfig : "
        f"-> {Colors.ENDC}export model -fmt esri -o Outputs/SHP/ -enc UTF-8"
        )
   
    # Analyser les arguments de ligne de commande
    args = parser.parse_args()
    
    if os.name == 'posix':  os.system('clear') # Linux, MacOS
    elif os.name == 'nt':  os.system('cls')# Windows
    else: print("\n" * 100) 
    
    print(f'{Colors.HEADER}*********************************************************************************************************')
    print(f'{Colors.HEADER}Script to generate QGis (.gpkg) files from Therion (.shp) files with auto-correction if possible')
    print(f'{Colors.HEADER}        Original written by X. Robert, ISTerre : {Colors.ENDC}October 2022')
    print(f'{Colors.HEADER}        Updated by : {Colors.ENDC}alexandre.pont@yahoo.fr')
    print(f'{Colors.HEADER}        Version : {Colors.ENDC}{globalDat.Version}')

    
    if args.option == "auto" : 
        
        print(f'{Colors.HEADER}        input folder :  {Colors.ENDC}{globalDat.pathshp}')
        print(f'{Colors.HEADER}        output folder : {Colors.ENDC}{globalDat.outputspath}')
        print(f'{Colors.HEADER}*********************************************************************************************************')
        
        ThtoQGis(globalDat.pathshp, globalDat.outputspath)
        
    
    elif args.option == "manual" :
        root = tk.Tk()
        root.withdraw()  # Cacher la fenêtre principale de Tkinter
        input_folder_name = filedialog.askdirectory( title="Choose the shp folder")       
        
        if not input_folder_name:
            print(f"{Colors.ERROR}No folder selected. The program will terminate")
            sys.exit()    
        
    
        input_folder = input_folder_name + "\\"
        
        print(f'{Colors.HEADER}        input folder :  {Colors.ENDC}{safe_relpath(input_folder)}')
        print(f'{Colors.HEADER}        output folder : {Colors.ENDC}{globalDat.outputspath}')
        print(f'{Colors.HEADER}****************************************************************')
        
        ThtoQGis(input_folder, globalDat.outputspath)
        
    
    elif args.option == "test" :
        exit(1)


