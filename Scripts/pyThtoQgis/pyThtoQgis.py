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
import sys, os, argparse, time, math, logging, struct
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
    try : 
        log.info(f"Clipping file : {Colors.ENDC}{safe_relpath(input_gpkg_path)}{Colors.INFO} to file : {Colors.ENDC}{safe_relpath(output_gpkg_path)}")

        # -------------------------------------------------
        # OPEN INPUT
        # -------------------------------------------------
        ds_in = ogr.Open(input_gpkg_path)
        
        if ds_in is None:
            log.error(f"cutGPKG, cannot open file : {Colors.ENDC}{safe_relpath(input_gpkg_path)}")
            globalDat.errorCount += 1
            return -1

        layer_in = ds_in.GetLayer()
        in_defn = layer_in.GetLayerDefn()
        srs = layer_in.GetSpatialRef()
        geom_type = layer_in.GetGeomType()

        # Vérification présence champ _SCRAP_ID
        idx_scrap = in_defn.GetFieldIndex("_SCRAP_ID")
        
        if idx_scrap == -1:
            log.error(f"cutGPKG, field {Colors.ENDC}'_SCRAP_ID'{Colors.ERROR} not found in input layer.")
            globalDat.errorCount += 1
            return -1

        # -------------------------------------------------
        # OPEN OUTLINES
        # -------------------------------------------------
        ds_outline = ogr.Open(outlines_path)
        
        if ds_outline is None:
            log.error(f"cutGPKG, cannot open file : {Colors.ENDC}{safe_relpath(outlines_path)}")
            globalDat.errorCount += 1
            return -1

        layer_outline = ds_outline.GetLayer()
        outline_defn = layer_outline.GetLayerDefn()

        idx_id = outline_defn.GetFieldIndex("_ID")
        
        if idx_id == -1:
            log.error(f"cutGPKG, field {Colors.ENDC}'_ID'{Colors.ERROR} not found in outlines layer.")
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
        log.error(f"cutGPKG in file {Colors.ENDC}{safe_relpath(outlines_path)}{Colors.ERROR}, unable to validate geometry: {Colors.ENDC}{e}{Colors.ERROR}, continuing anyway.")
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
                    if n < 2: return

                    for i in range(n):
                        x, y, z, m = ls.GetPointZM(i)

                        if m != 16: continue

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

# ======================================================================
# FONCTION : ATTRIBUTS DIRECT
# ======================================================================
def get_dbf_attributes_direct(file_path, record_index):
    """
    Lecture directe du DBF associé à un Shapefile.

    Ne passe PAS par OGR et ne lit PAS le SHP.
    Permet donc de récupérer les attributs d'un objet dont
    la géométrie SHP est corrompue.

    record_index :
        index du record DBF à partir de 0.
        Pour FID 46 => record_index = 46
    """

    dbf_path = os.path.splitext(file_path)[0] + ".dbf"

    try:

        if not os.path.exists(dbf_path):
            log.error(f"DBF introuvable : {Colors.ENDC}{safe_relpath(dbf_path)}" )
            globalDat.errorCount += 1
            return {}

        with open(dbf_path, "rb") as f:

            # ==========================================================
            # EN-TETE DBF
            # ==========================================================

            header = f.read(32)

            if len(header) != 32:
                log.error(f"DBF invalide ou tronqué : {Colors.ENDC}{safe_relpath(dbf_path)}")
                globalDat.errorCount += 1
                return {}

            # Nombre de records
            num_records = struct.unpack("<I", header[4:8])[0]

            # Taille de l'en-tête
            header_length = struct.unpack("<H", header[8:10])[0]

            # Taille d'un record
            record_length = struct.unpack("<H", header[10:12])[0]

            if record_index < 0 or record_index >= num_records:
                log.error(f"Record DBF hors limites : {Colors.ENDC}{record_index}{Colors.ERROR} / {Colors.ENDC}{num_records}")
                globalDat.errorCount += 1
                return {}

            # ==========================================================
            # LECTURE DES DESCRIPTIONS DE CHAMPS
            # ==========================================================

            fields = []

            while True:
                descriptor = f.read(32)

                if len(descriptor) != 32:
                    log.error("Fin inattendue des descripteurs DBF")
                    globalDat.errorCount += 1
                    return {}

                # 0x0D = fin des descripteurs
                if descriptor[0] == 0x0D:
                    break

                # ------------------------------------------------------
                # Nom du champ : 11 octets
                # ------------------------------------------------------

                field_name = (descriptor[0:11].split(b"\x00", 1)[0].decode("ascii", errors="replace").strip())

                # Type
                field_type = chr(descriptor[11])

                # Taille
                field_length = descriptor[16]

                # Nombre de décimales
                decimal_count = descriptor[17]

                fields.append({"name": field_name, "type": field_type, "length": field_length, "decimals": decimal_count})

            # ==========================================================
            # POSITION DU RECORD
            # ==========================================================

            record_offset = (header_length+ record_index * record_length)
            f.seek(record_offset)
            record = f.read(record_length)

            if len(record) != record_length:
                log.error(f"Record DBF incomplet : FID {Colors.ENDC}{record_index}")
                globalDat.errorCount += 1
                return {}

            # ==========================================================
            # RECORD SUPPRIME ?
            # ==========================================================

            deletion_flag = record[0]

            if deletion_flag == 0x2A:  # '*'
                log.warning(f"Record DBF {Colors.ENDC}{record_index}{Colors.WARNING} marqué comme supprimé")

            # ==========================================================
            # LECTURE DES VALEURS
            # ==========================================================

            attributes = {}
            position = 1

            for field in fields:

                length = field["length"]
                raw_value = record[position:position + length]
                position += length

                # ------------------------------------------------------
                # Décodage
                # ------------------------------------------------------

                # On tente UTF-8 puis CP1252
                try:
                    value = raw_value.decode("utf-8")

                except UnicodeDecodeError:
                    value = raw_value.decode("cp1252", errors="replace")

                value = value.strip()

                # ------------------------------------------------------
                # Conversion selon type DBF
                # ------------------------------------------------------

                field_type = field["type"]

                if value == "":
                    value = None

                elif field_type in ("N", "F"):
                    try:
                        if (field["decimals"] == 0 and "." not in value ):
                            value = int(value)

                        else:
                            value = float(value)

                    except ValueError:
                        pass

                elif field_type == "L":
                    if value.upper() == "Y": value = True
                    elif value.upper() == "N": value = False

                attributes[field["name"]] = value

            return attributes

    except Exception as e:
        log.error(f"Erreur lecture directe DBF FID {Colors.ENDC}{record_index}{Colors.ERROR} : {Colors.ENDC}{e}")
        globalDat.errorCount += 1
        return {}

# ======================================================================
# FONCTION : AFFICHAGE ATTRIBUTS
# ======================================================================
def log_feature_attributes(attributes, level="debug"):
    if level=="error":
        log.error(f"Attributs de l'objet :")
        if not attributes :
            log.error("Attributs : indisponibles")
            return

        for field_name, value in attributes.items():
            log.error(f"\t\t{Colors.ENDC}{field_name}{Colors.ERROR} = {Colors.ENDC}{value}")
        
    else :
        log.debug(f"Attributs de l'objet :")
        if not attributes :
            log.error("Attributs : indisponibles")
            return

        for field_name, value in attributes.items():
            log.debug(f"\t\t{Colors.ENDC}{field_name}{Colors.DEBUG} = {Colors.ENDC}{value}")
    
