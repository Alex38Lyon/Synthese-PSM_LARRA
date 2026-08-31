######!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2020 Xavier Robert <xavier.robert@ird.fr>
# SPDX-License-Identifier: GPL-3.0-or-later


"""
!######################################################################
!#                                                        	          #  
!# Script to automatize data extraction of Therion databases for QGis #
!#                                                        	          #  
!#                       By Xavier Robert                             #
!#                    Grenoble, October 2022                   	      #
!#                                                        	          #  
!######################################################################

Written by Xavier Robert, October 2022
Xavier.robert@ird.fr

Modifié Alex 2025 01 31
Modifié Alex 2026 02 27 
Modifié Alex 2026 08 28

Inputs files (28):  (.dbf, .prj, .shp, .shx)
    - points2d (4)
    - lines2d (4)
    - areas2d (4)
    - outlines (4)
    - shots3d (4)
    - stations3d (4)
    - walls3d (4)

Outputs files (8), in QGis_GPKG_Files folder: 
    - points2d.gpkg
    - lines2dMasked.gpkg
    - areas2dMasked.gpkg
    - outline2d.gpkg
    - shots3d.gpkg
    - stations3d.gpkg
    - walls3d.gpkg
    - pyThtoQgis.log
    
    
En cas d'erreur (voir log), corriger manuellement avec QGis ou dans therion la topologie des fichiers 

"""
    
from __future__ import division

import Lib.global_data as globalDat
from Lib.general_fonctions import setup_logger, Colors, safe_relpath, colored_help


# Import Python modules
import sys, os, argparse, time, math, logging
import tkinter as tk
from tkinter import filedialog
from osgeo import ogr, gdal
from collections import defaultdict
from alive_progress import alive_bar              # https://github.com/rsalmei/alive-progress	


