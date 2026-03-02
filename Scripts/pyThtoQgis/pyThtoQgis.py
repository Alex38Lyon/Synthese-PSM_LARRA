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
Modifié Alex 2026 02 27 

Inputs files (16):  (.dbf, .prj, .shp, .shx)
    - points2d
    - lines2d
    - areas2d
    - outlines

En cas d'erreur corriger manuellement (QGis) la topologie des fichiers 

"""

# Do divisions with Reals, not with integers
# Must be at the beginning of the file
    
from __future__ import division

import Lib.global_data as globalDat
from Lib.general_fonctions import setup_logger, Colors, safe_relpath, colored_help


# Import Python modules
import sys, os, argparse, time, math
import tkinter as tk
from tkinter import filedialog
from osgeo import ogr, gdal
from collections import defaultdict
from alive_progress import alive_bar              # https://github.com/rsalmei/alive-progress	


#################################################################################################
def cutGPKG(input_gpkg_path, outlines_path, output_gpkg_path):
    """
    Generic clipping function for lines or polygons using OGR only.

    Ne coupe que les objets de input_gpkg_path dont
    _SCRAP_ID == _ID (dans outlines_path), et uniquement
    avec la géométrie correspondante.

    Args:
        input_gpkg_path (str) : input gpkg path (lines or areas)
        outlines_path (str)   : polygon outline file (doit contenir _ID)
        output_gpkg_path (str): output gpkg path
    """

    log.info(f"Clipping file : {Colors.ENDC}{input_gpkg_path}{Colors.INFO} to file : {Colors.ENDC}{output_gpkg_path}")

    # -------------------------------------------------
    # OPEN INPUT
    # -------------------------------------------------
    ds_in = ogr.Open(input_gpkg_path)
    if ds_in is None:
        log.error(f"cutGPKG, cannot open file : {Colors.ENDC}{input_gpkg_path}")
        return

    layer_in = ds_in.GetLayer()
    in_defn = layer_in.GetLayerDefn()
    srs = layer_in.GetSpatialRef()
    geom_type = layer_in.GetGeomType()

    # Vérification présence champ _SCRAP_ID
    idx_scrap = in_defn.GetFieldIndex("_SCRAP_ID")
    if idx_scrap == -1:
        log.error("cutGPKG, field '_SCRAP_ID' not found in input layer.")
        return

    # -------------------------------------------------
    # OPEN OUTLINES
    # -------------------------------------------------
    ds_outline = ogr.Open(outlines_path)
    if ds_outline is None:
        log.error(f"cutGPKG, cannot open file : {Colors.ENDC}{outlines_path}")
        return

    layer_outline = ds_outline.GetLayer()
    outline_defn = layer_outline.GetLayerDefn()

    idx_id = outline_defn.GetFieldIndex("_ID")
    if idx_id == -1:
        log.error("cutGPKG, field '_ID' not found in outlines layer.")
        return

    # -------------------------------------------------
    # BUILD DICTIONARY {_ID : geometry}
    # -------------------------------------------------
    outline_dict = {}

    for feat in layer_outline:
        geom = feat.GetGeometryRef()
        if geom is None:
            continue

        if not geom.IsValid():
            geom = geom.Buffer(0)

        scrap_id = feat.GetField("_ID")
        if scrap_id is None:
            continue

        if scrap_id not in outline_dict:
            outline_dict[scrap_id] = geom.Clone()
        else:
            outline_dict[scrap_id] = outline_dict[scrap_id].Union(geom)

    if not outline_dict:
        log.error("cutGPKG, no valid geometry found in outlines.")
        return

    # -------------------------------------------------
    # CREATE OUTPUT
    # -------------------------------------------------
    driver = ogr.GetDriverByName("GPKG")

    if os.path.exists(output_gpkg_path):
        driver.DeleteDataSource(output_gpkg_path)

    ds_out = driver.CreateDataSource(output_gpkg_path)

    out_layer = ds_out.CreateLayer(
        os.path.splitext(os.path.basename(output_gpkg_path))[0],
        srs=srs,
        geom_type=geom_type
    )

    # Copy fields
    for i in range(in_defn.GetFieldCount()):
        out_layer.CreateField(in_defn.GetFieldDefn(i))

    out_defn = out_layer.GetLayerDefn()
    layer_in.ResetReading()

    # -------------------------------------------------
    # PROCESS FEATURES
    # -------------------------------------------------
    with alive_bar(len(layer_in), title=f"{Colors.YELLOW}Clipping {Colors.ENDC}", length=20) as bar:
        for feat in layer_in:

            geom = feat.GetGeometryRef()
            if geom is None:
                continue

            if not geom.IsValid():
                geom = geom.Buffer(0)

            scrap_id = feat.GetField("_SCRAP_ID")

            # Si aucun scrap correspondant → on ignore
            if scrap_id not in outline_dict:
                continue

            outline_geom = outline_dict[scrap_id]

            _type = feat.GetField("_TYPE")
            _clip = feat.GetField("_CLIP")

            _type = (_type or "").strip().lower()
            _clip = (_clip or "").strip().lower()

            # -----------------------------------
            # OUTSIDE (no clipping)
            # -----------------------------------
            keep_outside = (_type in {"label", "water_flow", "centerline"} or _clip == "off")

            if keep_outside:
                new_feat = ogr.Feature(out_defn)
                new_feat.SetGeometry(geom.Clone())

                for i in range(out_defn.GetFieldCount()):
                    new_feat.SetField(out_defn.GetFieldDefn(i).GetNameRef(), feat.GetField(i))

                out_layer.CreateFeature(new_feat)
                new_feat = None
                bar()
                continue

            # Pas d'intersection → on ignore
            if not geom.Intersects(outline_geom):
                continue

            inter_geom = geom.Intersection(outline_geom)

            if inter_geom is None or inter_geom.IsEmpty():
                continue

            new_feat = ogr.Feature(out_defn)
            new_feat.SetGeometry(inter_geom)

            for i in range(out_defn.GetFieldCount()):
                new_feat.SetField(
                    out_defn.GetFieldDefn(i).GetNameRef(),
                    feat.GetField(i)
                )

            out_layer.CreateFeature(new_feat)
            new_feat = None
            bar()

    # -------------------------------------------------
    # CLEANUP
    # -------------------------------------------------
    ds_in = None
    ds_outline = None
    ds_out = None

    return

#################################################################################################
def extractVertices(input_gpkg_path, output_gpkg_path):
    """
    Extract vertices from a line layer (GPKG) and write them as points into a GPKG.

    Conditions :
    - Ne conserve que les sommets dont M == 16
    - Conserve tous les attributs d’origine
    - Ajoute un attribut 'angle' correspondant à la direction locale de la ligne (en degrés)
    - Si le fichier de sortie existe, les points sont ajoutés à la fin
    """

    log.info(f"Extract vertices from : {Colors.ENDC}{input_gpkg_path}{Colors.INFO} to {Colors.ENDC}{output_gpkg_path}")

    # -------------------------------------------------
    # OPEN INPUT
    # -------------------------------------------------
    ds_in = ogr.Open(input_gpkg_path)
    if ds_in is None:
        log.error(f"Extract vertices, cannot open file : {Colors.ENDC}{input_gpkg_path}")
        return

    layer_in = ds_in.GetLayer()
    in_defn = layer_in.GetLayerDefn()
    srs = layer_in.GetSpatialRef()

    geom_type = layer_in.GetGeomType()

    allowed_types = {
        0,
        ogr.wkbLineString,
        ogr.wkbMultiLineString,
        ogr.wkbLineString25D,
        ogr.wkbMultiLineString25D,
        ogr.wkbLineStringM,
        ogr.wkbMultiLineStringM,
        ogr.wkbLineStringZM,
        ogr.wkbMultiLineStringZM,
    }
    
    if geom_type not in allowed_types:
        log.error(f"Extract vertices, layer must be LineString type with M support and not : {Colors.ENDC}{geom_type}.")
        return

    # -------------------------------------------------
    # CREATE OR OPEN OUTPUT
    # -------------------------------------------------
    driver = ogr.GetDriverByName("GPKG")

    if os.path.exists(output_gpkg_path):
        ds_out = ogr.Open(output_gpkg_path, update=1)
        if ds_out is None:
            log.error(f"Extract vertices, cannot open file : {Colors.ENDC}{output_gpkg_path}{Colors.ERROR} in update mode.")
            return
        
        out_layer = ds_out.GetLayer()
        out_defn = out_layer.GetLayerDefn()
        
    else:
        ds_out = driver.CreateDataSource(output_gpkg_path)

        out_layer = ds_out.CreateLayer(os.path.splitext(os.path.basename(output_gpkg_path))[0], srs=srs, geom_type=ogr.wkbPoint25D )

    
    # -------------------------------------------------
    # COPY FIELDS (SAFE FOR EXISTING FILE)
    # -------------------------------------------------

    existing_defn = out_layer.GetLayerDefn()

    exclude_fields = {
        "fid",
        "vertex_index",
        "vertex_part",
        "vertex_part_index",
        "distance"
    }

    for i in range(in_defn.GetFieldCount()):

        field_def = in_defn.GetFieldDefn(i)
        field_name = field_def.GetNameRef()

        if field_name.lower() in exclude_fields:
            continue

        # Si le champ existe déjà → on ne recrée pas
        if existing_defn.GetFieldIndex(field_name) != -1:
            continue

        # Création sécurisée (sans Clone)
        new_field = ogr.FieldDefn(field_name, field_def.GetType())
        new_field.SetWidth(field_def.GetWidth())
        new_field.SetPrecision(field_def.GetPrecision())
        new_field.SetNullable(field_def.IsNullable())

        out_layer.CreateField(new_field)

    # Ajout du champ angle si absent
    if existing_defn.GetFieldIndex("_TYPEFCR") == -1:
        field_angle = ogr.FieldDefn("_TYPEFCR", ogr.OFTReal)
        out_layer.CreateField(field_angle)

    out_defn = out_layer.GetLayerDefn()
    
 
    # -------------------------------------------------
    # PROCESS
    # -------------------------------------------------
    layer_in.ResetReading()

    with alive_bar(len(layer_in), title=f"{Colors.YELLOW}Extract vertices {Colors.ENDC}", length=20) as bar:

        for feat in layer_in:

            geom = feat.GetGeometryRef()
            if geom is None:
                continue

            if not geom.IsValid():
                geom = geom.Buffer(0)

            def process_linestring(ls):

                n = ls.GetPointCount()
                if n < 2:
                    return

                for i in range(n):

                    x, y, z, m = ls.GetPointZM(i)

                    if m != 16:
                        continue

                    # calcul direction locale
                    if i == 0:
                        x2, y2, _, _ = ls.GetPointZM(i + 1)
                        dx = x2 - x
                        dy = y2 - y
                    else:
                        x1, y1, _, _ = ls.GetPointZM(i - 1)
                        dx = x - x1
                        dy = y - y1

                    angle = math.degrees(math.atan2(dy, dx))

                    pt = ogr.Geometry(ogr.wkbPoint25D)
                    pt.AddPoint(x, y, z)

                    new_feat = ogr.Feature(out_defn)
                    new_feat.SetGeometry(pt)

                    # copie attributs
                    for f in range(in_defn.GetFieldCount()):
                        new_feat.SetField(in_defn.GetFieldDefn(f).GetNameRef(), feat.GetField(f) )

                    new_feat.SetField("_TYPEFCR", angle)
                    
                    type_val = feat.GetField("_TYPE")
                    
                    if type_val is not None:
                        new_feat.SetField("_TYPE", "line_" + str(type_val))

                    out_layer.CreateFeature(new_feat)
                    new_feat = None

            geom_name = geom.GetGeometryName()

            if geom_name == "LINESTRING":
                process_linestring(geom)

            elif geom_name == "MULTILINESTRING":
                for part in range(geom.GetGeometryCount()):
                    process_linestring(geom.GetGeometryRef(part))

            bar()

    # -------------------------------------------------
    # CLEANUP
    # -------------------------------------------------
    ds_in = None
    ds_out = None

    return

#################################################################################################    
def diagnostic(file_path):

    start_time = time.time()
    
    if not os.path.exists(file_path):
        log.error(f"diagnostic, fichier non trouvé : {Colors.ENDC}{file_path}")
        return
    
    ds = ogr.Open(file_path)
    
    if ds is None:
        log.error(f"Impossible d'ouvrir le fichier : {Colors.ENDC}{file_path}")
        return

    layer = ds.GetLayer()

    total = 0
    invalid = 0
    empty = 0
    multi_geom_count = 0
    geom_types = defaultdict(int)
    has_z = False
    has_m = False
    field_stats = defaultdict(list)

    extent = layer.GetExtent()
    srs = layer.GetSpatialRef()
    crs = srs.ExportToWkt() if srs else "CRS inconnu"

    for feature in layer:

        total += 1

        geom = feature.GetGeometryRef()
        
        if geom is None or geom.IsEmpty():
            empty += 1
            continue

        geom_types[geom.GetGeometryName()] += 1

        if not geom.IsValid():
            invalid += 1

        gtype = geom.GetGeometryType()

        if ogr.GT_HasZ(gtype):
            has_z = True

        if ogr.GT_HasM(gtype):
            has_m = True
            
        # champs attributaires
        layer_defn = layer.GetLayerDefn()
        
        for i in range(layer_defn.GetFieldCount()):
            field_name = layer_defn.GetFieldDefn(i).GetNameRef()
            val = feature.GetField(i)
            if val is not None:
                field_stats[field_name].append(val)
            
    elapsed = time.time() - start_time
    file_size = os.path.getsize(file_path) / (1024*1024)  # Mo

    log.info(f"{Colors.HEADER}============================================== {Colors.INFO}BILAN FILE : {Colors.ENDC}{file_path}{Colors.HEADER}   ==============================================")
    log.info(f"Temps d'analyse : {Colors.ENDC}{elapsed:.2f}{Colors.INFO} s")
    log.info(f"Taille : {Colors.ENDC}{file_size:.2f}{Colors.INFO} Mo")
    log.info(f"Nombre d'objets :  {Colors.ENDC}{total}")
    
    if empty == 0 : log.info(f"Géométries vides : {Colors.ENDC}{empty}")
    else :  log.warning(f"Géométries vides : {Colors.ENDC}{empty}")
    
    if invalid == 0 : log.info(f"Géométries invalides : {Colors.ENDC}{invalid}")
    else : log.warning(f"Géométries invalides : {Colors.ENDC}{invalid}")
    
    log.info(f"MultiGeometries / Collections : {Colors.ENDC}{multi_geom_count}")
    
    log.info("Types géométriques :")
    for gtype, count in geom_types.items():
        log.info(f"\t{gtype} : {Colors.ENDC}{count}")

    log.info("Bounding box :")
    log.info(f"\txmin = {Colors.ENDC}{extent[0]}")
    log.info(f"\txmax = {Colors.ENDC}{extent[1]}")
    log.info(f"\tymin = {Colors.ENDC}{extent[2]}")
    log.info(f"\tymax = {Colors.ENDC}{extent[3]}")


    log.info(f"CRS : {Colors.ENDC}{crs}")

    log.info("Dimensions :")
    log.info(f"\tZ présent : {Colors.ENDC}{has_z}")
    log.info(f"\tM présent : {Colors.ENDC}{has_m}")
    
    log.info("Champs attributaires :")
    
    for field, values in field_stats.items():
        unique_count = len(set(values))
        log.info(f"\tchamp : {Colors.ENDC}{field}{Colors.INFO} : {Colors.ENDC}{len(values)}{Colors.INFO} valeurs, {Colors.ENDC}{unique_count}{Colors.INFO} uniques")

    log.info(f"{Colors.HEADER}=========================================================================================================")

    ds = None
    
    return invalid

#################################################################################################
def fix_geometry(geom, GetFID):
    
    if geom is None:
        return None

    geom = geom.Clone()

    try:
        geom.CloseRings()   # ferme anneaux
                
        # geom = geom.RemoveDuplicatePoints()  # supprime points dupliqués

       
        if not geom.IsValid():  # corrige topologie
            log.debug(f"Géométrie invalide FID {Colors.ENDC}{GetFID}{Colors.WARNING}")
            geom = geom.MakeValid()
            if not geom.IsValid():
                return None

        if geom is None or geom.IsEmpty(): # supprime géométries vides
            log.warning(f"Géométrie vide supprimée FID {Colors.ENDC}{GetFID}{Colors.WARNING}")
            return None

        gtype = geom.GetGeometryType()

        if gtype in (ogr.wkbLineString, ogr.wkbLineString25D):
            if geom.GetPointCount() < 2:
                log.warning(f"Géométrie de type ligne supprimée, nombre de points insuffisant <2 {Colors.ENDC}{GetFID}{Colors.WARNING}")
                return None

        if gtype == ogr.wkbPolygon:
            ring = geom.GetGeometryRef(0)
            if ring is None or ring.GetPointCount() < 4:
                log.warning(f"Géométrie de type Polygone supprimée, nombre de points insuffisant <4 {Colors.ENDC}{GetFID}{Colors.WARNING}")
                return None

        return geom

    except Exception as e:
        log.error(f"Géométrie impossible à corriger, FID {Colors.ENDC}{GetFID}{Colors.ERROR} code : {Colors.ENDC}{e}")
        return None

#################################################################################################
def shp2gpkg(pathshp, infile, outputspath, outfile):

    """
    Conversion rapide SHP -> GPKG.

    - support tous types de géométrie
    - conserve Z et M
    - ferme anneaux automatiquement
    - corrige géométries invalides
    - message uniquement si correction impossible
    - optimisé gros fichiers
    """

    input_shp = os.path.join(pathshp, infile + ".shp")
    output_gpkg = os.path.join(outputspath, outfile + ".gpkg")
    
    geom_stats = defaultdict(int)

    try:        

        # sécurité GDAL_DATA
        if not gdal.GetConfigOption("GDAL_DATA"):
            gdal.SetConfigOption("GDAL_DATA", "/usr/share/gdal")

        gdal.SetConfigOption("OGR_GEOMETRY_ACCEPT_UNCLOSED_RING", "YES")

        # ouverture SHP
        ds = ogr.Open(input_shp)
        if ds is None:
            log.error(f"shp2gpkg, impossible d'ouvrir le SHP : {Colors.ENDC}{input_shp}")
            return

        layer = ds.GetLayer()
        srs = layer.GetSpatialRef()

        # suppression gpkg existant
        if os.path.exists(output_gpkg):
            ogr.GetDriverByName("GPKG").DeleteDataSource(output_gpkg)

        # création gpkg
        driver = ogr.GetDriverByName("GPKG")
        out_ds = driver.CreateDataSource(output_gpkg)

        # type inconnu = accepte tout
        out_layer = out_ds.CreateLayer(outfile, srs, geom_type=ogr.wkbUnknown)

        # copie structure attributaire
        layer_defn = layer.GetLayerDefn()

        for i in range(layer_defn.GetFieldCount()):
            out_layer.CreateField(layer_defn.GetFieldDefn(i))

        out_layer_defn = out_layer.GetLayerDefn()

        # optimisation écriture
        out_layer.StartTransaction()

        error_count = 0
        feature_count = 0
        total_count = len(layer)
        
        log.info(f"Conversion du fichier SHP : {Colors.ENDC}{infile}.shp{Colors.INFO} contenant {Colors.ENDC}{total_count}{Colors.INFO} objets")

        with alive_bar(len(layer), title=f"{Colors.YELLOW}Conversion {Colors.ENDC}" ,  length = 20) as bar:
            for feature in layer:

                geom = fix_geometry(feature.GetGeometryRef(), feature.GetFID() )
                
                if geom is None : 
                    log.warning(f"Géométrie impossible à corriger FID")
                    error_count += 1
                    
                geom_type_name = geom.GetGeometryName()
                geom_stats[geom_type_name] += 1

                # création feature
                out_feature = ogr.Feature(out_layer_defn)

                # copie attributs
                for i in range(out_layer_defn.GetFieldCount()):
                    out_feature.SetField(i, feature.GetField(i))

                out_feature.SetGeometry(geom)

                out_layer.CreateFeature(out_feature)

                out_feature = None

                feature_count += 1

                # commit par bloc (performance)
                if feature_count % 10000 == 0:
                    out_layer.CommitTransaction()
                    out_layer.StartTransaction()
                bar()

        out_layer.CommitTransaction()

        ds = None
        out_ds = None
        
        # total = 0 
        log.info(f"Conversion GPKG terminée fichier: {Colors.ENDC}{outfile}{Colors.INFO}, {Colors.ENDC}{feature_count}{Colors.INFO} objets convertis")
        # for gtype, count in sorted(geom_stats.items()):
        #     log.info(f"Type : {gtype} -> {Colors.ENDC}{count}")
        #     total += count
        # log.info(f"Total -> {Colors.ENDC}{total}")
        

        if error_count > 0: log.warning(f"{Colors.ENDC}{error_count}{Colors.WARNING} géométries n'ont pas pu être corrigées")
        if (total_count - feature_count) > 0 : log.warning(f"{Colors.ENDC}{total_count - feature_count}{Colors.WARNING} géométries supprimées") 

    except Exception as e:

        if log:
            log.error(f"Erreur conversion SHP to GPKG : {e}")

        raise

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
            log.error(f"File not found: {Colors.ENDC}{file_path}")
            return {}, -1

        driver = ogr.GetDriverByName("ESRI Shapefile")
        datasource = driver.Open(file_path, 0)  # 0 = read-only

        if datasource is None:
            log.error(f"Cannot open file: {Colors.ENDC}{file_path}")
            return {}, -1

        layer = datasource.GetLayer()

        for i, feature in enumerate(layer):
            total_records += 1

            if feature is None:
                log.error(
                    f"Error in file {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR}, "
                    f"record {Colors.ENDC}{i+1}{Colors.ERROR} is None"
                )
                continue

            geometry = feature.GetGeometryRef()

            # Vérifier présence géométrie
            if geometry is None:
                log.error(
                    f"Error in file {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR}, "
                    f"record {Colors.ENDC}{i+1}{Colors.ERROR} has no geometry, correct it : "
                    f"_ID: {Colors.ENDC}{feature.GetField('_ID')}{Colors.ERROR}, "
                    f"_NAME: {Colors.ENDC}{feature.GetField('_NAME')}{Colors.ERROR}, "
                    f"_SURVEY: {Colors.ENDC}{feature.GetField('_SURVEY')}{Colors.ENDC}"
                )
                continue

            # Ignorer géométries vides
            if geometry.IsEmpty():
                log.warning(
                    f"Warning, file {Colors.ENDC}{safe_relpath(file_path)}{Colors.WARNING}, "
                    f"Record {i+1} has empty geometry. Skipping.{Colors.ENDC}"
                )
                continue

            # Comptage des types de géométrie
            geom_type = geometry.GetGeometryName()
            record_types[geom_type] = record_types.get(geom_type, 0) + 1

            # Vérification topologique
            try:
                if not geometry.IsValid():
                    total_errors += 1

                    # Tentative d'explication (GEOS requis dans GDAL)
                    try:
                        validity_explanation = geometry.IsValidReason()
                    except Exception:
                        validity_explanation = "Invalid Geometry"

                    error_details.setdefault(validity_explanation, []).append(i)

            except Exception as e:
                log.error(
                    f"Error in file {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR}, "
                    f"validating geometry for record {Colors.ENDC}{i+1}{Colors.ERROR}: "
                    f"{Colors.ENDC}{e}{Colors.ENDC}"
                )

        log.info(
            f"Geometry num: {Colors.ENDC}{total_records}{Colors.YELLOW}, "
            f"types found: {Colors.ENDC}{record_types}"
        )

        if total_errors == 0:
            log.info(
                f"File error check OK: {Colors.ENDC}{safe_relpath(file_path)}{Colors.GREEN}, "
                f"records: {Colors.ENDC}{total_records}{Colors.GREEN}, no errors found"
            )
        else:
            log.error(
                f"File error check NOK: {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR}, "
                f"records: {Colors.ENDC}{total_records}{Colors.ERROR}, "
                f"total errors: {Colors.ENDC}{total_errors}"
            )

        log.info(
            f"Geometry in file: {Colors.ENDC}{safe_relpath(file_path)}{Colors.GREEN}, "
            f"types found: {Colors.ENDC}{record_types}"
        )

        datasource = None  # fermeture propre

        return error_details, total_errors

    except Exception as e:
        log.error(
            f"Topology error when analyzing the shapefile: {Colors.ENDC}"
            f"{safe_relpath(file_path)}{Colors.ERROR}, code: {Colors.ENDC}{e}"
        )
        return {}, -1

#################################################################################################
def ThtoQGis(pathshp, outputspath):
    
    # Check if areas, lines, points2d and outline shapefiles exists...
        
    # Check if Outputs path exists
    if not os.path.exists(outputspath):
        log.warning(f"WARNING: {Colors.ENDC}{safe_relpath(outputspath)}{Colors.WARNING} does not exist, I am creating it...")
        os.mkdir(outputspath)
    
    file_list = ['points2d', 'lines2d', 'outline2d', 'areas2d', 'walls3d', 'stations3d', 'shots3d']
    dest_list = ['points2d', 'outline2d', 'walls3d', 'stations3d', 'shots3d']
        
    log.info(f"{Colors.HEADER}{Colors.UNDERLINE}Step 1: Test files and convert to GPKG format in the folder:{Colors.ENDC} {safe_relpath(outputspath)}")
    
    for fname in file_list:
        log.info(f"Working with file: {Colors.ENDC}{fname}.shp")
        
        if not os.path.isfile(pathshp + fname + '.shp'):
            log.error(f"ERROR the file {Colors.ENDC}{(str(pathshp + fname + '.shp'))}{Colors.ERROR} does not exist'{Colors.ENDC}")
            continue    
                   
        diagnostic(pathshp + fname + '.shp')
        
        if fname in dest_list :
            destination = outputspath
            destinationName = fname 
        else :
            destination = pathshp
            destinationName = fname +  '_fixed'
            
        shp2gpkg(pathshp, fname, destination,  destinationName) 
        
        err = diagnostic(destination + destinationName + '.gpkg')

        if err != 0 : 
            log.error(f"ERROR: in file {Colors.ENDC}{(str(destination + destinationName + '.gpkg'))} {Colors.ERROR} please fix it manually with QGis...")
            return False


    log.info(f"{Colors.HEADER}{Colors.UNDERLINE}Step 2: Adapte drawing files for Qgis in the folder:{Colors.ENDC} {safe_relpath(outputspath)}")
    
    ## Work with lines
    cutGPKG(pathshp + 'lines2d_fixed.gpkg', outputspath + 'outline2d.gpkg', outputspath + 'lines2dMasked.gpkg')     
    diagnostic(outputspath + 'lines2dMasked.gpkg')
          
    ## Work with Areas        
    cutGPKG(pathshp + 'areas2d_fixed.gpkg', outputspath + 'outline2d.gpkg', outputspath + 'areas2dMasked.gpkg')    
    diagnostic(outputspath + 'areas2dMasked.gpkg')    
    
    ## Work with Points 'add altitudes' 
    extractVertices(globalDat.outputspath + 'lines2dMasked.gpkg', globalDat.outputspath + 'points2d.gpkg')
    diagnostic(outputspath + 'points2d.gpkg') 
    
  
#####################################################################################################################################
#                                                                                                                                   #
#                                                           Main                                                                    #
#                                                                                                                                   #
#####################################################################################################################################
if __name__ == u'__main__':	
	###################################################
    ogr.UseExceptions()
    gdal.UseExceptions()
    gdal.PushErrorHandler("CPLQuietErrorHandler")
    gdal.SetConfigOption("SHAPE_ENCODING", "UTF-8")
    gdal.SetConfigOption("OGR_CHARSET", "UTF-8")
    gdal.SetConfigOption("OGR_GPKG_ENCODING", "UTF-8")
    
    log = setup_logger(globalDat.output_log, globalDat.debug_log)

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
        f"{Colors.GREEN}Note : to generate shp files in therion, add in .thconfig "
        f"-> {Colors.ENDC}export model -fmt esri -o Outputs/SHP/ -enc UTF-8"
        )

    # Analyser les arguments de ligne de commande
    args = parser.parse_args()
    
    if os.name == 'posix':  os.system('clear') # Linux, MacOS
    elif os.name == 'nt':  os.system('cls')# Windows
    else: print("\n" * 100) 
    
    log.info(f'{Colors.HEADER}*********************************************************************************************************')
    log.info(f'{Colors.HEADER}Script to generate QGis (.gpkg) files from Therion (.shp) files with auto-correction if possible')
    log.info(f'{Colors.HEADER}        original written by X. Robert, ISTerre : {Colors.ENDC}October 2022')
    log.info(f'{Colors.HEADER}        updated by : {Colors.ENDC}alexandre.pont@yahoo.fr')
    log.info(f'{Colors.HEADER}        version : {Colors.ENDC}{globalDat.Version}')

    
    if args.option == "auto" : 
        log.info(f'{Colors.HEADER}        auto mode')
        log.info(f'{Colors.HEADER}        input folder :  {Colors.ENDC}{globalDat.pathshp}')
        log.info(f'{Colors.HEADER}        output folder : {Colors.ENDC}{globalDat.outputspath}')
        log.info(f'{Colors.HEADER}*********************************************************************************************************')
        
        ThtoQGis(globalDat.pathshp, globalDat.outputspath)
        
    
    elif args.option == "manual" :
        root = tk.Tk()
        root.withdraw()  # Cacher la fenêtre principale de Tkinter
        input_folder_name = filedialog.askdirectory( title="Choose the shp folder")       
        
        if not input_folder_name:
            log.error(f"No folder selected. The program will terminate")
            sys.exit()    
        
    
        input_folder = input_folder_name + "\\"
        log.info(f'{Colors.HEADER}        manual mode')
        log.info(f'{Colors.HEADER}        input folder :  {Colors.ENDC}{safe_relpath(input_folder)}')
        log.info(f'{Colors.HEADER}        output folder : {Colors.ENDC}{globalDat.outputspath}')
        log.info(f'{Colors.HEADER}*********************************************************************************************************')
        
        ThtoQGis(input_folder, globalDat.outputspath)
        
    
    elif args.option == "test" :
        log.info(f'{Colors.HEADER}        test mode')
        log.info(f'{Colors.HEADER}        input folder :  {Colors.ENDC}{globalDat.pathshp}')
        log.info(f'{Colors.HEADER}        output folder : {Colors.ENDC}{globalDat.outputspath}')
        log.info(f'{Colors.HEADER}*********************************************************************************************************')
 
        extractVertices(globalDat.outputspath + 'lines2dMasked.gpkg', globalDat.outputspath + 'points2d.gpkg')
        
        exit(0)
        
        diagnostic(globalDat.pathshp + 'lines2d.shp')
        count_topology_errors(globalDat.pathshp + 'lines2d.shp')
        shp2gpkg(globalDat.pathshp, 'lines2d' , globalDat.outputspath, 'lines2d')
        diagnostic(globalDat.outputspath + 'lines2d.gpkg')
        
        
        diagnostic(globalDat.pathshp + 'outline2d.shp')
        shp2gpkg(globalDat.pathshp, 'outline2d', globalDat.outputspath, 'outline2d') 
        diagnostic(globalDat.outputspath + 'outline2d.gpkg')
        
        # diagnostic(globalDat.pathshp + 'points2d.shp')
        # shp2gpkg(globalDat.pathshp, 'points2d', globalDat.outputspath, 'points2d') 
        # diagnostic(globalDat.outputspath + 'points2d.gpkg')
        
        diagnostic(globalDat.pathshp + 'areas2d.shp')
        shp2gpkg(globalDat.pathshp, 'areas2d', globalDat.outputspath, 'areas2d') 
        diagnostic(globalDat.outputspath + 'areas2d.gpkg')
        
        # diagnostic(globalDat.pathshp + 'walls3d.shp')
        # shp2gpkg(globalDat.pathshp, 'walls3d', globalDat.outputspath, 'walls3d') 
        # diagnostic(globalDat.outputspath + 'walls3d.gpkg')

        cutGPKG(globalDat.outputspath + 'lines2d.gpkg', globalDat.outputspath + 'outline2d.gpkg', globalDat.outputspath + 'lines2dMasked.gpkg')    
        diagnostic(globalDat.outputspath + 'lines2dMasked.gpkg')
                
        cutGPKG(globalDat.outputspath + 'areas2d.gpkg', globalDat.outputspath + 'outline2d.gpkg', globalDat.outputspath + 'areas2dMasked.gpkg')    
        diagnostic(globalDat.outputspath + 'areas2dMasked.gpkg')        
    
        
        # outlines = gpd.read_file(globalDat.outputspath + 'outline2d.gpkg')
        # cutLines(globalDat.outputspath, globalDat.outputspath + 'outline2d.gpkg', globalDat.outputspath)    
        # diagnostic(globalDat.outputspath + 'lines2dMasked.gpkg')
        
        # fname = "stations3d"
        # shp2gpkg(globalDat.pathshp, fname , globalDat.outputspath, fname)
        
        # fname = "shots3d"
        # shp2gpkg(globalDat.pathshp, fname , globalDat.outputspath, fname)
        
        # fname = "walls3d"
        # shp2gpkg(globalDat.pathshp, fname , globalDat.outputspath, fname)
        

        

            


 