#################################################################################################
def diagnosticNew(file_path):
    """
    Diagnostic robuste d'un fichier vectoriel OGR/GDAL.

    Analyse :
        - nombre total de features
        - géométries vides
        - géométries invalides OGC
        - géométries illisibles/corrompues
        - géométries multiparties
        - parties vides dans les multiparties
        - structure des multiparties
        - types géométriques
        - présence Z / M
        - emprise
        - CRS
        - statistiques des champs attributaires

    En cas d'erreur GDAL sur un feature :
        - l'erreur est enregistrée
        - les attributs sont affichés lorsqu'ils sont accessibles
        - le traitement du fichier continue autant que possible

    Retour :
        (invalid, total)
    """

    start_time = time.time()
    
    ds = None
    total = 0
    invalid = 0
    empty = 0
    geometry_read_errors = 0
    geometry_validation_errors = 0
    feature_errors = 0
    multi_geom_count = 0
    multi_geom_valid_count = 0
    multi_geom_empty_part_count = 0
    multi_geom_corrupted_count = 0
    empty_part_count = 0
    total_part_count = 0
    geom_types = defaultdict(int)
    has_z = False
    has_m = False
    field_stats = defaultdict(list)
    error_codes = defaultdict(int)
    error_types = defaultdict(int)
    error_messages = defaultdict(int)
    corrupted_features = []
    field_definitions = []

    # ======================================================================
    # FONCTION : ATTRIBUTS DIRECT
    # ======================================================================
    def get_dbf_attributes_direct(file_path, record_index):
        """
        Lecture directe du DBF associé à un Shapefile.

        Ne passe PAS par OGR et ne lit PAS le SHP.
        Permet donc de récupérer les attributs d'un objet dont
        la géométrie SHP est corrompue.

        record_index :
            index du record DBF à partir de 0.
            Pour FID 46 => record_index = 46
        """

        dbf_path = os.path.splitext(file_path)[0] + ".dbf"

        try:

            if not os.path.exists(dbf_path):
                log.error(f"DBF introuvable : {Colors.ENDC}{safe_relpath(dbf_path)}" )
                globalDat.errorCount += 1
                return {}

            with open(dbf_path, "rb") as f:

                # ==========================================================
                # EN-TETE DBF
                # ==========================================================

                header = f.read(32)

                if len(header) != 32:
                    log.error(f"DBF invalide ou tronqué : {Colors.ENDC}{safe_relpath(dbf_path)}")
                    globalDat.errorCount += 1
                    return {}

                # Nombre de records
                num_records = struct.unpack("<I", header[4:8])[0]

                # Taille de l'en-tête
                header_length = struct.unpack("<H", header[8:10])[0]

                # Taille d'un record
                record_length = struct.unpack("<H", header[10:12])[0]

                if record_index < 0 or record_index >= num_records:
                    log.error(f"Record DBF hors limites : {Colors.ENDC}{record_index}{Colors.ERROR} / {Colors.ENDC}{num_records}")
                    globalDat.errorCount += 1
                    return {}

                # ==========================================================
                # LECTURE DES DESCRIPTIONS DE CHAMPS
                # ==========================================================

                fields = []

                while True:
                    descriptor = f.read(32)

                    if len(descriptor) != 32:
                        log.error("Fin inattendue des descripteurs DBF")
                        globalDat.errorCount += 1
                        return {}

                    # 0x0D = fin des descripteurs
                    if descriptor[0] == 0x0D:
                        break

                    # ------------------------------------------------------
                    # Nom du champ : 11 octets
                    # ------------------------------------------------------

                    field_name = (descriptor[0:11].split(b"\x00", 1)[0].decode("ascii", errors="replace").strip())

                    # Type
                    field_type = chr(descriptor[11])

                    # Taille
                    field_length = descriptor[16]

                    # Nombre de décimales
                    decimal_count = descriptor[17]

                    fields.append({"name": field_name, "type": field_type, "length": field_length, "decimals": decimal_count})

                # ==========================================================
                # POSITION DU RECORD
                # ==========================================================

                record_offset = (header_length+ record_index * record_length)
                f.seek(record_offset)
                record = f.read(record_length)

                if len(record) != record_length:
                    log.error(f"Record DBF incomplet : FID {Colors.ENDC}{record_index}")
                    globalDat.errorCount += 1
                    return {}

                # ==========================================================
                # RECORD SUPPRIME ?
                # ==========================================================

                deletion_flag = record[0]

                if deletion_flag == 0x2A:  # '*'
                    log.warning(f"Record DBF {Colors.ENDC}{record_index}{Colors.WARNING} marqué comme supprimé")

                # ==========================================================
                # LECTURE DES VALEURS
                # ==========================================================

                attributes = {}
                position = 1

                for field in fields:

                    length = field["length"]
                    raw_value = record[position:position + length]
                    position += length

                    # ------------------------------------------------------
                    # Décodage
                    # ------------------------------------------------------

                    # On tente UTF-8 puis CP1252
                    try:
                        value = raw_value.decode("utf-8")

                    except UnicodeDecodeError:
                        value = raw_value.decode("cp1252", errors="replace")

                    value = value.strip()

                    # ------------------------------------------------------
                    # Conversion selon type DBF
                    # ------------------------------------------------------

                    field_type = field["type"]

                    if value == "":
                        value = None

                    elif field_type in ("N", "F"):
                        try:
                            if (field["decimals"] == 0 and "." not in value ):
                                value = int(value)

                            else:
                                value = float(value)

                        except ValueError:
                            pass

                    elif field_type == "L":
                        if value.upper() == "Y": value = True
                        elif value.upper() == "N": value = False

                    attributes[field["name"]] = value

                return attributes

        except Exception as e:
            log.error(f"Erreur lecture directe DBF FID {Colors.ENDC}{record_index}{Colors.ERROR} : {Colors.ENDC}{e}")
            globalDat.errorCount += 1
            return {}

    # ======================================================================
    # FONCTION : ATTRIBUTS
    # ======================================================================
    def get_feature_attributes(feature):
        attributes = {}

        if feature is None: 
            return attributes

        try:
            for field_index, field_name in field_definitions:
                try:
                    value = feature.GetField(field_index)
                    attributes[field_name] = value

                except Exception as e:
                    attributes[field_name] = (f"<ERREUR LECTURE : {Colors.ENDC}{e}>")

        except Exception as e:
            attributes["_ATTRIBUTE_ERROR_"] = str(e)

        return attributes

    # ======================================================================
    # FONCTION : AFFICHAGE ATTRIBUTS
    # ======================================================================
    def log_feature_attributes(attributes, level="debug"):
        if level=="error":
            log.error(f"Attributs de l'objet :")
            if not attributes :
                log.error("Attributs : indisponibles")
                return

            for field_name, value in attributes.items():
                log.error(f"\t\t{Colors.ENDC}{field_name}{Colors.ERROR} = {Colors.ENDC}{value}")
            
        else :
            log.debug(f"Attributs de l'objet :")
            if not attributes :
                log.error("Attributs : indisponibles")
                return

            for field_name, value in attributes.items():
                log.debug(f"\t\t{Colors.ENDC}{field_name}{Colors.DEBUG} = {Colors.ENDC}{value}")
                      
    # ======================================================================
    # FONCTION : ANALYSE MULTIPARTIE
    # ======================================================================
    def analyse_multipart_geometry(geom):

        result = {
            "is_multi": False,
            "part_count": 0,
            "empty_parts": 0,
            "valid_structure": True,
            "error": None
        }

        try:
            geom_name = geom.GetGeometryName().upper()

        except Exception as e:

            result["valid_structure"] = False
            result["error"] = str(e)

            return result

        multipart_types = (
            "MULTIPOINT",
            "MULTILINESTRING",
            "MULTIPOLYGON",
            "GEOMETRYCOLLECTION"
        )

        if geom_name not in multipart_types:
            return result

        result["is_multi"] = True

        # --------------------------------------------------------------
        # Nombre de parties
        # --------------------------------------------------------------

        try:
            part_count = geom.GetGeometryCount()
            result["part_count"] = part_count

        except Exception as e:
            result["valid_structure"] = False
            result["error"] = (f"Impossible de récupérer le nombre de parties : {Colors.ENDC}{e}")
            return result

        # --------------------------------------------------------------
        # Analyse de chaque partie
        # --------------------------------------------------------------

        for i in range(part_count):
            try:
                part = geom.GetGeometryRef(i)

            except Exception as e:
                result["valid_structure"] = False
                if result["error"] is None:
                    result["error"] = (f"Impossible de lire la partie {Colors.ENDC}{i}{Colors.ERROR} : {Colors.ENDC}{e}")
                continue

            if part is None:
                result["empty_parts"] += 1
                continue

            try:
                if part.IsEmpty():
                    result["empty_parts"] += 1

            except Exception as e:
                result["valid_structure"] = False

                if result["error"] is None:
                    result["error"] = (f"Impossible de tester la partie {Colors.ENDC}{i}{Colors.ERROR} : {Colors.ENDC}{e}")

        return result

    # ======================================================================
    # FONCTION : AFFICHAGE DETAIL MULTIPARTIE
    # ======================================================================
    def log_multipart_details(geom, fid, geom_name, attributes ):
        """
        Affiche le détail d'une géométrie multipartie :
            - FID
            - type
            - nombre de parties
            - attributs
            - type et nombre de sommets de chaque partie
        """

        try:
            part_count = geom.GetGeometryCount()

        except Exception as e:
            log.error(f"GetGeometryCount, SHAPE {Colors.ENDC}{fid + 1}{Colors.ERROR} / FID {Colors.ENDC}{fid}{Colors.ERROR} : impossible de déterminer le nombre de parties : {Colors.ENDC}{e}")
            globalDat.errorCount += 1
            return

        log.debug(f"MultiGeometry détectée : SHAPE {Colors.ENDC}{fid + 1}{Colors.DEBUG} / FID {Colors.ENDC}{fid}")
        log.debug(f"\t\tType : {Colors.ENDC}{geom_name}")
        log.debug(f"\t\tNombre de parties : {Colors.ENDC}{part_count}")

        # --------------------------------------------------------------
        # Attributs
        # --------------------------------------------------------------
        log_feature_attributes(attributes)

        # --------------------------------------------------------------
        # Parties
        # --------------------------------------------------------------

        for part_index in range(part_count):
            try:
                part = geom.GetGeometryRef(part_index)
                if part is None:
                    log.warning(f"\t\tPartie {Colors.ENDC}{part_index + 1}{Colors.WARNING} : NULL / VIDE")
                    continue

                try:
                    part_type = part.GetGeometryName()

                except Exception:
                    part_type = "UNKNOWN"

                try:
                    point_count = part.GetPointCount()

                except Exception:
                    point_count = "?"

                try:
                    is_empty = part.IsEmpty()

                except Exception:
                    is_empty = "?"

                if is_empty is True:
                    log.warning(f"\t\tPartie {Colors.ENDC}{part_index + 1}{Colors.WARNING} : VIDE")

                else:
                    log.debug(f"\t\tPartie {Colors.ENDC}{part_index + 1}{Colors.DEBUG} : {Colors.ENDC}{part_type}{Colors.DEBUG}, {Colors.ENDC}{point_count}{Colors.DEBUG} sommets")

            except Exception as e:
                log.error(f"\t\tPartie {Colors.ENDC}{part_index + 1}{Colors.ERROR} : erreur lecture : {Colors.ENDC}{e}")
                

    # ======================================================================
    # OUVERTURE
    # ======================================================================
    try:
        log.info(f"==================== BILAN FILE: {Colors.ENDC}{safe_relpath(file_path)}{Colors.INFO} ===================================")

        # ==================================================================
        # EXISTENCE
        # ==================================================================

        if not os.path.exists(file_path):
            log.error(f"diagnostic, fichier non trouvé : {Colors.ENDC}{safe_relpath(file_path)}")
            globalDat.errorCount += 1
            return -1, -1

        # ==================================================================
        # OGR OPEN
        # ==================================================================

        try:
            ds = ogr.Open(file_path)

        except Exception as e:
            log.error(f"Impossible d'ouvrir le fichier : {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR} : {Colors.ENDC}{e}")
            globalDat.errorCount += 1
            return -1, -1

        if ds is None:
            log.error(f"Impossible d'ouvrir le fichier : {Colors.ENDC}{safe_relpath(file_path)}")
            globalDat.errorCount += 1
            return -1, -1

        # ==================================================================
        # LAYER
        # ==================================================================
        try:
            layer = ds.GetLayer()

        except Exception as e:
            log.error(f"Impossible de récupérer la couche : {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR} : {Colors.ENDC}{e}")
            globalDat.errorCount += 1
            return -1, -1

        if layer is None:
            log.error(f"Couche inaccessible : {Colors.ENDC}{safe_relpath(file_path)}")
            globalDat.errorCount += 1
            return -1, -1

        # ==================================================================
        # NOMBRE DE FEATURES
        # ==================================================================
        try:
            feature_count = layer.GetFeatureCount()

        except Exception as e:
            feature_count = -1
            log.warning(f"Impossible de déterminer le nombre de features : {Colors.ENDC}{e}")

        log.debug(f"Nombre de features annoncé par GDAL : {Colors.ENDC}{feature_count}")

        # ==================================================================
        # EXTENT
        # ==================================================================
        try:
            extent = layer.GetExtent()

        except Exception as e:
            extent = None
            log.warning(f"Impossible de récupérer l'emprise : {Colors.ENDC}{e}")

        # ==================================================================
        # CRS
        # ==================================================================
        try:
            srs = layer.GetSpatialRef()
            crs = (srs.ExportToWkt() if srs else "CRS inconnu" )

        except Exception as e:
            crs = "CRS inconnu"
            log.warning(f"Impossible de récupérer le CRS : {Colors.ENDC}{e}")

        # ==================================================================
        # CHAMPS
        # ==================================================================
        try:
            layer_defn = layer.GetLayerDefn()

            for i in range(layer_defn.GetFieldCount()):
                field_definitions.append((i, layer_defn.GetFieldDefn(i).GetNameRef()))

        except Exception as e:
            log.warning(f"Impossible de récupérer les champs : {Colors.ENDC}{e}")

        # ==================================================================
        # PARCOURS PAR FID
        # ==================================================================

        if feature_count >= 0:
            for fid in range(feature_count):
                # ----------------------------------------------------------
                # Lecture du feature
                # ----------------------------------------------------------
                try:
                    feature = layer.GetFeature(fid)

                except Exception as e:
                    geometry_read_errors += 1
                    attributes = get_dbf_attributes_direct(file_path, fid)
                    corrupted_features.append({"index": total + 1, "fid": fid, "shape": fid + 1, "stage": "GetFeature", "error": str(e), "attributes": attributes})

                    log.error(f"GetFeature, SHAPE : {Colors.ENDC}{fid + 1}{Colors.ERROR}, FID : {Colors.ENDC}{fid}{Colors.ERROR}, GetFeature : {Colors.ENDC}{e}" )
                    globalDat.errorCount += 1                    
                    log_feature_attributes(attributes, "error")
                    total += 1
                    continue

                total += 1

                if feature is None:
                    geometry_read_errors += 1
                    corrupted_features.append({"index": total, "fid": fid, "shape": fid + 1, "stage": "GetFeature", "error": "Feature None", "attributes": {}})
                    log.error(f"SHAPE {Colors.ENDC}{fid + 1}{Colors.ERROR} / FID {Colors.ENDC}{fid}{Colors.ERROR} : {Colors.ENDC}GDAL retourne None")
                    globalDat.errorCount += 1   
                    continue

                # ----------------------------------------------------------
                # Attributs
                # ----------------------------------------------------------
                attributes = get_feature_attributes(feature)

                # ----------------------------------------------------------
                # Géométrie
                # ----------------------------------------------------------
                try:
                    geom = feature.GetGeometryRef()

                except Exception as e:
                    geometry_read_errors += 1
                    corrupted_features.append({"index": total, "fid": fid, "shape": fid + 1, "stage": "GetGeometryRef", "error": str(e), "attributes": attributes})
                    log.error(f"SHAPE {Colors.ENDC}{fid + 1}{Colors.ERROR} / FID {Colors.ENDC}{fid}{Colors.ERROR} : {Colors.ENDC}géométrie illisible{Colors.ERROR} : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1   
                    log_feature_attributes(attributes)
                    continue

                # ----------------------------------------------------------
                # Géométrie absente
                # ----------------------------------------------------------
                if geom is None:
                    empty += 1
                    continue

                # ----------------------------------------------------------
                # Géométrie vide
                # ----------------------------------------------------------
                try:
                    if geom.IsEmpty():
                        empty += 1
                        continue

                except Exception as e:
                    geometry_read_errors += 1
                    corrupted_features.append({"index": total, "fid": fid, "shape": fid + 1, "stage": "IsEmpty", "error": str(e), "attributes": attributes })
                    log.error(f"IsEmpty, SHAPE {Colors.ENDC}{fid + 1}{Colors.ERROR} / FID {Colors.ENDC}{fid}{Colors.ERROR} : impossible de tester IsEmpty() : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1   
                    log_feature_attributes(attributes)
                    continue

                # ----------------------------------------------------------
                # Type
                # ----------------------------------------------------------
                try:
                    geom_name = geom.GetGeometryName()
                    geom_types[geom_name] += 1

                except Exception as e:
                    geom_name = "UNKNOWN"
                    log.warning(f"GetGeometryName UNKNOWN, SHAPE {Colors.ENDC}{fid + 1}{Colors.ENDC} / FID {Colors.ENDC}{fid} : impossible de lire le type : {Colors.ENDC}{e}")

                # ==========================================================
                # ANALYSE MULTIPARTIE
                # ==========================================================
                try:
                    multipart = analyse_multipart_geometry(geom)

                    if multipart["is_multi"]:
                        multi_geom_count += 1
                        part_count = multipart["part_count"]
                        total_part_count += part_count
                        empty_parts = multipart["empty_parts"]

                        # --------------------------------------------------
                        # Affichage détaillé
                        # --------------------------------------------------
                        log_multipart_details(geom, fid, geom_name, attributes)

                        # --------------------------------------------------
                        # Multipartie normale
                        # --------------------------------------------------

                        if (multipart["valid_structure"] and empty_parts == 0 ):
                            multi_geom_valid_count += 1

                        # --------------------------------------------------
                        # Multipartie avec partie vide
                        # --------------------------------------------------

                        elif empty_parts > 0:
                            multi_geom_empty_part_count += 1
                            empty_part_count += empty_parts
                            log.warning(f"SHAPE {Colors.ENDC}{fid + 1}{Colors.WARNING} / FID {Colors.ENDC}{fid}{Colors.WARNING} : {Colors.ENDC}MULTIPARTIE AVEC PARTIE VIDE")
                            log.warning(f"\t\tNombre de parties : {Colors.ENDC}{part_count}")
                            log.warning(f"\t\tParties vides : {Colors.ENDC}{empty_parts}")

                        # --------------------------------------------------
                        # Structure non analysable
                        # --------------------------------------------------

                        if not multipart["valid_structure"]:
                            multi_geom_corrupted_count += 1
                            log.error(f"SHAPE {Colors.ENDC}{fid + 1}{Colors.ERROR} / FID {Colors.ENDC}{fid}{Colors.ERROR} : {Colors.ENDC}structure multipartie non analysable")
                            log.error(f"\t\tcode : {Colors.ENDC}{multipart['error']}")
                            globalDat.errorCount += 1   

                except Exception as e:
                    multi_geom_corrupted_count += 1
                    log.error(f"SHAPE {Colors.ENDC}{fid + 1}{Colors.ERROR} / FID {Colors.ENDC}{fid}{Colors.ERROR} : {Colors.ENDC}erreur analyse multipartie : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1   

                # ==========================================================
                # VALIDATION OGC
                # ==========================================================
                try:
                    valid = geom.IsValid()

                except Exception as e:
                    geometry_validation_errors += 1
                    corrupted_features.append({ "index": total, "fid": fid, "shape": fid + 1, "stage": "IsValid", "error": str(e), "attributes": attributes})                    

                    log.error(f"SHAPE {Colors.ENDC}{fid + 1}{Colors.ERROR} / FID {Colors.ENDC}{fid}{Colors.ERROR} : impossible de valider la géométrie : {Colors.ENDC}{e}")
                    log_feature_attributes(attributes)
                    globalDat.errorCount += 1   
                    continue

                # ----------------------------------------------------------
                # Géométrie invalide
                # ----------------------------------------------------------
                if not valid:
                    invalid += 1

                    try:
                        code, error_type, error_msg = (get_geometry_error(geom))
                        error_codes[code] += 1
                        error_types[error_type] += 1
                        error_messages[error_msg] += 1

                    except Exception:
                        error_types["Unknown"] += 1

                # ==========================================================
                # Z / M
                # ==========================================================
                try:
                    gtype = geom.GetGeometryType()

                    if ogr.GT_HasZ(gtype): has_z = True

                    if ogr.GT_HasM(gtype): has_m = True

                except Exception as e:
                    log.warning(f"SHAPE {Colors.ENDC}{fid + 1}{Colors.WARNING} / FID {Colors.ENDC}{fid}{Colors.WARNING} : impossible de déterminer Z/M : {Colors.ENDC}{e}")

                # ==========================================================
                # STATISTIQUES ATTRIBUTAIRES
                # ==========================================================
                try:
                    for field_index, field_name in field_definitions:
                        value = feature.GetField(field_index)

                        if value is not None:
                            field_stats[field_name].append(value)

                except Exception as e:
                    feature_errors += 1
                    log.warning(f"SHAPE {Colors.ENDC}{fid + 1}{Colors.WARNING} / FID {Colors.ENDC}{fid}{Colors.WARNING} : erreur lecture attributs : {Colors.ENDC}{e}")
                    continue

        else:

            # ==================================================================
            # FALLBACK : PARCOURS SEQUENTIEL
            # ==================================================================
            log.warning("Nombre de features inconnu : utilisation du parcours séquentiel.")

            while True:
                try:
                    feature = layer.GetNextFeature()

                except Exception as e:
                    geometry_read_errors += 1
                    log.error(f"Erreur GDAL lors de la lecture du prochain feature du fichier {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR} : {Colors.ENDC}{e}")
                    log.error("Arrêt du parcours des features pour ce fichier, mais poursuite du traitement global.")
                    globalDat.errorCount += 1   
                    break

                if feature is None:
                    break

                total += 1

                try:
                    fid = feature.GetFID()
                
                except Exception:
                    fid = "?"

                attributes = get_feature_attributes(feature)

                try:
                    geom = feature.GetGeometryRef()

                    if geom is None or geom.IsEmpty():
                        empty += 1
                        continue

                    geom_name = geom.GetGeometryName()
                    geom_types[geom_name] += 1

                except Exception as e:
                    geometry_read_errors += 1
                    corrupted_features.append(
                        {
                            "index": total,
                            "fid": fid,
                            "shape": (
                                fid + 1
                                if isinstance(fid, int)
                                else "?"
                            ),
                            "stage": "Geometry",
                            "error": str(e),
                            "attributes": attributes
                        }
                    )

                    log.error(f"Feature {Colors.ENDC}{total}{Colors.ERROR} / FID {Colors.ENDC}{fid}{Colors.ERROR} : erreur géométrie : {Colors.ENDC}{e}")
                    log_feature_attributes(attributes)
                    globalDat.errorCount += 1   
                    continue

                # --------------------------------------------------------------
                # Multipartie
                # --------------------------------------------------------------
                try:
                    multipart = analyse_multipart_geometry(geom)

                    if multipart["is_multi"]:
                        multi_geom_count += 1
                        total_part_count += (multipart["part_count"])
                        log_multipart_details(geom, fid, geom_name, attributes)

                        if multipart["empty_parts"] > 0:
                            multi_geom_empty_part_count += 1
                            empty_part_count += (multipart["empty_parts"])

                        elif multipart["valid_structure"]:
                            multi_geom_valid_count += 1

                        else:
                            multi_geom_corrupted_count += 1

                except Exception as e:
                    multi_geom_corrupted_count += 1
                    log.error(f"Feature {Colors.ENDC}{total}{Colors.ERROR} / FID {Colors.ENDC}{fid}{Colors.ERROR} : erreur analyse multipartie : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1   

                # --------------------------------------------------------------
                # Validation
                # --------------------------------------------------------------
                try:
                    if not geom.IsValid():
                        invalid += 1

                        try:
                            code, error_type, error_msg = ( get_geometry_error(geom))
                            error_codes[code] += 1
                            error_types[error_type] += 1
                            error_messages[error_msg] += 1

                        except Exception:
                            error_types["Unknown"] += 1

                except Exception as e:
                    geometry_validation_errors += 1
                    corrupted_features.append(
                        {
                            "index": total,
                            "fid": fid,
                            "shape": (
                                fid + 1
                                if isinstance(fid, int)
                                else "?"
                            ),
                            "stage": "IsValid",
                            "error": str(e),
                            "attributes": attributes
                        }
                    )

                    log.error(f"Feature {Colors.ENDC}{total}{Colors.ERROR} / FID {Colors.ENDC}{fid}{Colors.ERROR} : impossible de valider : {Colors.ENDC}{e}")
                    log_feature_attributes(attributes)
                    globalDat.errorCount += 1   
                    continue

                # --------------------------------------------------------------
                # Z / M
                # --------------------------------------------------------------
                try:
                    gtype = geom.GetGeometryType()

                    if ogr.GT_HasZ(gtype): has_z = True
                    if ogr.GT_HasM(gtype): has_m = True

                except Exception:
                    pass

                # --------------------------------------------------------------
                # Attributs
                # --------------------------------------------------------------
                try:
                    for field_index, field_name in field_definitions:
                        value = feature.GetField(field_index)
                        if value is not None:
                            field_stats[field_name].append(value)

                except Exception as e :
                    feature_errors += 1

        # ==================================================================
        # BILAN
        # ==================================================================

        elapsed = time.time() - start_time

        try:
            file_size = (os.path.getsize(file_path)/(1024 * 1024))

        except Exception:
            file_size = 0

        
        log.debug(f"Temps d'analyse : {Colors.ENDC}{elapsed:.2f}{Colors.DEBUG} s")
        log.debug(f"Taille : {Colors.ENDC}{file_size:.2f}{Colors.DEBUG} Mo")
        log.debug(f"Nombre d'objets annoncés par GDAL : {Colors.ENDC}{feature_count}")
        log.debug(f"Nombre d'objets analysés : {Colors.ENDC}{total}")

        # ==================================================================
        # VIDES
        # ==================================================================
        if empty == 0:
            log.debug(f"Géométries vides : {Colors.ENDC}{empty}")

        else:
            log.warning(f"Géométries vides : {Colors.ENDC}{empty}")

        # ==================================================================
        # INVALIDES
        # ==================================================================
        if invalid == 0:
            log.info(f"Géométries invalides : {Colors.ENDC}{invalid}{Colors.INFO} sur {Colors.ENDC}{total}")

        else:
            log.warning(f"Géométries invalides : {Colors.ENDC}{invalid}{Colors.WARNING} sur {Colors.ENDC}{total}")

            for error, count in sorted(error_types.items(), key=lambda item: item[1], reverse=True ):
                log.warning(f"\t\t{Colors.ENDC}{error}{Colors.WARNING} : {Colors.ENDC}{count}")

        # ==================================================================
        # CORROMPU / NON ANALYSABLE
        # ==================================================================

        corrupted_count = ( geometry_read_errors + geometry_validation_errors )

        if corrupted_count == 0:
            log.info(f"Géométries corrompues / non analysables : {Colors.ENDC}0")

        else:
            log.error(f"Géométries corrompues / non analysables : {Colors.ENDC}{corrupted_count}")

            for item in corrupted_features:
                log.error(f"SHAPE {Colors.ENDC}{item['shape']}{Colors.ERROR} / FID {Colors.ENDC}{item['fid']}{Colors.ERROR} / {Colors.ENDC}{item['stage']}{Colors.ERROR} : {Colors.ENDC}{item['error']}")
                log_feature_attributes(item["attributes"])

        # ==================================================================
        # MULTIPARTIES
        # ==================================================================
        log.debug(f"MultiGeometries / Collections : {Colors.ENDC}{multi_geom_count}")
        log.debug(f"MultiGeometries avec structure valide : {Colors.ENDC}{multi_geom_valid_count}")
        log.debug(f"MultiGeometries avec partie(s) vide(s) : {Colors.ENDC}{multi_geom_empty_part_count}")
        log.debug(f"MultiGeometries avec structure non analysable : {Colors.ENDC}{multi_geom_corrupted_count}")
        log.debug(f"Nombre total de parties multiparties : {Colors.ENDC}{total_part_count}")

        if multi_geom_count > 0:
            log.debug(f"Nombre moyen de parties par MultiGeometry : {Colors.ENDC}{total_part_count / multi_geom_count:.2f}")

        if empty_part_count > 0:
            log.warning(f"Nombre total de parties vides : {Colors.ENDC}{empty_part_count}")

        # ==================================================================
        # ERREURS
        # ==================================================================
        log.debug(f"Erreurs lecture géométrie : {Colors.ENDC}{geometry_read_errors}")
        log.debug(f"Erreurs validation géométrie : {Colors.ENDC}{geometry_validation_errors}")
        log.debug(f"Erreurs lecture attributs : {Colors.ENDC}{feature_errors}")

        # ==================================================================
        # TYPES
        # ==================================================================
        log.debug("Types géométriques :")

        for gtype, count in geom_types.items():
            log.debug(f"\t\t{Colors.ENDC}{gtype}{Colors.DEBUG} : {Colors.ENDC}{count}")

        # ==================================================================
        # EXTENT
        # ==================================================================
        log.debug("Bounding box :")

        if extent is not None:
            try:
                log.debug(f"\t\txmin = {Colors.ENDC}{extent[0]:>8.3f}{Colors.DEBUG}\txmax = {Colors.ENDC}{extent[1]:>8.3f}")
                log.debug(f"\t\tymin = {Colors.ENDC}{extent[2]:>8.3f}{Colors.DEBUG}\tymax = {Colors.ENDC}{extent[3]:>8.3f}")

            except Exception:
                log.debug(f"\t\tEmprise : {Colors.ENDC}{extent}")

        else:
            log.debug(f"\t\tEmprise indisponible")

        # ==================================================================
        # CRS
        # ==================================================================
        log.debug(f"CRS : {Colors.ENDC}{crs}")

        # ==================================================================
        # Z / M
        # ==================================================================
        log.debug(f"Dimensions, Z présent : {Colors.ENDC}{has_z}{Colors.DEBUG}\tM présent : {Colors.ENDC}{has_m}")

        # ==================================================================
        # CHAMPS
        # ==================================================================
        log.debug("Champs attributaires :")

        for field, values in field_stats.items():
            try:
                unique_count = len(set(values))

            except Exception:
                unique_count = "?"

            field_width = 20
            number_width = 10
            log.debug(f"\t\t{Colors.ENDC}{field:<{field_width}}{Colors.DEBUG}: {Colors.ENDC}{len(values):>{number_width}}{Colors.DEBUG} valeurs, {Colors.ENDC}{str(unique_count):>{number_width}}{Colors.DEBUG} uniques")

        # ==================================================================
        # BILAN FINAL
        # ==================================================================
        log.info(f"BILAN : {Colors.ENDC}{total}{Colors.INFO} objets, {Colors.ENDC}{invalid}{Colors.INFO} invalides, {Colors.ENDC}{empty}{Colors.INFO} vides, {Colors.ENDC}{corrupted_count}{Colors.INFO} corrompus/non analysables, {Colors.ENDC}{multi_geom_count}{Colors.INFO} multiparties")
        log.info(f"=========================================================================================================")

        return invalid, total

    # ======================================================================
    # ERREUR GLOBALE
    # ======================================================================
    except Exception as e:
        log.error(f"diagnostic file: {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR}, erreur inattendue : {Colors.ENDC}{e}{Colors.ERROR}, continuing anyway.")
        globalDat.errorCount += 1
        return -1, -1

    # ======================================================================
    # FERMETURE
    # ======================================================================
    finally:
        ds = None
    
def diagnostic(file_path):    
    total = 0
    invalid = 0
    empty = 0
    multi_geom_count = 0
    geometry_read_errors = 0
    geom_types = defaultdict(int)
    has_z = False
    has_m = False
    field_stats = defaultdict(list)
    
    error_codes = defaultdict(int) 
    error_types = defaultdict(int) 
    error_messages = defaultdict(int)
    corrupted_features = []

    try:
        start_time = time.time()
        
        log.info(f"==================== BILAN FILE: {Colors.ENDC}{safe_relpath(file_path)}{Colors.INFO} ===================================")
        
        if not os.path.exists(file_path):
            log.error(f"diagnostic, fichier non trouvé : {Colors.ENDC}{safe_relpath(file_path)}")
            globalDat.errorCount += 1
            return -1, -1
        

        ds = ogr.Open(file_path)
        
        
        if ds is None:
            log.error(f"Impossible d'ouvrir le fichier : {Colors.ENDC}{safe_relpath(file_path)}")
            globalDat.errorCount += 1
            return -1, -1
   
        layer = ds.GetLayer()
            
        extent = layer.GetExtent()
        srs = layer.GetSpatialRef()
        crs = srs.ExportToWkt() if srs else "CRS inconnu"

        feature_count = layer.GetFeatureCount()
        if feature_count >= 0:
            for fid in range(feature_count):
                try:
                    feature = layer.GetFeature(fid)

                except Exception as e:
                    geometry_read_errors += 1
                    attributes = get_dbf_attributes_direct(file_path, fid)
                    corrupted_features.append({"index": total + 1, "fid": fid, "shape": fid + 1, "stage": "GetFeature", "error": str(e), "attributes": attributes})

                    log.error(f"GetFeature, SHAPE : {Colors.ENDC}{fid + 1}{Colors.ERROR}, FID : {Colors.ENDC}{fid}{Colors.ERROR}, GetFeature : {Colors.ENDC}{e}" )
                    globalDat.errorCount += 1                    
                    log_feature_attributes(attributes, "error")
                    total += 1
                    continue
                
                if feature is None:
                    geometry_read_errors += 1
                    corrupted_features.append({"fid": fid,"stage": "GetFeature","error": "GetFeature returned None"})
                    log.warning(f"Erreur lecture feature FID {Colors.ENDC}{fid}{Colors.WARNING} : GetFeature() retourne None")
                    continue
                
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
                    try: 
                        val = feature.GetField(i)
                    except Exception as e:
                        log.error(f"Impossible d’exécuter GetField : {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR} : {Colors.ENDC}{e}")
                        globalDat.errorCount += 1
                        continue
                    if val is not None:
                        field_stats[field_name].append(val)
                

            
        elapsed = time.time() - start_time
        file_size = os.path.getsize(file_path) / (1024*1024)  # Mo

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
    
    except Exception as e:
        log.error(f"diagnostic file: {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR}, unable to validate geometry: {Colors.ENDC}{e}{Colors.ERROR}, continuing anyway.")
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
def shp2gpkgBad(pathshp, infile, outputspath, outfile):
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
        if not gdal.GetConfigOption("GDAL_DATA"):
            gdal.SetConfigOption("GDAL_DATA", "/usr/share/gdal")

        gdal.SetConfigOption("OGR_GEOMETRY_ACCEPT_UNCLOSED_RING", "YES")

        ds = ogr.Open(input_shp)
        
        if ds is None:
            log.error(f"shp2gpkg, impossible d'ouvrir le SHP : {Colors.ENDC}{safe_relpath(input_shp)}")
            globalDat.errorCount += 1
            return

        layer = ds.GetLayer()
        srs = layer.GetSpatialRef()
        featureCount = layer.GetFeatureCount()

        if os.path.exists(output_gpkg):
            ogr.GetDriverByName("GPKG").DeleteDataSource(output_gpkg)

        driver = ogr.GetDriverByName("GPKG")
        out_ds = driver.CreateDataSource(output_gpkg)

        out_layer = out_ds.CreateLayer(outfile, srs, geom_type=ogr.wkbUnknown)
        layer_defn = layer.GetLayerDefn()

        for i in range(layer_defn.GetFieldCount()):
            out_layer.CreateField(layer_defn.GetFieldDefn(i))

        out_layer_defn = out_layer.GetLayerDefn()
        out_layer.StartTransaction()

        error_count = 0
        feature_count = 0
        corrupted_features = []
        total_count = len(layer)
        total = 0
        
        log.info(f"SHP file conversion : {Colors.ENDC}{infile}.shp{Colors.INFO} with {Colors.ENDC}{total_count}{Colors.INFO} objets")

        with alive_bar(len(layer), title=f"{Colors.YELLOW}Conversion SHP file {Colors.ENDC}{infile}{Colors.YELLOW} to GPKG {Colors.ENDC}" ,  length = 20) as bar:
            if featureCount >= 0:
                for fid in range(featureCount):
                    # ----------------------------------------------------------
                    # Lecture du feature
                    # ----------------------------------------------------------
                    try:
                        feature = layer.GetFeature(fid)

                    except Exception as e:
                        error_count += 1
                        attributes = get_dbf_attributes_direct(input_shp, fid)
                        corrupted_features.append({"index": total + 1, "fid": fid, "shape": fid + 1, "stage": "GetFeature", "error": str(e), "attributes": attributes})

                        log.error(f"GetFeature, SHAPE : {Colors.ENDC}{fid + 1}{Colors.ERROR}, FID : {Colors.ENDC}{fid}{Colors.ERROR}, GetFeature : {Colors.ENDC}{e}" )
                        globalDat.errorCount += 1                    
                        log_feature_attributes(attributes, "error")
                        total += 1
                        bar()
                        continue
    
                    geom = fix_geometry(feature, infile, layer_defn)
                    
                    if geom is None : 
                        log.warning(f"Géométrie impossible à corriger FID")
                        error_count += 1
                        corrupted_features.append({
                            "index": total + 1,
                            "fid": fid,
                            "shape": fid + 1,
                            "stage": "fix_geometry",
                            "error": "Geometry is None",
                            "attributes": get_dbf_attributes_direct(input_shp, fid)
                        })

                        total += 1
                        bar()
                        continue
                        
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
            log.error(f"Error in conversion file {Colors.ENDC}{infile}{Colors.ERROR} SHP to GPKG : {Colors.ENDC}{e}{Colors.ERROR}")
            globalDat.errorCount += 1
        
        return
            
    
    # except Exception as e:

    #     if log:
    #         log.error(f"Error in conversion file {infile} SHP to GPKG : {e}")
    #         globalDat.errorCount += 1

    #     raise
#################################################################################################
def shp2gpkg(pathshp, infile, outputspath, outfile):
    """
    Conversion SHP -> GPKG.

    - supporte tous les types de géométrie
    - conserve Z et M
    - ferme les anneaux automatiquement via fix_geometry()
    - corrige les géométries invalides via fix_geometry()
    - ne crée JAMAIS de feature avec une géométrie None
    - détecte les erreurs de lecture
    - détecte les erreurs de création dans le GPKG
    - ne suppose PAS que les FID sont continus
    - optimisé pour les gros fichiers
    """

    input_shp = os.path.join(pathshp, infile + ".shp")
    output_gpkg = os.path.join(outputspath, outfile + ".gpkg")
    ds = None
    out_ds = None
    out_layer = None
    error_count = 0
    feature_count = 0
    processed_count = 0
    corrupted_features = []

    try:
        if not gdal.GetConfigOption("GDAL_DATA"):
            gdal.SetConfigOption("GDAL_DATA", "/usr/share/gdal")

        gdal.SetConfigOption("OGR_GEOMETRY_ACCEPT_UNCLOSED_RING", "YES")

        if not os.path.exists(input_shp):
            log.error(f"shp2gpkg, fichier SHP inexistant : {Colors.ENDC}{safe_relpath(input_shp)}")
            globalDat.errorCount += 1
            return
        
        ds = ogr.Open(input_shp)

        if ds is None:
            log.error(f"shp2gpkg, impossible d'ouvrir le SHP : {Colors.ENDC}{safe_relpath(input_shp)}")
            globalDat.errorCount += 1
            return

        layer = ds.GetLayer()

        if layer is None:
            log.error(f"shp2gpkg, impossible de récupérer la couche : {Colors.ENDC}{safe_relpath(input_shp)}")
            globalDat.errorCount += 1
            return

        srs = layer.GetSpatialRef()
        featureCount = layer.GetFeatureCount()

        if featureCount < 0:
            log.error(f"shp2gpkg, impossible de déterminer le nombre de features : {Colors.ENDC}{safe_relpath(input_shp)}")
            globalDat.errorCount += 1
            return

        layer_defn = layer.GetLayerDefn()

        if layer_defn is None:
            log.error(f"shp2gpkg, impossible de récupérer la définition de la couche : {Colors.ENDC}{safe_relpath(input_shp)}")
            globalDat.errorCount += 1
            return

        total_count = featureCount

        log.info(f"SHP file conversion : {Colors.ENDC}{infile}.shp{Colors.INFO} with {Colors.ENDC}{total_count}{Colors.INFO} objets")

        if os.path.exists(output_gpkg):
            try:
                ogr.GetDriverByName("GPKG").DeleteDataSource(output_gpkg)

            except Exception as e:
                log.error(f"Impossible de supprimer le GPKG existant : {Colors.ENDC}{output_gpkg}{Colors.ERROR} : {Colors.ENDC}{e}")
                globalDat.errorCount += 1
                return

        driver = ogr.GetDriverByName("GPKG")

        if driver is None:
            log.error("shp2gpkg, driver GPKG GDAL indisponible")
            globalDat.errorCount += 1
            return

        out_ds = driver.CreateDataSource(output_gpkg)

        if out_ds is None:
            log.error(f"shp2gpkg, impossible de créer le GPKG : {Colors.ENDC}{output_gpkg}")
            globalDat.errorCount += 1
            return

        out_layer = out_ds.CreateLayer(outfile, srs, geom_type=ogr.wkbUnknown )

        if out_layer is None:
            log.error(f"shp2gpkg, impossible de créer la couche GPKG : {Colors.ENDC}{outfile}")
            globalDat.errorCount += 1
            return
        
        for i in range(layer_defn.GetFieldCount()):

            field_defn = layer_defn.GetFieldDefn(i)
            if field_defn is None:
                log.warning(f"Définition de champ invalide index {Colors.ENDC}{i}")
                continue

            result = out_layer.CreateField(field_defn)

            if result != 0:
                log.error(f"Impossible de créer le champ {Colors.ENDC}{field_defn.GetNameRef()}")
                globalDat.errorCount += 1

        out_layer_defn = out_layer.GetLayerDefn()

        if out_layer_defn is None:
            log.error("shp2gpkg, impossible de récupérer la définition de la couche de sortie")
            globalDat.errorCount += 1
            return

        out_layer.StartTransaction()

        # ============================================================
        # Parcours réel des features
        #
        # Ne PAS utiliser :
        #
        #     for fid in range(featureCount)
        #     feature = layer.GetFeature(fid)
        #
        # Les FID d'un SHP peuvent ne pas être continus.
        # ============================================================

        layer.ResetReading()

        with alive_bar(total_count, title=(f"{Colors.YELLOW}Conversion SHP file {Colors.ENDC}{infile}{Colors.YELLOW} to GPKG {Colors.ENDC}"),length=20) as bar:

            while True:

                # ====================================================
                # Lecture du prochain feature
                # ====================================================

                try:
                    feature = layer.GetNextFeature()

                except Exception as e:
                    error_count += 1

                    log.error(f"Erreur lecture SHP après {Colors.ENDC}{processed_count}{Colors.ERROR} features : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1

                    bar()
                    continue

                # ====================================================
                # Fin normale de la couche
                # ====================================================

                if feature is None:
                    break

                # ====================================================
                # Récupération du vrai FID
                # ====================================================

                try:
                    fid = feature.GetFID()

                except Exception:
                    fid = processed_count

                processed_count += 1

                # ====================================================
                # Vérification de la géométrie brute
                # ====================================================

                try:
                    source_geom = feature.GetGeometryRef()

                except Exception as e:
                    error_count += 1

                    try:
                        attributes = get_dbf_attributes_direct(input_shp, fid)

                    except Exception:
                        attributes = None

                    corrupted_features.append({
                        "index": processed_count,
                        "fid": fid,
                        "shape": processed_count,
                        "stage": "GetGeometryRef",
                        "error": str(e),
                        "attributes": attributes
                    })

                    log.error(f"GetGeometryRef, SHAPE : {Colors.ENDC}{processed_count}{Colors.ERROR}, FID : {Colors.ENDC}{fid}{Colors.ERROR} : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1

                    if attributes is not None:
                        log_feature_attributes(attributes, "error")

                    bar()
                    continue

                # ====================================================
                # Géométrie NULL
                # ====================================================

                if source_geom is None:
                    error_count += 1

                    try:
                        attributes = get_dbf_attributes_direct(input_shp, fid)

                    except Exception:
                        attributes = None

                    corrupted_features.append({
                        "index": processed_count,
                        "fid": fid,
                        "shape": processed_count,
                        "stage": "GetGeometryRef",
                        "error": "Source geometry is None",
                        "attributes": attributes
                    })

                    log.error(f"Géométrie NULL, SHAPE : {Colors.ENDC}{processed_count}{Colors.ERROR}, FID : {Colors.ENDC}{fid}")
                    globalDat.errorCount += 1

                    if attributes is not None:
                        log_feature_attributes(attributes, "error")

                    bar()
                    continue

                # ====================================================
                # Correction de la géométrie
                # ====================================================

                try:
                    geom = fix_geometry(feature, infile, layer_defn)

                except Exception as e:
                    geom = None
                    error_count += 1

                    try:
                        attributes = get_dbf_attributes_direct(input_shp, fid)

                    except Exception:
                        attributes = None

                    corrupted_features.append({
                        "index": processed_count,
                        "fid": fid,
                        "shape": processed_count,
                        "stage": "fix_geometry",
                        "error": str(e),
                        "attributes": attributes
                    })

                    log.error(f"Erreur fix_geometry, SHAPE : {Colors.ENDC}{processed_count}{Colors.ERROR}, FID : {Colors.ENDC}{fid}{Colors.ERROR} : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1

                    if attributes is not None:
                        log_feature_attributes(attributes, "error")

                    bar()
                    continue

                # ====================================================
                # Géométrie impossible à corriger
                # ====================================================

                if geom is None:
                    error_count += 1

                    try:
                        attributes = get_dbf_attributes_direct(input_shp, fid)

                    except Exception:
                        attributes = None

                    corrupted_features.append({
                        "index": processed_count,
                        "fid": fid,
                        "shape": processed_count,
                        "stage": "fix_geometry",
                        "error": "fix_geometry returned None",
                        "attributes": attributes
                    })

                    log.warning(f"Géométrie impossible à corriger, SHAPE : {Colors.ENDC}{processed_count}{Colors.WARNING}, FID : {Colors.ENDC}{fid}")
                    globalDat.errorCount += 1

                    if attributes is not None:
                        log_feature_attributes(attributes, "error")

                    bar()
                    continue

                # ====================================================
                # Vérification finale de la géométrie
                # ====================================================

                try:
                    if geom.IsEmpty():
                        error_count += 1

                        log.warning(f"Géométrie vide après correction, SHAPE : {Colors.ENDC}{processed_count}{Colors.WARNING}, FID : {Colors.ENDC}{fid}")

                        corrupted_features.append({
                            "index": processed_count,
                            "fid": fid,
                            "shape": processed_count,
                            "stage": "geometry_validation",
                            "error": "Geometry is empty",
                            "attributes": None
                        })

                        globalDat.errorCount += 1
                        bar()
                        continue

                except Exception as e:
                    error_count += 1

                    log.warning(f"Impossible de vérifier la géométrie SHAPE {Colors.ENDC}{processed_count}{Colors.WARNING} : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1
                    bar()
                    continue

                # ====================================================
                # Création feature
                # ====================================================

                out_feature = ogr.Feature(out_layer_defn)

                if out_feature is None:
                    error_count += 1

                    log.error(f"Impossible de créer le feature GPKG, SHAPE : {Colors.ENDC}{processed_count}")
                    globalDat.errorCount += 1
                    bar()
                    continue

                # ====================================================
                # Copie attributs
                # ====================================================

                try:

                    for i in range(out_layer_defn.GetFieldCount()):
                        out_feature.SetField(i, feature.GetField(i))

                except Exception as e:
                    error_count += 1

                    log.error(f"Erreur copie attributs, SHAPE : {Colors.ENDC}{processed_count}{Colors.ERROR} : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1

                    out_feature = None
                    bar()
                    continue

                # ====================================================
                # Affectation géométrie
                # ====================================================

                try:
                    out_feature.SetGeometry(geom)

                except Exception as e:
                    error_count += 1

                    log.error(f"Erreur SetGeometry, SHAPE : {Colors.ENDC}{processed_count}{Colors.ERROR} : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1

                    out_feature = None
                    bar()
                    continue

                # ====================================================
                # Création dans le GPKG
                # ====================================================

                try:
                    result = out_layer.CreateFeature(out_feature)

                except Exception as e:
                    result = 1

                    log.error(f"Erreur CreateFeature, SHAPE : {Colors.ENDC}{processed_count}{Colors.ERROR}, FID : {Colors.ENDC}{fid}{Colors.ERROR} : {Colors.ENDC}{e}")

                finally:
                    out_feature = None

                if result != 0:
                    error_count += 1

                    log.error(f"Impossible de créer le feature GPKG, SHAPE : {Colors.ENDC}{processed_count}{Colors.ERROR}, FID : {Colors.ENDC}{fid}")
                    globalDat.errorCount += 1

                    bar()
                    continue

                feature_count += 1

                # ====================================================
                # Commit par bloc
                # ====================================================

                if feature_count % 10000 == 0:

                    try:
                        out_layer.CommitTransaction()
                        out_layer.StartTransaction()

                    except Exception as e:
                        log.error(f"Erreur transaction GPKG après {Colors.ENDC}{feature_count}{Colors.ERROR} features : {Colors.ENDC}{e}")
                        globalDat.errorCount += 1
                        raise

                bar()

        # ============================================================
        # Commit final
        # ============================================================

        try:
            out_layer.CommitTransaction()

        except Exception as e:
            log.error(f"Erreur CommitTransaction final : {Colors.ENDC}{e}")
            globalDat.errorCount += 1
            raise

        layer = None
        ds = None

        out_layer = None
        out_ds = None

        log.info(f"Conversion GPKG terminée fichier : {Colors.ENDC}{outfile}{Colors.INFO}, {Colors.ENDC}{feature_count}{Colors.INFO} objets convertis")

        if error_count > 0:
            log.warning(f"{Colors.ENDC}{error_count}{Colors.WARNING} objets en erreur")

        deleted_count = total_count - feature_count

        if deleted_count > 0:
            log.warning(f"{Colors.ENDC}{deleted_count}{Colors.WARNING} géométries supprimées")

        if corrupted_features:
            log.warning(f"{Colors.ENDC}{len(corrupted_features)}{Colors.WARNING} features rejetés pendant la conversion")

            for item in corrupted_features:
                log.warning(f"SHAPE {Colors.ENDC}{item['shape']}{Colors.WARNING} / FID {Colors.ENDC}{item['fid']}{Colors.WARNING} / {Colors.ENDC}{item['stage']}{Colors.WARNING} : {Colors.ENDC}{item['error']}")

        return

    # =================================================================
    # Erreur GDAL / Runtime
    # =================================================================

    except RuntimeError as e:

        log.error(f"Error in conversion file {Colors.ENDC}{infile}{Colors.ERROR} SHP to GPKG : {Colors.ENDC}{e}")
        globalDat.errorCount += 1

    # =================================================================
    # Erreur inattendue
    # =================================================================

    except Exception as e:

        log.error(f"Erreur inattendue dans shp2gpkg {Colors.ENDC}{infile}{Colors.ERROR} : {Colors.ENDC}{e}")
        globalDat.errorCount += 1

    # =================================================================
    # Nettoyage garanti
    # =================================================================

    finally:

        try:
            if out_layer is not None: out_layer = None

        except Exception:
            pass

        try:
            if out_ds is not None: out_ds = None

        except Exception:
            pass

        try:
            if ds is not None: ds = None

        except Exception:
            pass




def shp2gpkg2(pathshp, infile, outputspath, outfile):
    """
    Conversion SHP -> GPKG.

    - supporte tous les types de géométrie
    - conserve Z et M
    - ferme les anneaux automatiquement via fix_geometry()
    - corrige les géométries invalides via fix_geometry()
    - ne crée JAMAIS de feature avec une géométrie None
    - détecte GetFeature() retournant None
    - détecte les erreurs de création dans le GPKG
    - optimisé pour les gros fichiers
    """

    input_shp = os.path.join(pathshp, infile + ".shp")
    output_gpkg = os.path.join(outputspath, outfile + ".gpkg")
    ds = None
    out_ds = None
    out_layer = None
    error_count = 0
    feature_count = 0
    corrupted_features = []

    try:
        if not gdal.GetConfigOption("GDAL_DATA"):
            gdal.SetConfigOption("GDAL_DATA", "/usr/share/gdal")

        gdal.SetConfigOption("OGR_GEOMETRY_ACCEPT_UNCLOSED_RING", "YES")

        if not os.path.exists(input_shp):
            log.error(f"shp2gpkg, fichier SHP inexistant : {Colors.ENDC}{safe_relpath(input_shp)}")
            globalDat.errorCount += 1
            return
        
        ds = ogr.Open(input_shp)

        if ds is None:
            log.error(f"shp2gpkg, impossible d'ouvrir le SHP : {Colors.ENDC}{safe_relpath(input_shp)}")
            globalDat.errorCount += 1
            return

        layer = ds.GetLayer()

        if layer is None:
            log.error(f"shp2gpkg, impossible de récupérer la couche : {Colors.ENDC}{safe_relpath(input_shp)}")
            globalDat.errorCount += 1
            return

        srs = layer.GetSpatialRef()
        featureCount = layer.GetFeatureCount()

        if featureCount < 0:
            log.error(f"shp2gpkg, impossible de déterminer le nombre de features : {Colors.ENDC}{safe_relpath(input_shp)}")
            globalDat.errorCount += 1
            return

        layer_defn = layer.GetLayerDefn()

        if layer_defn is None:
            log.error(f"shp2gpkg, impossible de récupérer la définition de la couche : {Colors.ENDC}{safe_relpath(input_shp)}")
            globalDat.errorCount += 1
            return

        total_count = featureCount

        log.info(f"SHP file conversion : {Colors.ENDC}{infile}.shp{Colors.INFO} with {Colors.ENDC}{total_count}{Colors.INFO} objets")

        if os.path.exists(output_gpkg):
            try:
                ogr.GetDriverByName("GPKG").DeleteDataSource(output_gpkg)

            except Exception as e:
                log.error(f"Impossible de supprimer le GPKG existant : {Colors.ENDC}{output_gpkg}{Colors.ERROR} : {Colors.ENDC}{e}")
                globalDat.errorCount += 1
                return
        driver = ogr.GetDriverByName("GPKG")

        if driver is None:
            log.error("shp2gpkg, driver GPKG GDAL indisponible")
            globalDat.errorCount += 1
            return

        out_ds = driver.CreateDataSource(output_gpkg)

        if out_ds is None:
            log.error(f"shp2gpkg, impossible de créer le GPKG : {Colors.ENDC}{output_gpkg}")
            globalDat.errorCount += 1
            return

        out_layer = out_ds.CreateLayer(outfile, srs, geom_type=ogr.wkbUnknown )

        if out_layer is None:
            log.error(f"shp2gpkg, impossible de créer la couche GPKG : {Colors.ENDC}{outfile}")
            globalDat.errorCount += 1
            return
        
        for i in range(layer_defn.GetFieldCount()):

            field_defn = layer_defn.GetFieldDefn(i)
            if field_defn is None:
                log.warning(f"Définition de champ invalide index {Colors.ENDC}{i}")
                continue

            result = out_layer.CreateField(field_defn)

            if result != 0:
                log.error(f"Impossible de créer le champ {Colors.ENDC}{field_defn.GetNameRef()}")
                globalDat.errorCount += 1

        out_layer_defn = out_layer.GetLayerDefn()

        if out_layer_defn is None:
            log.error("shp2gpkg, impossible de récupérer la définition de la couche de sortie")
            globalDat.errorCount += 1
            return

        out_layer.StartTransaction()


        with alive_bar(total_count, title=(f"{Colors.YELLOW}Conversion SHP file {Colors.ENDC}{infile}{Colors.YELLOW} to GPKG {Colors.ENDC}"),length=20) as bar:
            for fid in range(featureCount):
                try:
                    feature = layer.GetFeature(fid)

                except Exception as e:
                    error_count += 1
                    attributes = get_dbf_attributes_direct(input_shp, fid)
                    corrupted_features.append({
                        "index": fid + 1,
                        "fid": fid,
                        "shape": fid + 1,
                        "stage": "GetFeature",
                        "error": str(e),
                        "attributes": attributes
                    })

                    log.error(f"GetFeature, SHAPE : {Colors.ENDC}{fid + 1}{Colors.ERROR}, FID : {Colors.ENDC}{fid}{Colors.ERROR}, GetFeature :{Colors.ENDC}{e}")
                    globalDat.errorCount += 1
                    log_feature_attributes(attributes, "error")
                    bar()
                    continue

                if feature is None:
                    error_count += 1
                    try:
                        attributes = get_dbf_attributes_direct(input_shp, fid)
                    
                    except Exception:
                        attributes = None

                    corrupted_features.append({
                        "index": fid + 1,
                        "fid": fid,
                        "shape": fid + 1,
                        "stage": "GetFeature",
                        "error": "GetFeature returned None",
                        "attributes": attributes
                    })

                    log.error(f"GetFeature retourne None, SHAPE : {Colors.ENDC}{fid + 1}{Colors.ERROR}, FID : {Colors.ENDC}{fid}")
                    globalDat.errorCount += 1

                    if attributes is not None:
                        log_feature_attributes(attributes, "error")

                    bar()
                    continue

                # ====================================================
                # Vérification de la géométrie brute
                # ====================================================

                try:
                    source_geom = feature.GetGeometryRef()

                except Exception as e:
                    error_count += 1

                    try:
                        attributes = get_dbf_attributes_direct( input_shp, fid)
                   
                    except Exception:
                        attributes = None

                    corrupted_features.append({
                        "index": fid + 1,
                        "fid": fid,
                        "shape": fid + 1,
                        "stage": "GetGeometryRef",
                        "error": str(e),
                        "attributes": attributes
                    })

                    log.error(f"GetGeometryRef, SHAPE : {Colors.ENDC}{fid + 1}{Colors.ERROR}, FID : {Colors.ENDC}{fid}{Colors.ERROR} : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1

                    if attributes is not None:
                        log_feature_attributes(attributes, "error")

                    bar()
                    continue

                # ====================================================
                # Géométrie NULL
                # ====================================================

                if source_geom is None:
                    error_count += 1

                    try:
                        attributes = get_dbf_attributes_direct(input_shp, fid)
                    
                    except Exception:
                        attributes = None

                    corrupted_features.append({
                        "index": fid + 1,
                        "fid": fid,
                        "shape": fid + 1,
                        "stage": "GetGeometryRef",
                        "error": "Source geometry is None",
                        "attributes": attributes
                    })

                    log.error(f"Géométrie NULL, SHAPE : {Colors.ENDC}{fid + 1}{Colors.ERROR}, FID : {Colors.ENDC}{fid}")
                    globalDat.errorCount += 1
                    if attributes is not None:
                        log_feature_attributes(attributes, "error")

                    bar()
                    continue

                # ====================================================
                # Correction de la géométrie
                # ====================================================

                try:

                    geom = fix_geometry(feature, infile, layer_defn)

                except Exception as e:
                    geom = None
                    error_count += 1
                    try:
                        attributes = get_dbf_attributes_direct(input_shp, fid)
                    
                    except Exception:
                        attributes = None

                    corrupted_features.append({
                        "index": fid + 1,
                        "fid": fid,
                        "shape": fid + 1,
                        "stage": "fix_geometry",
                        "error": str(e),
                        "attributes": attributes
                    })

                    log.error(f"Erreur fix_geometry, SHAPE : {Colors.ENDC}{fid + 1}{Colors.ERROR}, FID : {Colors.ENDC}{fid}{Colors.ERROR} : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1
                    if attributes is not None:
                        log_feature_attributes(attributes, "error")

                    bar()
                    continue

                if geom is None:
                    error_count += 1

                    try:
                        attributes = get_dbf_attributes_direct(input_shp, fid)
                    
                    except Exception:
                        attributes = None

                    corrupted_features.append({
                        "index": fid + 1,
                        "fid": fid,
                        "shape": fid + 1,
                        "stage": "fix_geometry",
                        "error": "fix_geometry returned None",
                        "attributes": attributes
                    })

                    log.warning(f"Géométrie impossible à corriger, SHAPE : {Colors.ENDC}{fid + 1}{Colors.WARNING}, FID : {Colors.ENDC}{fid}")
                    globalDat.errorCount += 1
                    if attributes is not None:
                        log_feature_attributes(attributes, "error")

                    bar()
                    continue

                # ====================================================
                # Vérification finale de la géométrie
                # ====================================================

                try:
                    if geom.IsEmpty():
                        error_count += 1
                        log.warning(f"Géométrie vide après correction, SHAPE : {Colors.ENDC}{fid + 1}{Colors.WARNING}, FID : {Colors.ENDC}{fid}")

                        corrupted_features.append({
                            "index": fid + 1,
                            "fid": fid,
                            "shape": fid + 1,
                            "stage": "geometry_validation",
                            "error": "Geometry is empty",
                            "attributes": None
                        })

                        globalDat.errorCount += 1
                        bar()
                        continue

                except Exception as e:
                    error_count += 1
                    log.warning(f"Impossible de vérifier la géométrie SHAPE {Colors.ENDC}{fid + 1}{Colors.WARNING} : {Colors.ENDC}{e}")
                    bar()
                    continue

                out_feature = ogr.Feature(out_layer_defn)

                if out_feature is None:
                    error_count += 1
                    log.error(f"Impossible de créer le feature GPKG, SHAPE : {Colors.ENDC}{fid + 1}")
                    globalDat.errorCount += 1
                    bar()
                    continue

                try:

                    for i in range(out_layer_defn.GetFieldCount()):
                        out_feature.SetField(i, feature.GetField(i))

                except Exception as e:
                    error_count += 1
                    log.error(f"Erreur copie attributs, SHAPE : {Colors.ENDC}{fid + 1}{Colors.ERROR} : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1
                    out_feature = None
                    bar()
                    continue

                try:
                    out_feature.SetGeometry(geom)

                except Exception as e:
                    error_count += 1
                    log.error(f"Erreur SetGeometry, SHAPE : {Colors.ENDC}{fid + 1}{Colors.ERROR} : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1
                    out_feature = None
                    bar()
                    continue

                try:
                    result = out_layer.CreateFeature(out_feature)

                except Exception as e:
                    result = 1
                    log.error(f"Erreur CreateFeature, SHAPE : {Colors.ENDC}{fid + 1}{Colors.ERROR} : {Colors.ENDC}{e}")

                finally:
                    out_feature = None

                if result != 0:
                    error_count += 1
                    log.error(f"Impossible de créer le feature GPKG, SHAPE : {Colors.ENDC}{fid + 1}{Colors.ERROR}, FID : {Colors.ENDC}{fid}")
                    globalDat.errorCount += 1
                    bar()
                    continue

                feature_count += 1

                if feature_count % 10000 == 0:

                    try:
                        out_layer.CommitTransaction()
                        out_layer.StartTransaction()

                    except Exception as e:
                        log.error(f"Erreur transaction GPKG après {Colors.ENDC}{feature_count}{Colors.ERROR} features : {Colors.ENDC}{e}")
                        globalDat.errorCount += 1
                        raise
                bar()

        try:
            out_layer.CommitTransaction()

        except Exception as e:

            log.error(f"Erreur CommitTransaction final : {Colors.ENDC}{e}")
            globalDat.errorCount += 1
            raise


        layer = None
        ds = None

        out_layer = None
        out_ds = None

        log.info(f"Conversion GPKG terminée fichier : {Colors.ENDC}{outfile}{Colors.INFO}, {Colors.ENDC}{feature_count}{Colors.INFO} objets convertis")

        if error_count > 0:
            log.warning(f"{Colors.ENDC}{error_count}{Colors.WARNING} objets en erreur")

        deleted_count = total_count - feature_count

        if deleted_count > 0:
            log.warning(f"{Colors.ENDC}{deleted_count}{Colors.WARNING} géométries supprimées")

        if corrupted_features:
            log.warning(f"{Colors.ENDC}{len(corrupted_features)}{Colors.WARNING} features rejetés pendant la conversion")
            for item in corrupted_features:
                log.warning(f"SHAPE {Colors.ENDC}{item['shape']}{Colors.WARNING} / FID {Colors.ENDC}{item['fid']}{Colors.WARNING} / {Colors.ENDC}{item['stage']}{Colors.WARNING} : {Colors.ENDC}{item['error']}")
        return

    # =================================================================
    # Erreur GDAL / Runtime
    # =================================================================
    except RuntimeError as e:
        log.error(
            f"Error in conversion file {Colors.ENDC}{infile}{Colors.ERROR} SHP to GPKG : {Colors.ENDC}{e}")
        globalDat.errorCount += 1

    # =================================================================
    # Erreur inattendue
    # =================================================================
    except Exception as e:
        log.error(f"Erreur inattendue dans shp2gpkg {Colors.ENDC}{infile}{Colors.ERROR} : {Colors.ENDC}{e}")
        globalDat.errorCount += 1

    # =================================================================
    # Nettoyage garanti
    # =================================================================

    finally:
        try:
            if out_layer is not None: out_layer = None
                
        except Exception:
            pass

        try:
            if out_ds is not None: out_ds = None
                
        except Exception:
            pass

        try:
            if ds is not None: ds = None
            
        except Exception:
            pass

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
                log.error(f"in file {Colors.ENDC}{(safe_relpath(outputspath + destinationName + '.gpkg'))}{Colors.ERROR} please fix it manually with QGis...")
                globalDat.errorCount += 1
                continue


    log.info(f"{Colors.HEADER}{Colors.UNDERLINE}Step 2: adapte drawing files (cut it) for QGis in the folder:{Colors.ENDC} {safe_relpath(outputspath)}")
    
    ## Work with lines
    file_path = os.path.join(outputspath, 'lines2d_fixed.gpkg')
    valid = cutGPKG(file_path, os.path.join(outputspath,'outline2d.gpkg'), os.path.join(outputspath,'lines2dMasked.gpkg'))     
    err, valid2 = diagnostic(os.path.join(outputspath,'lines2dMasked.gpkg'))
    
    if (valid2 - valid) != 0 :
        log.warning(f"{Colors.ENDC}{abs(valid2 - valid)}{Colors.WARNING} deleted geometries need to be verified in {Colors.ENDC}lines2dMasked.gpkg{Colors.WARNING} file") 
    elif (valid2 == -1):
        log.error(f"in clipped geometries in {Colors.ENDC}lines2dMasked.gpkg{Colors.INFO} file") 
    else :
        log.info(f"{Colors.ENDC}{valid}{Colors.INFO} clipped geometries in {Colors.ENDC}lines2dMasked.gpkg{Colors.ERROR} file") 
        
    if os.path.exists(file_path):
        os.remove(file_path)
          
    ## Work with Areas  
    file_path = os.path.join(outputspath, 'areas2d_fixed.gpkg')      
    valid = cutGPKG(file_path, os.path.join(outputspath,'outline2d.gpkg'), os.path.join(outputspath,'areas2dMasked.gpkg'))    
    err, valid2 = diagnostic(os.path.join(outputspath,'areas2dMasked.gpkg'))    
    
    if (valid2 - valid) != 0 :
        log.warning(f"{Colors.ENDC}{abs(valid2 - valid)}{Colors.WARNING} Deleted geometries need to be verified in {Colors.ENDC}areas2d_fixed.gpkg{Colors.WARNING} file") 
    elif (valid2 == -1):
        log.error(f"in clipped geometries in {Colors.ENDC}areas2d_fixed.gpkg{Colors.ERROR} file") 
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

            


 