#################################################################################################
#################################################################################################
def cutGPKG_2(input_gpkg_path, outlines_path, output_gpkg_path):
    """
    Generic clipping function for lines or polygons using OGR only.
    """
    try:
        log.info(
            f"Clipping file : {Colors.ENDC}{safe_relpath(input_gpkg_path)}"
            f"{Colors.INFO} to file : {Colors.ENDC}{safe_relpath(output_gpkg_path)}"
        )

        # -------------------------------------------------
        # OPEN INPUT
        # -------------------------------------------------
        ds_in = ogr.Open(input_gpkg_path)

        if ds_in is None:
            log.error(
                f"cutGPKG, cannot open file : "
                f"{Colors.ENDC}{input_gpkg_path}"
            )
            globalDat.errorCount += 1
            return -1

        layer_in = ds_in.GetLayer()
        in_defn = layer_in.GetLayerDefn()
        srs = layer_in.GetSpatialRef()
        geom_type = layer_in.GetGeomType()

        idx_scrap = in_defn.GetFieldIndex("_SCRAP_ID")

        if idx_scrap == -1:
            log.error("cutGPKG, field '_SCRAP_ID' not found in input layer.")
            globalDat.errorCount += 1
            return -1

        # -------------------------------------------------
        # OPEN OUTLINES
        # -------------------------------------------------
        ds_outline = ogr.Open(outlines_path)

        if ds_outline is None:
            log.error(
                f"cutGPKG, cannot open file : "
                f"{Colors.ENDC}{outlines_path}"
            )
            globalDat.errorCount += 1
            return -1

        layer_outline = ds_outline.GetLayer()
        outline_defn = layer_outline.GetLayerDefn()

        idx_id = outline_defn.GetFieldIndex("_ID")

        if idx_id == -1:
            log.error(
                "cutGPKG, field '_ID' not found in outlines layer."
            )
            globalDat.errorCount += 1
            return -1

        # -------------------------------------------------
        # BUILD DICTIONARY {_ID : geometry}
        # -------------------------------------------------
        outline_dict = {}

        for feat in layer_outline:

            geom = feat.GetGeometryRef()

            if geom is None:
                log.warning(
                    f"cutGPKG, outline FID={feat.GetFID()} : "
                    f"geometry is None"
                )
                continue

            if not geom.IsValid():
                log.warning(
                    f"cutGPKG, invalid outline geometry, "
                    f"FID={feat.GetFID()}, _ID={feat.GetField('_ID')}, "
                    f"applying Buffer(0)"
                )
                geom = geom.Buffer(0)

            scrap_id = feat.GetField("_ID")

            if scrap_id is None:
                log.warning(
                    f"cutGPKG, outline FID={feat.GetFID()} : "
                    f"_ID is NULL"
                )
                continue

            if scrap_id not in outline_dict:
                outline_dict[scrap_id] = geom.Clone()

            else:
                outline_dict[scrap_id] = outline_dict[scrap_id].Union(geom)

        if not outline_dict:
            log.error("cutGPKG, no valid geometry found in outlines.")
            globalDat.errorCount += 1
            return -1

        log.debug(
            f"cutGPKG, nombre de _ID dans les outlines : "
            f"{len(outline_dict)}"
        )

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

        countObjetsInput = len(layer_in)

        # Compteurs de diagnostic
        count_keep_outside = 0
        count_clipped = 0
        count_no_scrap = 0
        count_no_intersection = 0
        count_empty_intersection = 0
        count_geom_none = 0
        count_create_error = 0

        input_fids = set()
        output_fids = []

        with alive_bar(
            countObjetsInput,
            title=f"{Colors.YELLOW}Clipping file "
                  f"{Colors.ENDC}{safe_relpath(input_gpkg_path)}",
            length=20
        ) as bar:

            for feat in layer_in:

                fid = feat.GetFID()
                input_fids.add(fid)

                geom = feat.GetGeometryRef()

                scrap_id = feat.GetField("_SCRAP_ID")

                _type = (
                    feat.GetField("_TYPE") or ""
                ).strip().lower()

                _clip = (
                    feat.GetField("_CLIP") or ""
                ).strip().lower()

                # -------------------------------------------------
                # ATTRIBUTS POUR LES LOGS
                # -------------------------------------------------

                attrs = []

                for i in range(in_defn.GetFieldCount()):
                    field_name = in_defn.GetFieldDefn(i).GetNameRef()
                    field_value = feat.GetField(i)
                    attrs.append(
                        f"{field_name}={field_value}"
                    )

                attrs_formatted = ", ".join(attrs)

                # -------------------------------------------------
                # GEOMETRY NONE
                # -------------------------------------------------

                if geom is None:

                    count_geom_none += 1

                    log.warning(
                        f"cutGPKG, OBJET IGNORE - geometry is None : "
                        f"FID={fid}, "
                        f"_SCRAP_ID={scrap_id}, "
                        f"_TYPE={_type}, "
                        f"_CLIP={_clip}, "
                        f"attributes: {attrs_formatted}"
                    )

                    bar()
                    continue

                # -------------------------------------------------
                # INVALID GEOMETRY
                # -------------------------------------------------

                if not geom.IsValid():

                    log.warning(
                        f"cutGPKG, invalid input geometry : "
                        f"FID={fid}, "
                        f"_SCRAP_ID={scrap_id}, "
                        f"_TYPE={_type}, "
                        f"_CLIP={_clip}"
                    )

                    geom = geom.Buffer(0)

                    if geom is None or geom.IsEmpty():

                        log.warning(
                            f"cutGPKG, OBJET PERDU après Buffer(0) : "
                            f"FID={fid}, "
                            f"_SCRAP_ID={scrap_id}, "
                            f"attributes: {attrs_formatted}"
                        )

                        bar()
                        continue

                # -------------------------------------------------
                # SCRAP ID INCONNU
                # -------------------------------------------------

                if scrap_id not in outline_dict:

                    count_no_scrap += 1

                    log.warning(
                        f"cutGPKG, SCRAP_ID ABSENT DES OUTLINES : "
                        f"FID={fid}, "
                        f"_SCRAP_ID={scrap_id}, "
                        f"_TYPE={_type}, "
                        f"_CLIP={_clip}, "
                        f"attributes: {attrs_formatted}"
                    )

                    # ATTENTION :
                    # comportement actuel conservé
                    outline_dict[scrap_id] = geom.Clone()

                outline_geom = outline_dict[scrap_id]

                # -------------------------------------------------
                # OUTSIDE (no clipping)
                # -------------------------------------------------

                keep_outside = (
                    _type in {
                        "label",
                        "water_flow",
                        "centerline"
                    }
                    or _clip == "off"
                )

                if keep_outside:

                    new_feat = ogr.Feature(out_defn)
                    new_feat.SetGeometry(geom.Clone())

                    for i in range(out_defn.GetFieldCount()):
                        new_feat.SetField(
                            out_defn.GetFieldDefn(i).GetNameRef(),
                            feat.GetField(i)
                        )

                    result = out_layer.CreateFeature(new_feat)

                    if result != 0:

                        count_create_error += 1

                        log.warning(
                            f"cutGPKG, ERREUR CreateFeature "
                            f"(OUTSIDE) : "
                            f"FID={fid}, "
                            f"_SCRAP_ID={scrap_id}, "
                            f"OGR error={result}, "
                            f"attributes: {attrs_formatted}"
                        )

                    else:
                        count_keep_outside += 1

                    new_feat = None
                    bar()
                    continue

                # -------------------------------------------------
                # NO INTERSECTION
                # -------------------------------------------------

                try:
                    intersects = geom.Intersects(outline_geom)
                except Exception as e:

                    log.warning(
                        f"cutGPKG, ERREUR Intersects : "
                        f"FID={fid}, "
                        f"_SCRAP_ID={scrap_id}, "
                        f"error={e}, "
                        f"attributes: {attrs_formatted}"
                    )

                    bar()
                    continue

                if not intersects:

                    count_no_intersection += 1

                    log.warning(
                        f"cutGPKG, OBJET IGNORE - aucune intersection : "
                        f"FID={fid}, "
                        f"_SCRAP_ID={scrap_id}, "
                        f"_TYPE={_type}, "
                        f"_CLIP={_clip}, "
                        f"attributes: {attrs_formatted}"
                    )

                    bar()
                    continue

                # -------------------------------------------------
                # INTERSECTION
                # -------------------------------------------------

                try:
                    inter_geom = geom.Intersection(outline_geom)

                except Exception as e:

                    log.warning(
                        f"cutGPKG, ERREUR Intersection : "
                        f"FID={fid}, "
                        f"_SCRAP_ID={scrap_id}, "
                        f"error={e}, "
                        f"attributes: {attrs_formatted}"
                    )

                    bar()
                    continue

                if inter_geom is None:

                    count_empty_intersection += 1

                    log.warning(
                        f"cutGPKG, OBJET IGNORE - "
                        f"Intersection retourne None : "
                        f"FID={fid}, "
                        f"_SCRAP_ID={scrap_id}, "
                        f"attributes: {attrs_formatted}"
                    )

                    bar()
                    continue

                if inter_geom.IsEmpty():

                    count_empty_intersection += 1

                    log.warning(
                        f"cutGPKG, OBJET IGNORE - "
                        f"Intersection vide : "
                        f"FID={fid}, "
                        f"_SCRAP_ID={scrap_id}, "
                        f"attributes: {attrs_formatted}"
                    )

                    bar()
                    continue

                # -------------------------------------------------
                # CREATE FEATURE
                # -------------------------------------------------

                new_feat = ogr.Feature(out_defn)
                new_feat.SetGeometry(inter_geom)

                for i in range(out_defn.GetFieldCount()):
                    new_feat.SetField(
                        out_defn.GetFieldDefn(i).GetNameRef(),
                        feat.GetField(i)
                    )

                result = out_layer.CreateFeature(new_feat)

                if result != 0:

                    count_create_error += 1

                    log.warning(
                        f"cutGPKG, ERREUR CreateFeature "
                        f"(CLIPPED) : "
                        f"FID={fid}, "
                        f"_SCRAP_ID={scrap_id}, "
                        f"OGR error={result}, "
                        f"attributes: {attrs_formatted}"
                    )

                else:
                    count_clipped += 1
                    output_fids.append(fid)

                new_feat = None

                bar()

        # -------------------------------------------------
        # DIAGNOSTIC FINAL
        # -------------------------------------------------

        total_output = (
            count_keep_outside +
            count_clipped
        )

        log.warning(
            f"cutGPKG, BILAN : "
            f"entrée={countObjetsInput}, "
            f"sortie={total_output}, "
            f"différence={countObjetsInput - total_output}"
        )

        log.warning(
            f"cutGPKG, conservés sans découpage : "
            f"{count_keep_outside}"
        )

        log.warning(
            f"cutGPKG, objets découpés : "
            f"{count_clipped}"
        )

        log.warning(
            f"cutGPKG, SCRAP_ID absents : "
            f"{count_no_scrap}"
        )

        log.warning(
            f"cutGPKG, sans intersection : "
            f"{count_no_intersection}"
        )

        log.warning(
            f"cutGPKG, intersections vides : "
            f"{count_empty_intersection}"
        )

        log.warning(
            f"cutGPKG, géométries None : "
            f"{count_geom_none}"
        )

        log.warning(
            f"cutGPKG, erreurs CreateFeature : "
            f"{count_create_error}"
        )

        # -------------------------------------------------
        # VERIFICATION REELLE DU FICHIER DE SORTIE
        # -------------------------------------------------

        ds_out.FlushCache()

        output_layer_count = len(out_layer)

        log.warning(
            f"cutGPKG, nombre réel d'objets dans la couche finale : "
            f"{output_layer_count}"
        )

        # -------------------------------------------------
        # CLEANUP
        # -------------------------------------------------

        ds_in = None
        ds_outline = None
        ds_out = None

        return countObjetsInput

    except RuntimeError as e:

        log.error(
            f"cutGPKG, unable to validate geometry: "
            f"{e}, continuing anyway."
        )

        globalDat.errorCount += 1
        return -1

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
    try : 
        log.info(f"Clipping file : {Colors.ENDC}{safe_relpath(input_gpkg_path)}{Colors.INFO} to file : {Colors.ENDC}{safe_relpath(output_gpkg_path)}")

        # -------------------------------------------------
        # OPEN INPUT
        # -------------------------------------------------
        ds_in = ogr.Open(input_gpkg_path)
        
        if ds_in is None:
            log.error(f"cutGPKG, cannot open file : {Colors.ENDC}{input_gpkg_path}")
            globalDat.errorCount += 1
            return -1

        layer_in = ds_in.GetLayer()
        in_defn = layer_in.GetLayerDefn()
        srs = layer_in.GetSpatialRef()
        geom_type = layer_in.GetGeomType()

        # Vérification présence champ _SCRAP_ID
        idx_scrap = in_defn.GetFieldIndex("_SCRAP_ID")
        
        if idx_scrap == -1:
            log.error("cutGPKG, field '_SCRAP_ID' not found in input layer.")
            globalDat.errorCount += 1
            return -1

        # -------------------------------------------------
        # OPEN OUTLINES
        # -------------------------------------------------
        ds_outline = ogr.Open(outlines_path)
        
        if ds_outline is None:
            log.error(f"cutGPKG, cannot open file : {Colors.ENDC}{outlines_path}")
            globalDat.errorCount += 1
            return -1

        layer_outline = ds_outline.GetLayer()
        outline_defn = layer_outline.GetLayerDefn()

        idx_id = outline_defn.GetFieldIndex("_ID")
        
        if idx_id == -1:
            log.error("cutGPKG, field '_ID' not found in outlines layer.")
            globalDat.errorCount += 1
            return -1

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
            globalDat.errorCount += 1
            return -1

        # -------------------------------------------------
        # CREATE OUTPUT
        # -------------------------------------------------
        driver = ogr.GetDriverByName("GPKG")

        if os.path.exists(output_gpkg_path):
            driver.DeleteDataSource(output_gpkg_path)

        ds_out = driver.CreateDataSource(output_gpkg_path)

        out_layer = ds_out.CreateLayer(os.path.splitext(os.path.basename(output_gpkg_path))[0], srs=srs, geom_type=geom_type)

        # Copy fields
        for i in range(in_defn.GetFieldCount()):
            out_layer.CreateField(in_defn.GetFieldDefn(i))

        out_defn = out_layer.GetLayerDefn()
        layer_in.ResetReading()

        # -------------------------------------------------
        # PROCESS FEATURES
        # -------------------------------------------------
        countObjetsInput = len(layer_in)
        with alive_bar(countObjetsInput, title=f"{Colors.YELLOW}Clipping file {Colors.ENDC}{safe_relpath(input_gpkg_path)} {Colors.ENDC}", length=20) as bar:
            for feat in layer_in:

                geom = feat.GetGeometryRef()
                
                if geom is None:
                    log.warning(f"geom is None")
                    bar()
                    continue

                if not geom.IsValid():
                    geom = geom.Buffer(0)

                scrap_id = feat.GetField("_SCRAP_ID")
                
                if scrap_id not in outline_dict:
                    outline_dict[scrap_id] = geom.Clone()                    

                # Si aucun scrap correspondant → on ignore
                # if scrap_id not in outline_dict:
                #     code, error_type, error_msg = get_geometry_error(geom)
                #     attrs = []
                    
                #     for i in range(in_defn.GetFieldCount()):
                #         field_name = in_defn.GetFieldDefn(i).GetNameRef()
                #         field_value = feat.GetField(i)
                #         attrs.append(f"{Colors.ENDC}{field_name}{Colors.WARNING}={Colors.ENDC}{field_value}{Colors.WARNING}")                
          
                #     attrs_formatted = ', '.join(attrs)
            
                #     log.warning(f"Scrap_ID {Colors.ENDC}{scrap_id}{Colors.WARNING} issue, error type {Colors.ENDC}{error_type}{Colors.WARNING}, attributes: {Colors.ENDC}{attrs_formatted}{Colors.WARNING}")
                #     bar()
                #     continue

                outline_geom = outline_dict[scrap_id]
                
                _type = (feat.GetField("_TYPE") or "").strip().lower()
                _clip = (feat.GetField("_CLIP") or "").strip().lower()

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
                    attrs = []
                    
                    for i in range(in_defn.GetFieldCount()):
                        field_name = in_defn.GetFieldDefn(i).GetNameRef()
                        field_value = feat.GetField(i)
                        attrs.append(f"{Colors.ENDC}{field_name}{Colors.WARNING}={Colors.ENDC}{field_value}{Colors.WARNING}")                
          
                    attrs_formatted = ', '.join(attrs)
            
                    log.warning(f"Any intersection issue, attributes: {Colors.ENDC}{attrs_formatted}{Colors.WARNING}")
                    bar()
                    continue

                inter_geom = geom.Intersection(outline_geom)

                if inter_geom is None or inter_geom.IsEmpty():
                    bar()
                    continue

                new_feat = ogr.Feature(out_defn)
                new_feat.SetGeometry(inter_geom)

                for i in range(out_defn.GetFieldCount()):
                    new_feat.SetField(out_defn.GetFieldDefn(i).GetNameRef(), feat.GetField(i))

                out_layer.CreateFeature(new_feat)
                new_feat = None
                bar()

        # -------------------------------------------------
        # CLEANUP
        # -------------------------------------------------
        ds_in = None
        ds_outline = None
        ds_out = None

        return countObjetsInput
    
    except RuntimeError as e:
        log.error(f"cutGPKG, unable to validate geometry: {e}, continuing anyway.")
        globalDat.errorCount += 1
        return -1

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
    try :

        log.info(f"Extract vertices from : {Colors.ENDC}{input_gpkg_path}{Colors.INFO} to {Colors.ENDC}{output_gpkg_path}")

        # -------------------------------------------------
        # OPEN INPUT
        # -------------------------------------------------
        ds_in = ogr.Open(input_gpkg_path)
        if ds_in is None:
            log.error(f"Extract vertices, cannot open file : {Colors.ENDC}{input_gpkg_path}")
            globalDat.errorCount += 1
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
            globalDat.errorCount += 1
            return

        # -------------------------------------------------
        # CREATE OR OPEN OUTPUT
        # -------------------------------------------------
        driver = ogr.GetDriverByName("GPKG")

        if os.path.exists(output_gpkg_path):
            ds_out = ogr.Open(output_gpkg_path, update=1)
            if ds_out is None:
                log.error(f"Extract vertices, cannot open file : {Colors.ENDC}{output_gpkg_path}{Colors.ERROR} in update mode.")
                globalDat.errorCount += 1
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

        with alive_bar(len(layer_in), title=f"{Colors.YELLOW}Extract vertices {Colors.ENDC}{input_gpkg_path}{Colors.ENDC}", length=20) as bar:

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
    
    except RuntimeError as e:
        log.error(f"extractVertices, unable to validate geometry: {e}, continuing anyway.")
        globalDat.errorCount += 1

#################################################################################################    
def diagnostic(file_path):
    try:
        
        start_time = time.time()
        
        if not os.path.exists(file_path):
            log.error(f"diagnostic, fichier non trouvé : {Colors.ENDC}{file_path}")
            globalDat.errorCount += 1
            return -1, -1
        
        ds = ogr.Open(file_path)
        
        if ds is None:
            log.error(f"Impossible d'ouvrir le fichier : {Colors.ENDC}{file_path}")
            globalDat.errorCount += 1
            return -1, -1

        layer = ds.GetLayer()

        total = 0
        invalid = 0
        empty = 0
        multi_geom_count = 0
        geom_types = defaultdict(int)
        has_z = False
        has_m = False
        field_stats = defaultdict(list)
        
        error_codes = defaultdict(int) 
        error_types = defaultdict(int) 
        error_messages = defaultdict(int)
        
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
                code, error_type, error_msg = get_geometry_error(geom)
                error_codes[code] += 1
                error_types[error_type] += 1
                error_messages[error_msg] += 1

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

        log.info(f"==================== BILAN FILE: {Colors.ENDC}{safe_relpath(file_path)}{Colors.INFO} ===================================")
        log.debug(f"Temps d'analyse : {Colors.ENDC}{elapsed:.2f}{Colors.DEBUG} s")
        log.debug(f"Taille : {Colors.ENDC}{file_size:.2f}{Colors.DEBUG} Mo")
        log.debug(f"Nombre d'objets :  {Colors.ENDC}{total}")
        
        if empty == 0 : 
            log.debug(f"Géométries vides : {Colors.ENDC}{empty}")
        else :  
            log.warning(f"Géométries vides : {Colors.ENDC}{empty}")
        
        if invalid == 0 : 
            log.info(f"Géométries invalides : {Colors.ENDC}{invalid}{Colors.INFO} sur  {Colors.ENDC}{total}")
        else : 
            log.warning(f"Géométries invalides : {Colors.ENDC}{invalid}{Colors.WARNING} sur  {Colors.ENDC}{total}")
            # for code, count in sorted( error_codes.items(), key=lambda item: item[1], reverse=True ): 
            #     log.warning( f"\t\t{Colors.ENDC}{str(code):<20}{Colors.WARNING}: {Colors.ENDC}{count}" )
            for error, count in sorted( error_types.items(), key=lambda item: item[1], reverse=True ): 
                log.warning( f"\t\t{Colors.ENDC}{error}{Colors.WARNING} : {Colors.ENDC}{count}" )
        
        log.debug(f"MultiGeometries / Collections : {Colors.ENDC}{multi_geom_count}")
        
        log.debug("Types géométriques :")
        for gtype, count in geom_types.items():
            log.debug(f"\t\t{gtype} : {Colors.ENDC}{count}")

        log.debug("Bounding box :")
        log.debug(f"\t\txmin = {Colors.ENDC}{extent[0]:>8.3f}{Colors.DEBUG}\txmax = {Colors.ENDC}{extent[1]:>8.3f}")
        log.debug(f"\t\tymin = {Colors.ENDC}{extent[2]:>8.3f}{Colors.DEBUG}\tymax = {Colors.ENDC}{extent[3]:>8.3f}")

        log.debug(f"CRS : {Colors.ENDC}{crs}")

        log.debug(f"Dimensions, Z présent : {Colors.ENDC}{has_z}{Colors.DEBUG}\tM présent : {Colors.ENDC}{has_m}")
        
        log.debug("Champs attributaires :")
        
        for field, values in field_stats.items():
            unique_count = len(set(values))
            # log.debug(f"\t\t{Colors.ENDC}{field}{Colors.DEBUG}\t\t: {Colors.ENDC}{len(values)}{Colors.DEBUG} valeurs,\t\t{Colors.ENDC}{unique_count}{Colors.DEBUG} uniques")
            # Définir une largeur fixe pour les noms de champs (par exemple 20 caractères)
            field_width = 20
            number_width = 10

            log.debug(
                f"\t\t{Colors.ENDC}{field:<{field_width}}{Colors.DEBUG}: "
                f"{Colors.ENDC}{len(values):>{number_width}}{Colors.DEBUG} valeurs, "
                f"{Colors.ENDC}{unique_count:>{number_width}}{Colors.DEBUG} uniques"
            )

        log.info(f"=========================================================================================================")

        ds = None
        
        return invalid, total
    
    except RuntimeError as e:
        log.error(f"diagnostic, unable to validate geometry: {e}, continuing anyway.")
        globalDat.errorCount += 1
        return -1, -1

#################################################################################################
def get_geometry_error(geom):
    """
    Analyse la validité d'une géométrie OGR.

    Retourne :
        code       : code d'erreur entier fourni par GDAL/OGR
        error_type : type d'erreur normalisé
        error_msg  : message complet retourné par GEOS/OGR
    """

    if geom is None:
        return ( -1, "Null geometry", "Geometry is None" )

    if geom.IsEmpty():
        return ( -1, "Empty geometry", "Geometry is empty" )
        
    # ------------------------------------------------------------------
    # GEOMETRYCOLLECTION / MULTI*
    # ------------------------------------------------------------------

    geom_name = geom.GetGeometryName().upper()

    if geom_name == "GEOMETRYCOLLECTION":
        return -2, "Not supported", "Geometry not checked (GEOMETRYCOLLECTION)"

    error_messages = []

    def error_handler(err_class, err_no, message):
        error_messages.append((err_no, message))

    # Intercepte les messages GDAL/GEOS
    gdal.PushErrorHandler(error_handler)

    try:
        valid = geom.IsValid()
        
    finally:
        gdal.PopErrorHandler()

    # Géométrie valide
    if valid:
        return (
            0,
            "Valid",
            "Geometry is valid"
        )

    # Récupération du code et du message GEOS
    if error_messages:
        code, error_msg = error_messages[0]
    
    else:
        code = -1
        error_msg = "Invalid geometry"

    # Normalisation du type d'erreur
    msg = error_msg.lower()

    if "ring self-intersection" in msg:
        error_type = "Ring self-intersection"

    elif "self-intersection" in msg:
        error_type = "Self-intersection"

    elif "hole lies outside shell" in msg:
        error_type = "Hole lies outside shell"

    elif "nested shells" in msg:
        error_type = "Nested shells"

    elif "too few points" in msg:
        error_type = "Too few points"

    elif "duplicate rings" in msg:
        error_type = "Duplicate rings"

    elif "invalid coordinate" in msg:
        error_type = "Invalid coordinate"

    else:
        error_type = f"Unknown ({code})"

    return code, error_type, error_msg
        
#################################################################################################
def fix_geometry(feature, infile, layer_defn):
    
    try:
        geom = feature.GetGeometryRef()
        GetFID = feature.GetFID()
        
        if geom is None:
            return None

        geom = geom.Clone()

        geom.CloseRings()   # ferme anneaux
                
        # geom = geom.RemoveDuplicatePoints()  # supprime points dupliqués

        if not geom.IsValid():  # corrige topologie
            geom_type = geom.GetGeometryName() if geom else "None"
            
            code, error_type, error_msg = get_geometry_error(geom)
            
            # Récupérer les attributs de l'objet
            attrs = []
            for i in range(layer_defn.GetFieldCount()):
                field_name = layer_defn.GetFieldDefn(i).GetNameRef()
                field_value = feature.GetField(i)
                attrs.append(f"{Colors.ENDC}{field_name}{Colors.ERROR}={Colors.ENDC}{field_value}{Colors.ERROR}")                
          
            attrs_formatted = ', '.join(attrs)
            
            if error_type == "Too few points" :
                log.debug(
                    f"geometry in file : {Colors.ENDC}{infile}{Colors.DEBUG}, "
                    f"geometry type: {Colors.ENDC}{geom_type}{Colors.DEBUG}, "
                    f"FID: {Colors.ENDC}{GetFID}{Colors.DEBUG}, "
                    f"message code: {Colors.ENDC}{code}{Colors.DEBUG}, {Colors.ENDC}{error_msg}{Colors.DEBUG}, "
                    # f"attributes: {Colors.ENDC}{attrs_formatted}{Colors.DEBUG}"
                )
            
            elif error_type == "Not supported" :
                log.debug(
                    f"geometry in file : {Colors.ENDC}{infile}{Colors.DEBUG}, "
                    f"geometry type: {Colors.ENDC}{geom_type}{Colors.DEBUG}, "
                    f"FID: {Colors.ENDC}{GetFID}{Colors.DEBUG}, "
                    f"message code: {Colors.ENDC}{code}{Colors.DEBUG}, {Colors.ENDC}{error_msg}{Colors.DEBUG}, "
                    # f"attributes: {Colors.ENDC}{attrs_formatted}{Colors.DEBUG}"
                )
                
            else : 
                error_info = (
                    f"invalid geometry in file : {Colors.ENDC}{infile}{Colors.ERROR}, "
                    f"geometry type: {Colors.ENDC}{geom_type}{Colors.ERROR}, "
                    f"FID: {Colors.ENDC}{GetFID}{Colors.ERROR}, "
                    f"message code: {Colors.ENDC}{code}{Colors.ERROR}, {Colors.ENDC}{error_msg}{Colors.ERROR}, "
                    f"attributes: {Colors.ENDC}{attrs_formatted}{Colors.ERROR}"
                )
                log.error(f"{error_info}")
                globalDat.geometryErrors.append(error_info)
                globalDat.errorCount += 1

            geom = geom.MakeValid()
            if not geom.IsValid():
                return None

        if geom is None or geom.IsEmpty(): # supprime géométries vides
            log.warning(f"Empty geometry removed FID {Colors.ENDC}{GetFID}")
            return None

        gtype = geom.GetGeometryType()

        if gtype in (ogr.wkbLineString, ogr.wkbLineString25D):
            if geom.GetPointCount() < 2:
                log.warning(f"Line geometry removed, insufficient number of points < 2 {Colors.ENDC}{GetFID}")
                return None

        if gtype == ogr.wkbPolygon:
            ring = geom.GetGeometryRef(0)
            if ring is None or ring.GetPointCount() < 4:
                log.warning(f"Polygon geometry removed, insufficient number of points < 4 {Colors.ENDC}{GetFID}")
                return None

        return geom

    except Exception as e:
        log.error(f"Geometry in file {Colors.ENDC}{infile}{Colors.ERROR}, cannot be repaired : FID {Colors.ENDC}{GetFID}{Colors.ERROR}, code : {Colors.ENDC}{e}")
        globalDat.errorCount += 1
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
    
    # geom_stats = defaultdict(int)

    try:        

        # sécurité GDAL_DATA
        if not gdal.GetConfigOption("GDAL_DATA"):
            gdal.SetConfigOption("GDAL_DATA", "/usr/share/gdal")

        gdal.SetConfigOption("OGR_GEOMETRY_ACCEPT_UNCLOSED_RING", "YES")

        # ouverture SHP
        ds = ogr.Open(input_shp)
        
        if ds is None:
            log.error(f"shp2gpkg, impossible d'ouvrir le SHP : {Colors.ENDC}{input_shp}")
            globalDat.errorCount += 1
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
        
        log.info(f"SHP file conversion : {Colors.ENDC}{infile}.shp{Colors.INFO} with {Colors.ENDC}{total_count}{Colors.INFO} objets")

        with alive_bar(len(layer), title=f"{Colors.YELLOW}Conversion SHP file {Colors.ENDC}{infile}{Colors.YELLOW} to GPKG {Colors.ENDC}" ,  length = 20) as bar:
            for feature in layer:

                geom = fix_geometry(feature, infile, layer_defn)
                
                if geom is None : 
                    log.warning(f"Géométrie impossible à corriger FID")
                    error_count += 1
                    
                # geom_type_name = geom.GetGeometryName()
                # geom_stats[geom_type_name] += 1

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

    except RuntimeError as e:

        if log:
            log.error(f"Error in conversion file {infile} SHP to GPKG : {e}")
            globalDat.errorCount += 1
        
        return
            
    
    # except Exception as e:

    #     if log:
    #         log.error(f"Error in conversion file {infile} SHP to GPKG : {e}")
    #         globalDat.errorCount += 1

    #     raise

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
                globalDat.errorCount += 1
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
                globalDat.errorCount += 1
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
                globalDat.errorCount += 1

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
            globalDat.errorCount += 1

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
        globalDat.errorCount += 1
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
        
    log.info(f"{Colors.HEADER}{Colors.UNDERLINE}Step 1: test files and convert to GPKG format in the folder:{Colors.ENDC} {safe_relpath(outputspath)}")
    
    count = 0
    
    for fname in file_list:
        count+= 1
        log.info(f"Working with file ({Colors.ENDC}{count}/{len(file_list)}{Colors.INFO}): {Colors.ENDC}{fname}.shp")
        
        file = os.path.join(pathshp, fname + '.shp')
        
        if not os.path.isfile(file):
            log.error(f"ERROR the file {Colors.ENDC}{(str(file))}{Colors.ERROR} does not exist'{Colors.ENDC}")
            globalDat.errorCount += 1
            continue    
                   
        err, valid = diagnostic(file)
        
        if fname in dest_list :
            destinationName = fname 
        
        else :
            destinationName = fname +  '_fixed'
            
        shp2gpkg(pathshp, fname, outputspath,  destinationName) 
        
        if err != 0 :
            err2, valid2 = diagnostic(os.path.join(outputspath,destinationName + '.gpkg'))

            if err2 != 0 : 
                log.error(f"ERROR: in file {Colors.ENDC}{(str(outputspath + destinationName + '.gpkg'))} {Colors.ERROR} please fix it manually with QGis...")
                globalDat.errorCount += 1
                return False


    log.info(f"{Colors.HEADER}{Colors.UNDERLINE}Step 2: adapte drawing files (cut it) for QGis in the folder:{Colors.ENDC} {safe_relpath(outputspath)}")
    
    ## Work with lines
    file_path = os.path.join(outputspath, 'lines2d_fixed.gpkg')
    valid = cutGPKG(file_path, os.path.join(outputspath,'outline2d.gpkg'), os.path.join(outputspath,'lines2dMasked.gpkg'))     
    err, valid2 = diagnostic(os.path.join(outputspath,'lines2dMasked.gpkg'))
    
    if (valid2 - valid) != 0 :
        log.warning(f"{Colors.ENDC}{abs(valid2 - valid)}{Colors.WARNING} deleted geometries need to be verified in {Colors.ENDC}lines2dMasked.gpkg{Colors.WARNING} file") 
    else :
        log.info(f"{Colors.ENDC}{valid}{Colors.INFO} clipped geometries in {Colors.ENDC}lines2dMasked.gpkg{Colors.INFO} file") 
        
    if os.path.exists(file_path):
        os.remove(file_path)
          
    ## Work with Areas  
    file_path = os.path.join(outputspath, 'areas2d_fixed.gpkg')      
    valid = cutGPKG(file_path, os.path.join(outputspath,'outline2d.gpkg'), os.path.join(outputspath,'areas2dMasked.gpkg'))    
    err, valid2 = diagnostic(os.path.join(outputspath,'areas2dMasked.gpkg'))    
    
    if (valid2 - valid) != 0 :
        log.warning(f"{Colors.ENDC}{abs(valid2 - valid)}{Colors.WARNING} Deleted geometries need to be verified in {Colors.ENDC}areas2d_fixed.gpkg{Colors.WARNING} file") 
    else :
        log.info(f"{Colors.ENDC}{valid}{Colors.INFO} clipped geometries in {Colors.ENDC}areas2d_fixed.gpkg{Colors.INFO} file") 
    
    if os.path.exists(file_path):
        os.remove(file_path)
    
    ## Work with Points 'add altitudes' 
    # extractVertices(os.path.join(outputspath,'lines2dMasked.gpkg'), os.path.join(outputspath,'points2d.gpkg'))
    # diagnostic(os.path.join(outputspath,'points2d.gpkg')) 
    
   

#####################################################################################################################################
#                                                                                                                                   #
#                                                           Main                                                                    #
#                                                                                                                                   #
#####################################################################################################################################
if __name__ == u'__main__':	
	#################################################################################################
    ogr.UseExceptions()
    gdal.UseExceptions()
    gdal.PushErrorHandler("CPLQuietErrorHandler")
    gdal.SetConfigOption("SHAPE_ENCODING", "UTF-8")
    gdal.SetConfigOption("OGR_CHARSET", "UTF-8")
    gdal.SetConfigOption("OGR_GPKG_ENCODING", "UTF-8")
    
    globalDat.errorCount = 0
    input_folder_name =""
    start_time = time.time()

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
            f"manual\t-> Manual selection by a window box for the input folder\n"
            f"test\t-> Tests fonction (debug)\n"
        )
    )

    parser.add_argument(
        '--folder',
        type=str,
        help="Input folder containing the shapefiles to process"
    )

    
    parser.epilog = (
        f"{Colors.HEADER}Note : {Colors.GREEN}to generate shp files in therion, add in thconfig file the commande\n"
        f"\t{Colors.GREEN}-> {Colors.ENDC}export model -fmt esri -o Outputs/SHP/ -enc UTF-8{Colors.ENDC}\n"
        f"\n"
        f"{Colors.HEADER}Usage examples :{Colors.ENDC}\n"
        f"\t{Colors.GREEN}-> {Colors.ENDC}python pyThtoQgis.py --folder \"../../Outputs/SHP/\"{Colors.ENDC}\n"
        f"\t{Colors.GREEN}-> {Colors.ENDC}python pyThtoQgis.py --option manual{Colors.ENDC}\n"
    )

    # Analyser les arguments de ligne de commande
    args = parser.parse_args()
    
    if os.name == 'posix':  os.system('clear') # Linux, MacOS
    elif os.name == 'nt':  os.system('cls')# Windows
    else: print("\n" * 100) 
    
    #################################################################################################
    if args.folder :
        
        input_folder =  os.path.normpath(args.folder)
        output_folder = os.path.join(input_folder,globalDat.outputfolder)
        
        if not os.path.exists(input_folder):
            log = setup_logger(globalDat.output_log, globalDat.debug_log)
            log.error(f"ERROR the folder {Colors.ENDC}{input_folder}{Colors.ERROR} does not exist'{Colors.ENDC}")
            globalDat.errorCount += 1
            sys.exit() 
        
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)  
            
        log = setup_logger(os.path.join(output_folder,globalDat.file_log), globalDat.debug_log)
          
        log.info(f'{Colors.HEADER}*********************************************************************************************************')
        log.info(f'{Colors.HEADER}Script to generate QGis (.gpkg) files from Therion (.shp) files with auto-correction if possible')
        log.info(f'{Colors.HEADER}        original written by X. Robert, ISTerre : {Colors.ENDC}October 2022')
        log.info(f'{Colors.HEADER}        updated by : {Colors.ENDC}alexandre.pont@yahoo.fr')
        log.info(f'{Colors.HEADER}        version : {Colors.ENDC}{globalDat.Version}')
        log.info(f'{Colors.HEADER}        commande line mode')
        log.info(f'{Colors.HEADER}        input folder :  {Colors.ENDC}{safe_relpath(input_folder)}')
        log.info(f'{Colors.HEADER}        output folder : {Colors.ENDC}{safe_relpath(output_folder)}')
        log.info(f'{Colors.HEADER}        log file      : {Colors.ENDC}{safe_relpath(next((h.baseFilename for h in log.handlers if isinstance(h, logging.FileHandler)), None))}')
        log.info(f'{Colors.HEADER}*********************************************************************************************************')
        
        ThtoQGis(input_folder, output_folder)
        
    
    elif args.option == "auto" : 
        log = setup_logger(globalDat.output_log, globalDat.debug_log)
        
        if not os.path.exists(globalDat.outputspath):
            os.makedirs(globalDat.outputspath)
        
        log.info(f'{Colors.HEADER}*********************************************************************************************************')
        log.info(f'{Colors.HEADER}Script to generate QGis (.gpkg) files from Therion (.shp) files with auto-correction if possible')
        log.info(f'{Colors.HEADER}        original written by X. Robert, ISTerre : {Colors.ENDC}October 2022')
        log.info(f'{Colors.HEADER}        updated by : {Colors.ENDC}alexandre.pont@yahoo.fr')
        log.info(f'{Colors.HEADER}        version : {Colors.ENDC}{globalDat.Version}')
        log.info(f'{Colors.HEADER}        auto mode')
        log.info(f'{Colors.HEADER}        input folder :  {Colors.ENDC}{globalDat.pathshp}')
        log.info(f'{Colors.HEADER}        output folder : {Colors.ENDC}{globalDat.outputspath}')
        log.info(f'{Colors.HEADER}*********************************************************************************************************')
        
        ThtoQGis(globalDat.pathshp, globalDat.outputspath)
        
    
    elif args.option == "manual" :
        root = tk.Tk()
        root.withdraw()  # Cacher la fenêtre principale de Tkinter
        input_folder_name = filedialog.askdirectory( title="Choose the shp folder")       
        
        input_folder = input_folder_name + "\\"
        output_folder = input_folder + globalDat.outputfolder
        
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        log = setup_logger(output_folder + globalDat.file_log, globalDat.debug_log)
        
        if not input_folder_name:
            log.error(f"No folder selected. The program will terminate")
            globalDat.errorCount += 1
            sys.exit()    
    
        
        log.info(f'{Colors.HEADER}*********************************************************************************************************')
        log.info(f'{Colors.HEADER}Script to generate QGis (.gpkg) files from Therion (.shp) files with auto-correction if possible')
        log.info(f'{Colors.HEADER}        original written by X. Robert, ISTerre : {Colors.ENDC}October 2022')
        log.info(f'{Colors.HEADER}        updated by : {Colors.ENDC}alexandre.pont@yahoo.fr')
        log.info(f'{Colors.HEADER}        version : {Colors.ENDC}{globalDat.Version}')
        log.info(f'{Colors.HEADER}        manual mode')
        log.info(f'{Colors.HEADER}        input folder :  {Colors.ENDC}{safe_relpath(input_folder)}')
        log.info(f'{Colors.HEADER}        output folder : {Colors.ENDC}{safe_relpath(output_folder)}')
        log.info(f'{Colors.HEADER}*********************************************************************************************************')
        
        ThtoQGis(input_folder, output_folder)
        
    
    elif args.option == "test" :
        
        log = setup_logger(globalDat.output_log, globalDat.debug_log)
        
        if not os.path.exists(globalDat.outputspath):
            os.makedirs(globalDat.outputspath)
        
        log.info(f'{Colors.HEADER}*********************************************************************************************************')
        log.info(f'{Colors.HEADER}Script to generate QGis (.gpkg) files from Therion (.shp) files with auto-correction if possible')
        log.info(f'{Colors.HEADER}        original written by X. Robert, ISTerre : {Colors.ENDC}October 2022')
        log.info(f'{Colors.HEADER}        updated by : {Colors.ENDC}alexandre.pont@yahoo.fr')
        log.info(f'{Colors.HEADER}        version : {Colors.ENDC}{globalDat.Version}')
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
        
#################################################################################################
elapsed = time.time() - start_time

if globalDat.errorCount == 0 : 
    log.info(f"{Colors.HEADER}=========================================================================================================")             
    log.info(f"{Colors.HEADER}Execution completed without errors in {Colors.ENDC}{elapsed:.2f}{Colors.HEADER} s")
    log.info(f"{Colors.HEADER}=========================================================================================================")

else :
    log.error(f"{Colors.HEADER}=========================================================================================================")
    log.error(f"{Colors.HEADER}Execution completed with {Colors.ENDC}{globalDat.errorCount}{Colors.ERROR} errors in {Colors.ENDC}{elapsed:.2f}{Colors.HEADER} s")
    for i, error in enumerate(globalDat.geometryErrors, start=1):
        log.error(f"{error}")
    log.error(f"{Colors.HEADER}=========================================================================================================")

            


 