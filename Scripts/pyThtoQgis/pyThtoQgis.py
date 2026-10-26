######!/usr/bin/env python
# SPDX-License-Identifier: GPL-3.0-or-later

"""
#################################################################################################
!#                                                        	                                    #
!# Script to automatize data extraction of Therion databases for QGis                           #
!#                                                        	                                    #
!#                                    By Xavier Robert                                          #
!#                                   Grenoble, October 2022                                     #
!#                                                        	                                    #
#################################################################################################

Written by Xavier Robert, October 2022
Copyright (c) 2020 Xavier Robert <xavier.robert@ird.fr>
Xavier.robert@ird.fr

Modifié Alex 2025 01 31
Modifié Alex 2026 02 27
Modifié Alex 2026 08 28
Modifié Alex 2026 10 25

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

import Lib.global_data as globalDat  # noqa: I001
from Lib.general_fonctions import setup_logger, Colors, safe_relpath, colored_help

# Import Python modules
import sys, os, argparse, time, math, logging, struct
import tkinter as tk
from tkinter import filedialog
from osgeo import ogr, gdal
from collections import defaultdict
from alive_progress import alive_bar  # https://github.com/rsalmei/alive-progress


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
    try:
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
                    log.warning("geom is None")
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
                keep_outside = _type in {"label", "water_flow", "centerline"} or _clip == "off"

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

                    attrs_formatted = ", ".join(attrs)
                    globalDat.geometryWarning.append(f"Any intersection issue\nAttributes: {Colors.ENDC}{attrs_formatted}{Colors.WARNING}")

                    log.warning(f"Any intersection issue\nAttributes: {Colors.ENDC}{attrs_formatted}{Colors.WARNING}")
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
        log.error(
            f"cutGPKG in file {Colors.ENDC}{safe_relpath(outlines_path)}{Colors.ERROR}, unable to validate geometry: {Colors.ENDC}{e}{Colors.ERROR}, continuing anyway."
        )
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
    try:
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
            out_layer = ds_out.CreateLayer(os.path.splitext(os.path.basename(output_gpkg_path))[0], srs=srs, geom_type=ogr.wkbPoint25D)

        # -------------------------------------------------
        # COPY FIELDS (SAFE FOR EXISTING FILE)
        # -------------------------------------------------

        existing_defn = out_layer.GetLayerDefn()

        exclude_fields = {"fid", "vertex_index", "vertex_part", "vertex_part_index", "distance"}

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
                            new_feat.SetField(in_defn.GetFieldDefn(f).GetNameRef(), feat.GetField(f))  # noqa: B023

                        new_feat.SetField("_TYPEFCR", angle)

                        type_val = feat.GetField("_TYPE")  # noqa: B023

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
            log.error(f"DBF not found : {Colors.ENDC}{safe_relpath(dbf_path)}")
            globalDat.errorCount += 1
            return {}

        with open(dbf_path, "rb") as f:
            # ==========================================================
            # EN-TETE DBF
            # ==========================================================

            header = f.read(32)

            if len(header) != 32:
                log.error(f"Invalid or truncated DBF : {Colors.ENDC}{safe_relpath(dbf_path)}")
                globalDat.errorCount += 1
                return {}

            # Nombre de records
            num_records = struct.unpack("<I", header[4:8])[0]

            # Taille de l'en-tête
            header_length = struct.unpack("<H", header[8:10])[0]

            # Taille d'un record
            record_length = struct.unpack("<H", header[10:12])[0]

            if record_index < 0 or record_index >= num_records:
                log.error(f"DBF record out of bounds : {Colors.ENDC}{record_index}{Colors.ERROR} / {Colors.ENDC}{num_records}")
                globalDat.errorCount += 1
                return {}

            # ==========================================================
            # LECTURE DES DESCRIPTIONS DE CHAMPS
            # ==========================================================

            fields = []

            while True:
                descriptor = f.read(32)

                if len(descriptor) != 32:
                    log.error("Unexpected end of DBF descriptors")
                    globalDat.errorCount += 1
                    return {}

                # 0x0D = fin des descripteurs
                if descriptor[0] == 0x0D:
                    break

                # ------------------------------------------------------
                # Nom du champ : 11 octets
                # ------------------------------------------------------

                field_name = descriptor[0:11].split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()

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

            record_offset = header_length + record_index * record_length
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
                raw_value = record[position : position + length]
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
                        if field["decimals"] == 0 and "." not in value:
                            value = int(value)

                        else:
                            value = float(value)

                    except ValueError:
                        pass

                elif field_type == "L":
                    if value.upper() == "Y":
                        value = True
                    elif value.upper() == "N":
                        value = False

                attributes[field["name"]] = value

            return attributes

    except Exception as e:  # noqa: BLE001
        log.error(f"Direct DBF FID read error {Colors.ENDC}{record_index}{Colors.ERROR} : {Colors.ENDC}{e}")
        globalDat.errorCount += 1
        return {}


# ======================================================================
# FONCTION : AFFICHAGE ATTRIBUTS
# ======================================================================
def log_feature_attributes(attributes, level="debug"):
    if level == "error":
        log.error("Object attributes :")
        if not attributes:
            log.error("Attributs : unavailable")
            return

        for field_name, value in attributes.items():
            log.error(f"\t\t{Colors.ENDC}{field_name}{Colors.ERROR} = {Colors.ENDC}{value}")

    else:
        log.debug("Object attributes :")
        if not attributes:
            log.error("Attributs : unavailable")
            return

        for field_name, value in attributes.items():
            log.debug(f"\t\t{Colors.ENDC}{field_name}{Colors.DEBUG} = {Colors.ENDC}{value}")


#################################################################################################
def diagnostic(file_path, detail=True):
    total = 0
    invalid = 0
    warning = 0
    empty = 0
    multi_geom_count = 0
    geometry_read_errors = 0
    geom_types = defaultdict(int)
    has_z = False
    has_m = False
    field_stats = defaultdict(list)
    error_codes = defaultdict(int)
    warning_codes = defaultdict(int)
    error_types = defaultdict(int)
    warning_types = defaultdict(int)
    error_messages = defaultdict(int)
    warning_messages = defaultdict(int)
    corrupted_features = []

    try:
        start_time = time.time()

        log.info(f"Bilan file : {Colors.ENDC}{safe_relpath(file_path)}{Colors.INFO} ")

        if not os.path.exists(file_path):
            log.error(f"Diagnostic, file not found : {Colors.ENDC}{safe_relpath(file_path)}")
            globalDat.errorCount += 1
            return -1, -1

        ds = ogr.Open(file_path)

        if ds is None:
            log.error(f"Unable to open the file : {Colors.ENDC}{safe_relpath(file_path)}")
            globalDat.errorCount += 1
            return -1, -1

        layer = ds.GetLayer()
        extent = layer.GetExtent()
        srs = layer.GetSpatialRef()
        crs = srs.ExportToWkt() if srs else "Unknown CRS"
        layer.ResetReading()

        while True:
            try:
                feature = layer.GetNextFeature()

            except Exception as e:  # noqa: BLE001
                geometry_read_errors += 1
                log.error(f"GetNextFeature, SHAPE : {Colors.ENDC}{total + 1}{Colors.ERROR} : {Colors.ENDC}{e}")
                globalDat.errorCount += 1
                total += 1
                continue

            # Fin normale de la lecture
            if feature is None:
                break

            # Récupération du véritable FID
            fid = feature.GetFID()

            total += 1

            # Lecture de la géométrie
            try:
                geom = feature.GetGeometryRef()

            except Exception as e:  # noqa: BLE001
                geometry_read_errors += 1

                try:
                    attributes = get_dbf_attributes_direct(file_path, fid)
                except Exception:  # noqa: BLE001
                    attributes = None

                corrupted_features.append({"index": total, "fid": fid, "shape": total, "stage": "GetGeometryRef", "error": str(e), "attributes": attributes})

                log.error(f"GetGeometryRef, SHAPE : {Colors.ENDC}{total}{Colors.ERROR}, FID : {Colors.ENDC}{fid}{Colors.ERROR} : {Colors.ENDC}{e}")
                globalDat.errorCount += 1
                continue

            if geom is None or geom.IsEmpty():
                empty += 1
                continue

            geom_types[geom.GetGeometryName()] += 1

            warning_type = "Too few points"

            if not geom.IsValid():
                code, error_type, error_msg = get_geometry_error(geom)

                if error_type is warning_type:
                    invalid += 1
                    error_codes[code] += 1
                    error_types[error_type] += 1
                    error_messages[error_msg] += 1
                else:
                    warning += 1
                    warning_codes[code] += 1
                    warning_types[error_type] += 1
                    warning_messages[error_msg] += 1

            gtype = geom.GetGeometryType()

            if ogr.GT_HasZ(gtype):
                has_z = True

            if ogr.GT_HasM(gtype):
                has_m = True

            # Champs attributaires
            layer_defn = layer.GetLayerDefn()

            for i in range(layer_defn.GetFieldCount()):
                field_name = layer_defn.GetFieldDefn(i).GetNameRef()

                try:
                    val = feature.GetField(i)
                except Exception as e:  # noqa: BLE001
                    log.error(f"Unable to execute GetField : {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR} : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1
                    continue

                if val is not None:
                    field_stats[field_name].append(val)

            # Libération explicite de la feature
            feature = None

        elapsed = time.time() - start_time
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # Mo

        log.debug(f"Analysis time : {Colors.ENDC}{elapsed:.2f}{Colors.DEBUG} s")
        log.debug(f"Size : {Colors.ENDC}{file_size:.2f}{Colors.DEBUG} Mo")
        log.debug(f"Number of objects :  {Colors.ENDC}{total}")

        if empty == 0:
            log.debug(f"Empty geometries : {Colors.ENDC}{empty}")

        else:
            log.warning(f"Empty geometries : {Colors.ENDC}{empty}")

        if invalid == 0:
            log.info(f"All geometry are valid, nbr : {Colors.ENDC}{total}{Colors.INFO}")

        else:
            log.warning(f"Invalid geometries : {Colors.ENDC}{invalid}{Colors.WARNING}")
            for error, count in sorted(error_types.items(), key=lambda item: item[1], reverse=True):
                log.warning(f"\t\t{Colors.ENDC}{error}{Colors.WARNING} : {Colors.ENDC}{count}")

        if warning > 0:
            log.warning(f"Warning geometries : {Colors.ENDC}{warning}{Colors.WARNING}")
            for error, count in sorted(warning_types.items(), key=lambda item: item[1], reverse=True):
                log.warning(f"\t\t{Colors.ENDC}{error}{Colors.WARNING} : {Colors.ENDC}{count}")

        if detail:
            if multi_geom_count > 0:
                log.info(f"MultiGeometries / Collections : {Colors.ENDC}{multi_geom_count}")

            log.info("Geometric types :")
            for gtype, count in geom_types.items():
                log.info(f"\t{gtype} : {Colors.ENDC}{count}")

            log.info("Bounding box :")
            log.info(f"\txmin = {Colors.ENDC}{extent[0]:>8.3f}{Colors.INFO}\txmax = {Colors.ENDC}{extent[1]:>8.3f}")
            log.info(f"\tymin = {Colors.ENDC}{extent[2]:>8.3f}{Colors.INFO}\tymax = {Colors.ENDC}{extent[3]:>8.3f}")

            log.info(f"Dimensions, Z present : {Colors.ENDC}{has_z}{Colors.INFO}\tM present : {Colors.ENDC}{has_m}")

        log.debug(f"CRS : {Colors.ENDC}{crs}")
        log.debug("Attribute fields :")

        for field, values in field_stats.items():
            unique_count = len(set(values))
            # log.debug(f"\t\t{Colors.ENDC}{field}{Colors.DEBUG}\t\t: {Colors.ENDC}{len(values)}{Colors.DEBUG} valeurs,\t\t{Colors.ENDC}{unique_count}{Colors.DEBUG} uniques")
            # Définir une largeur fixe pour les noms de champs (par exemple 20 caractères)
            field_width = 20
            number_width = 10

            log.debug(
                f"\t\t{Colors.ENDC}{field:<{field_width}}{Colors.DEBUG}: "
                f"{Colors.ENDC}{len(values):>{number_width}}{Colors.DEBUG} value, "
                f"{Colors.ENDC}{unique_count:>{number_width}}{Colors.DEBUG} uniques"
            )

        log.info(f"{'─' * 101}")

        ds = None

        return invalid, total

    except Exception as e:  # noqa: BLE001
        log.error(
            f"Diagnostic file: {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR}, unable to validate geometry: {Colors.ENDC}{e}{Colors.ERROR}, continuing anyway."
        )
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
        return (-1, "Null geometry", "Geometry is None")

    if geom.IsEmpty():
        return (-1, "Empty geometry", "Geometry is empty")

    # ------------------------------------------------------------------
    # GEOMETRYCOLLECTION / MULTI*
    # ------------------------------------------------------------------

    geom_name = geom.GetGeometryName().upper()

    if geom_name == "GEOMETRYCOLLECTION":
        return -2, f"{Colors.WARNING}Not supported", f"{Colors.WARNING}Geometry not checked ({Colors.ENDC}GEOMETRYCOLLECTION{Colors.WARNING})"

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
        return (0, "Valid", "Geometry is valid")

    # Récupération du code et du message GEOS
    if error_messages:
        code, error_msg = error_messages[0]

    else:
        code = -1
        error_msg = f"{Colors.ERROR}Invalid geometry"

    # Normalisation du type d'erreur
    msg = error_msg.lower()

    if "ring self-intersection" in msg:
        error_type = f"{Colors.ERROR}Ring self-intersection"

    elif "self-intersection" in msg:
        error_type = f"{Colors.ERROR}Self-intersection"

    elif "hole lies outside shell" in msg:
        error_type = f"{Colors.ERROR}Hole lies outside shell"

    elif "nested shells" in msg:
        error_type = f"{Colors.ERROR}Nested shells"

    elif "too few points" in msg:
        error_type = f"{Colors.WARNING}Too few points"

    elif "duplicate rings" in msg:
        error_type = f"{Colors.ERROR}Duplicate rings"

    elif "invalid coordinate" in msg:
        error_type = f"{Colors.ERROR}Invalid coordinate"

    else:
        error_type = f"{Colors.WARNING}Unknown error ({Colors.ENDC}{code}{Colors.ERROR})"

    return code, error_type, error_msg


#################################################################################################
def fix_geometry(feature, infile, layer_defn):

    try:
        geom = feature.GetGeometryRef()
        GetFID = feature.GetFID()

        if geom is None:
            return None

        geom = geom.Clone()

        geom.CloseRings()  # ferme anneaux

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

            attrs_formatted = ", ".join(attrs).replace("_MAP_TITLE", "\n\t_MAP_TITLE")

            if error_type == f"{Colors.WARNING}Too few points":  # noqa: SIM114
                log.debug(
                    f"Geometry in file : {Colors.ENDC}{infile}{Colors.DEBUG}, "
                    f"\n\tGeometry type: {Colors.ENDC}{geom_type}{Colors.DEBUG}, "
                    f"\n\tFID: {Colors.ENDC}{GetFID}{Colors.DEBUG}, "
                    f"\n\tMessage code: {Colors.ENDC}{code}{Colors.DEBUG}, {Colors.ENDC}{error_msg}{Colors.DEBUG}, "
                    # f"attributes: {Colors.ENDC}{attrs_formatted}{Colors.DEBUG}"
                )

            elif error_type == f"{Colors.WARNING}Not supported":
                log.debug(
                    f"Geometry in file : {Colors.ENDC}{infile}{Colors.DEBUG}, "
                    f"\n\tGeometry type: {Colors.ENDC}{geom_type}{Colors.DEBUG}, "
                    f"\n\tFID: {Colors.ENDC}{GetFID}{Colors.DEBUG}, "
                    f"\n\tMessage code: {Colors.ENDC}{code}{Colors.DEBUG}, {Colors.ENDC}{error_msg}{Colors.DEBUG}, "
                    # f"attributes: {Colors.ENDC}{attrs_formatted}{Colors.DEBUG}"
                )

            else:
                error_info = (
                    f"Invalid geometry in file : {Colors.ENDC}{infile}{Colors.ERROR}, "
                    f"\nGeometry type: {Colors.ENDC}{geom_type}{Colors.ERROR}, "
                    f"\nFID: {Colors.ENDC}{GetFID}{Colors.ERROR}, "
                    f"\nMessage code: {Colors.ENDC}{code}{Colors.ERROR}, {Colors.ENDC}{error_msg}{Colors.ERROR}, "
                    f"\nAttributes: {Colors.ENDC}{attrs_formatted}{Colors.ERROR}"
                )
                log.error(f"{error_info}")
                globalDat.geometryErrors.append(error_info)
                globalDat.errorCount += 1

            geom = geom.MakeValid()
            if not geom.IsValid():
                return None

        if geom is None or geom.IsEmpty():  # supprime géométries vides
            log.warning(f"Empty geometry removed FID {Colors.ENDC}{GetFID}")
            return None

        gtype = geom.GetGeometryType()

        if gtype in (ogr.wkbLineString, ogr.wkbLineString25D):  # noqa: SIM102
            if geom.GetPointCount() < 2:
                log.warning(f"Line geometry removed, insufficient number of points < 2 {Colors.ENDC}{GetFID}")
                return None

        if gtype == ogr.wkbPolygon:
            ring = geom.GetGeometryRef(0)
            if ring is None or ring.GetPointCount() < 4:
                log.warning(f"Polygon geometry removed, insufficient number of points < 4 {Colors.ENDC}{GetFID}")
                return None

        return geom

    except Exception as e:  # noqa: BLE001
        log.error(f"Geometry in file {Colors.ENDC}{infile}{Colors.ERROR}, cannot be repaired : FID {Colors.ENDC}{GetFID}{Colors.ERROR}, code : {Colors.ENDC}{e}")
        globalDat.errorCount += 1
        return None


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
            log.error(f"shp2gpkg, SHP file does not exist : {Colors.ENDC}{safe_relpath(input_shp)}")
            globalDat.errorCount += 1
            return

        ds = ogr.Open(input_shp)

        if ds is None:
            log.error(f"shp2gpkg, unable to open the SHP : {Colors.ENDC}{safe_relpath(input_shp)}")
            globalDat.errorCount += 1
            return

        layer = ds.GetLayer()

        if layer is None:
            log.error(f"shp2gpkg, unable to retrieve the layer : {Colors.ENDC}{safe_relpath(input_shp)}")
            globalDat.errorCount += 1
            return

        srs = layer.GetSpatialRef()
        featureCount = layer.GetFeatureCount()

        if featureCount < 0:
            log.error(f"shp2gpkg, unable to determine the number of features : {Colors.ENDC}{safe_relpath(input_shp)}")
            globalDat.errorCount += 1
            return

        layer_defn = layer.GetLayerDefn()

        if layer_defn is None:
            log.error(f"shp2gpkg, unable to retrieve the layer definition : {Colors.ENDC}{safe_relpath(input_shp)}")
            globalDat.errorCount += 1
            return

        total_count = featureCount

        log.info(f"SHP file conversion : {Colors.ENDC}{infile}.shp{Colors.INFO} with {Colors.ENDC}{total_count}{Colors.INFO} objets")

        if os.path.exists(output_gpkg):
            try:
                ogr.GetDriverByName("GPKG").DeleteDataSource(output_gpkg)
            except Exception as e:  # noqa: BLE001
                log.error(f"shp2gpkg, unable to delete the existing GPKG : {Colors.ENDC}{output_gpkg}{Colors.ERROR} : {Colors.ENDC}{e}")
                globalDat.errorCount += 1
                return

        driver = ogr.GetDriverByName("GPKG")

        if driver is None:
            log.error("shp2gpkg, driver GPKG GDAL indisponible")
            globalDat.errorCount += 1
            return

        out_ds = driver.CreateDataSource(output_gpkg)

        if out_ds is None:
            log.error(f"shp2gpkg, unable to create the GPKG : {Colors.ENDC}{output_gpkg}")
            globalDat.errorCount += 1
            return

        out_layer = out_ds.CreateLayer(outfile, srs, geom_type=ogr.wkbUnknown)

        if out_layer is None:
            log.error(f"shp2gpkg, unable to create the GPKG layer : {Colors.ENDC}{outfile}")
            globalDat.errorCount += 1
            return

        for i in range(layer_defn.GetFieldCount()):
            field_defn = layer_defn.GetFieldDefn(i)
            if field_defn is None:
                log.warning(f"Invalid field definition, index {Colors.ENDC}{i}")
                continue

            result = out_layer.CreateField(field_defn)

            if result != 0:
                log.error(f"Unable to create the field {Colors.ENDC}{field_defn.GetNameRef()}")
                globalDat.errorCount += 1

        out_layer_defn = out_layer.GetLayerDefn()

        if out_layer_defn is None:
            log.error("shp2gpkg, unable to retrieve the output layer definition")
            globalDat.errorCount += 1
            return

        out_layer.StartTransaction()

        # ============================================================
        # Parcours réel des features
        # Ne PAS utiliser :
        #     for fid in range(featureCount)
        #     feature = layer.GetFeature(fid)
        # Les FID d'un SHP peuvent ne pas être continus.
        # ============================================================
        layer.ResetReading()

        with alive_bar(total_count, title=(f"{Colors.YELLOW}Conversion SHP file {Colors.ENDC}{infile}{Colors.YELLOW} to GPKG {Colors.ENDC}"), length=20) as bar:
            while True:
                # Lecture du prochain feature
                try:
                    feature = layer.GetNextFeature()
                except Exception as e:  # noqa: BLE001
                    error_count += 1
                    log.error(f"SHP read error after {Colors.ENDC}{processed_count}{Colors.ERROR} features : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1
                    bar()
                    continue

                # Fin normale de la couche
                if feature is None:
                    break

                # Récupération du vrai FID
                try:
                    fid = feature.GetFID()
                except Exception:  # noqa: BLE001
                    fid = processed_count

                processed_count += 1

                # Vérification de la géométrie brute
                try:
                    source_geom = feature.GetGeometryRef()

                except Exception as e:  # noqa: BLE001
                    error_count += 1
                    try:
                        attributes = get_dbf_attributes_direct(input_shp, fid)
                    except Exception:  # noqa: BLE001
                        attributes = None

                    corrupted_features.append(
                        {"index": processed_count, "fid": fid, "shape": processed_count, "stage": "GetGeometryRef", "error": str(e), "attributes": attributes}
                    )

                    log.error(f"GetGeometryRef, SHAPE : {Colors.ENDC}{processed_count}{Colors.ERROR}, FID : {Colors.ENDC}{fid}{Colors.ERROR} : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1

                    if attributes is not None:
                        log_feature_attributes(attributes, "error")

                    bar()
                    continue

                # Géométrie NULL
                if source_geom is None:
                    error_count += 1
                    try:
                        attributes = get_dbf_attributes_direct(input_shp, fid)
                    except Exception:  # noqa: BLE001
                        attributes = None

                    corrupted_features.append(
                        {
                            "index": processed_count,
                            "fid": fid,
                            "shape": processed_count,
                            "stage": "GetGeometryRef",
                            "error": "Source geometry is None",
                            "attributes": attributes,
                        }
                    )

                    log.error(f"Geometry NULL, SHAPE : {Colors.ENDC}{processed_count}{Colors.ERROR}, FID : {Colors.ENDC}{fid}")
                    globalDat.errorCount += 1

                    if attributes is not None:
                        log_feature_attributes(attributes, "error")

                    bar()
                    continue

                # Correction de la géométrie
                try:
                    geom = fix_geometry(feature, infile, layer_defn)

                except Exception as e:  # noqa: BLE001
                    geom = None
                    error_count += 1

                    try:
                        attributes = get_dbf_attributes_direct(input_shp, fid)
                    except Exception:  # noqa: BLE001
                        attributes = None

                    corrupted_features.append(
                        {"index": processed_count, "fid": fid, "shape": processed_count, "stage": "fix_geometry", "error": str(e), "attributes": attributes}
                    )

                    log.error(f"Erreur fix_geometry, SHAPE : {Colors.ENDC}{processed_count}{Colors.ERROR}, FID : {Colors.ENDC}{fid}{Colors.ERROR} : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1

                    if attributes is not None:
                        log_feature_attributes(attributes, "error")

                    bar()
                    continue

                # Géométrie impossible à corriger
                if geom is None:
                    error_count += 1
                    try:
                        attributes = get_dbf_attributes_direct(input_shp, fid)
                    except Exception:  # noqa: BLE001
                        attributes = None

                    corrupted_features.append(
                        {
                            "index": processed_count,
                            "fid": fid,
                            "shape": processed_count,
                            "stage": "fix_geometry",
                            "error": "fix_geometry returned None",
                            "attributes": attributes,
                        }
                    )

                    log.warning(f"Geometry impossible to fix, SHAPE : {Colors.ENDC}{processed_count}{Colors.WARNING}, FID : {Colors.ENDC}{fid}")
                    globalDat.errorCount += 1

                    if attributes is not None:
                        log_feature_attributes(attributes, "error")

                    bar()
                    continue

                # Vérification finale de la géométrie
                try:
                    if geom.IsEmpty():
                        error_count += 1
                        log.warning(f"Empty geometry after correction, SHAPE : {Colors.ENDC}{processed_count}{Colors.WARNING}, FID : {Colors.ENDC}{fid}")
                        corrupted_features.append(
                            {
                                "index": processed_count,
                                "fid": fid,
                                "shape": processed_count,
                                "stage": "geometry_validation",
                                "error": "Geometry is empty",
                                "attributes": None,
                            }
                        )

                        globalDat.errorCount += 1
                        bar()
                        continue

                except Exception as e:  # noqa: BLE001
                    error_count += 1

                    log.warning(f"Unable to verify the geometry, SHAPE {Colors.ENDC}{processed_count}{Colors.WARNING} : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1
                    bar()
                    continue

                # Création feature
                out_feature = ogr.Feature(out_layer_defn)

                if out_feature is None:
                    error_count += 1

                    log.error(f"Unable to create the GPKG feature, SHAPE : {Colors.ENDC}{processed_count}")
                    globalDat.errorCount += 1
                    bar()
                    continue

                # Copie attributs
                try:
                    for i in range(out_layer_defn.GetFieldCount()):
                        out_feature.SetField(i, feature.GetField(i))

                except Exception as e:  # noqa: BLE001
                    error_count += 1

                    log.error(f"Attribute copy error, SHAPE : {Colors.ENDC}{processed_count}{Colors.ERROR} : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1

                    out_feature = None
                    bar()
                    continue

                # Affectation géométrie
                try:
                    out_feature.SetGeometry(geom)

                except Exception as e:  # noqa: BLE001
                    error_count += 1

                    log.error(f"Error SetGeometry, SHAPE : {Colors.ENDC}{processed_count}{Colors.ERROR} : {Colors.ENDC}{e}")
                    globalDat.errorCount += 1

                    out_feature = None
                    bar()
                    continue

                # Création dans le GPKG
                try:
                    result = out_layer.CreateFeature(out_feature)

                except Exception as e:  # noqa: BLE001
                    result = 1

                    log.error(f"Error CreateFeature, SHAPE : {Colors.ENDC}{processed_count}{Colors.ERROR}, FID : {Colors.ENDC}{fid}{Colors.ERROR} : {Colors.ENDC}{e}")

                finally:
                    out_feature = None

                if result != 0:
                    error_count += 1

                    log.error(f"Unable to create the GPKG feature, SHAPE : {Colors.ENDC}{processed_count}{Colors.ERROR}, FID : {Colors.ENDC}{fid}")
                    globalDat.errorCount += 1

                    bar()
                    continue

                feature_count += 1

                # Commit par bloc
                if feature_count % 10000 == 0:
                    try:
                        out_layer.CommitTransaction()
                        out_layer.StartTransaction()

                    except Exception as e:
                        log.error(f"GPKG transaction error after {Colors.ENDC}{feature_count}{Colors.ERROR}, features : {Colors.ENDC}{e}")
                        globalDat.errorCount += 1
                        raise

                bar()

        # Commit final
        try:
            out_layer.CommitTransaction()

        except Exception as e:
            log.error(f"Error CommitTransaction final : {Colors.ENDC}{e}")
            globalDat.errorCount += 1
            raise

        layer = None
        ds = None

        out_layer = None
        out_ds = None

        log.info(f"GPKG conversion completed file : {Colors.ENDC}{outfile}{Colors.INFO}, {Colors.ENDC}{feature_count}{Colors.INFO} converted objects")

        if error_count > 0:
            log.warning(f"{Colors.ENDC}{error_count}{Colors.WARNING} objects in error")

        deleted_count = total_count - feature_count

        if deleted_count > 0:
            log.warning(f"{Colors.ENDC}{deleted_count}{Colors.WARNING} deleted geometries")

        if corrupted_features:
            log.warning(f"{Colors.ENDC}{len(corrupted_features)}{Colors.WARNING}features rejected during conversion")

            for item in corrupted_features:
                log.warning(
                    f"SHAPE {Colors.ENDC}{item['shape']}{Colors.WARNING} / FID {Colors.ENDC}{item['fid']}{Colors.WARNING} / {Colors.ENDC}{item['stage']}{Colors.WARNING} : {Colors.ENDC}{item['error']}"
                )

        return

    # Erreur GDAL / Runtime
    except RuntimeError as e:
        log.error(f"Error in conversion file {Colors.ENDC}{infile}{Colors.ERROR} SHP to GPKG : {Colors.ENDC}{e}")
        globalDat.errorCount += 1

    # Erreur inattendue
    except Exception as e:  # noqa: BLE001
        log.error(f"Unexpected error in shp2gpkg {Colors.ENDC}{infile}{Colors.ERROR} : {Colors.ENDC}{e}")
        globalDat.errorCount += 1

    # Nettoyage garanti
    finally:
        try:
            if out_layer is not None:
                out_layer = None

        except Exception:  # noqa: BLE001, S110
            pass

        try:
            if out_ds is not None:
                out_ds = None

        except Exception:  # noqa: BLE001, S110
            pass

        try:
            if ds is not None:
                ds = None

        except Exception:  # noqa: BLE001, S110
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
                log.error(f"Error in file {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR}, record {Colors.ENDC}{i + 1}{Colors.ERROR} is None")
                globalDat.errorCount += 1
                continue

            geometry = feature.GetGeometryRef()

            # Vérifier présence géométrie
            if geometry is None:
                log.error(
                    f"Error in file {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR}, "
                    f"record {Colors.ENDC}{i + 1}{Colors.ERROR} has no geometry, correct it : "
                    f"_ID: {Colors.ENDC}{feature.GetField('_ID')}{Colors.ERROR}, "
                    f"_NAME: {Colors.ENDC}{feature.GetField('_NAME')}{Colors.ERROR}, "
                    f"_SURVEY: {Colors.ENDC}{feature.GetField('_SURVEY')}{Colors.ENDC}"
                )
                globalDat.errorCount += 1
                continue

            # Ignorer géométries vides
            if geometry.IsEmpty():
                log.warning(f"Warning, file {Colors.ENDC}{safe_relpath(file_path)}{Colors.WARNING}, Record {i + 1} has empty geometry. Skipping.{Colors.ENDC}")
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
                    except Exception:  # noqa: BLE001
                        validity_explanation = "Invalid Geometry"

                    error_details.setdefault(validity_explanation, []).append(i)

            except Exception as e:  # noqa: BLE001
                log.error(
                    f"Error in file {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR}, "
                    f"validating geometry for record {Colors.ENDC}{i + 1}{Colors.ERROR}: "
                    f"{Colors.ENDC}{e}{Colors.ENDC}"
                )
                globalDat.errorCount += 1

        log.info(f"Geometry num: {Colors.ENDC}{total_records}{Colors.YELLOW}, types found: {Colors.ENDC}{record_types}")

        if total_errors == 0:
            log.info(f"File error check OK: {Colors.ENDC}{safe_relpath(file_path)}{Colors.GREEN}, records: {Colors.ENDC}{total_records}{Colors.GREEN}, no errors found")
        else:
            log.error(
                f"File error check NOK: {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR}, "
                f"records: {Colors.ENDC}{total_records}{Colors.ERROR}, "
                f"total errors: {Colors.ENDC}{total_errors}"
            )
            globalDat.errorCount += 1

        log.info(f"Geometry in file: {Colors.ENDC}{safe_relpath(file_path)}{Colors.GREEN}, types found: {Colors.ENDC}{record_types}")

        datasource = None  # fermeture propre

        return error_details, total_errors

    except Exception as e:  # noqa: BLE001
        log.error(f"Topology error when analyzing the shapefile: {Colors.ENDC}{safe_relpath(file_path)}{Colors.ERROR}, code: {Colors.ENDC}{e}")
        globalDat.errorCount += 1
        return {}, -1


#################################################################################################
def ThtoQGis(pathshp, outputspath):

    # Check if areas, lines, points2d and outline shapefiles exists...

    # Check if Outputs path exists
    if not os.path.exists(outputspath):
        log.warning(f"WARNING: {Colors.ENDC}{safe_relpath(outputspath)}{Colors.WARNING} does not exist, I am creating it...")
        os.mkdir(outputspath)

    file_list = ["points2d", "lines2d", "outline2d", "areas2d", "walls3d", "stations3d", "shots3d"]
    dest_list = ["points2d", "outline2d", "walls3d", "stations3d", "shots3d"]

    log.info(f"{Colors.HEADER}Step 1 : test files and convert to GPKG format in the folder:{Colors.ENDC}{Colors.HEADER2} {safe_relpath(outputspath)}".ljust(129))
    count = 0

    for fname in file_list:
        count += 1
        log.info(f"{'═' * 101}")
        log.info(f"Process with file ({Colors.ENDC}{count}/{len(file_list)}{Colors.INFO}): {Colors.ENDC}{fname}.shp")
        file = os.path.join(pathshp, fname + ".shp")
        if not os.path.isfile(file):
            log.error(f"The file {Colors.ENDC}{(str(file))}{Colors.ERROR} does not exist'{Colors.ENDC}")  # noqa: RUF010
            globalDat.errorCount += 1
            continue
        err, valid = diagnostic(file, True)

        if fname in dest_list:
            destinationName = fname

        else:
            destinationName = fname + "_fixed"

        shp2gpkg(pathshp, fname, outputspath, destinationName)

        err2, valid2 = diagnostic(os.path.join(outputspath, destinationName + ".gpkg"), globalDat.debug_log)

        if err == 0 and err2 == 0 and valid == valid2:
            log.info(
                f"Conversion of {Colors.ENDC}{valid}{Colors.INFO} features in file {Colors.ENDC}{safe_relpath(outputspath + destinationName + '.gpkg')}{Colors.INFO} without issue  "
            )

        else:
            log.debug(
                f"INITIAL, error : {Colors.ENDC}{err}{Colors.DEBUG}, feature : {Colors.ENDC}{valid}{Colors.DEBUG}\nFINAL : error : {Colors.ENDC}{err2}{Colors.DEBUG}, feature {Colors.ENDC}{valid}"
            )
            log.error(f"Conversion of {Colors.ENDC}{(safe_relpath(outputspath + destinationName + '.gpkg'))}{Colors.ERROR} with issue(s), please fix it manually...")
            globalDat.errorCount += 1
            continue

    log.info(f"{Colors.HEADER}Step 2 : adapte drawing files (cut it) for QGis in the folder:{Colors.ENDC}{Colors.HEADER2} {safe_relpath(outputspath)}".ljust(129))

    ## Work with lines
    file_path = os.path.join(outputspath, "lines2d_fixed.gpkg")
    valid = cutGPKG(file_path, os.path.join(outputspath, "outline2d.gpkg"), os.path.join(outputspath, "lines2dMasked.gpkg"))
    err, valid2 = diagnostic(os.path.join(outputspath, "lines2dMasked.gpkg"))

    if (valid2 - valid) != 0:
        log.warning(f"{Colors.ENDC}{abs(valid2 - valid)}{Colors.WARNING} deleted geometries need to be verified in {Colors.ENDC}lines2dMasked.gpkg{Colors.WARNING} file")

    elif valid2 == -1:
        log.error(f"Clipped geometries in {Colors.ENDC}lines2dMasked.gpkg{Colors.INFO} file")

    else:
        log.info(f"{Colors.ENDC}{valid}{Colors.INFO} clipped geometries in {Colors.ENDC}lines2dMasked.gpkg{Colors.ERROR} file")

    if os.path.exists(file_path):
        os.remove(file_path)

    ## Work with Areas
    file_path = os.path.join(outputspath, "areas2d_fixed.gpkg")
    valid = cutGPKG(file_path, os.path.join(outputspath, "outline2d.gpkg"), os.path.join(outputspath, "areas2dMasked.gpkg"))
    err, valid2 = diagnostic(os.path.join(outputspath, "areas2dMasked.gpkg"))

    if (valid2 - valid) != 0:
        log.warning(f"{Colors.ENDC}{abs(valid2 - valid)}{Colors.WARNING} Deleted geometries need to be verified in {Colors.ENDC}areas2d_fixed.gpkg{Colors.WARNING} file")

    elif valid2 == -1:
        log.error(f"in clipped geometries in {Colors.ENDC}areas2d_fixed.gpkg{Colors.ERROR} file")

    else:
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
if __name__ == "__main__":
    #################################################################################################
    ogr.UseExceptions()
    gdal.UseExceptions()
    gdal.PushErrorHandler("CPLQuietErrorHandler")
    gdal.SetConfigOption("SHAPE_ENCODING", "UTF-8")
    gdal.SetConfigOption("OGR_CHARSET", "UTF-8")
    gdal.SetConfigOption("OGR_GPKG_ENCODING", "UTF-8")

    globalDat.errorCount = 0
    input_folder_name = ""
    start_time = time.time()

    #################################################################################################
    # Parse arguments                                                                               #
    #################################################################################################
    parser = argparse.ArgumentParser(
        description=f"{Colors.HEADER}Script to generate QGis (.gpkg) files from Therion (.shp) files with auto-correction if possible",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.print_help = colored_help.__get__(parser)
    parser.add_argument(
        "--option",
        default="auto",
        choices=["auto", "manual", "test"],
        help=(
            f"Execution options for pyThtoQgis.py\n"
            f"auto\t-> Execution from the folder {globalDat.pathshp} (défaut)\n"
            f"manual\t-> Manual selection by a window box for the input folder\n"
            f"test\t-> Tests fonction (debug)\n"
        ),
    )

    parser.add_argument("--folder", type=str, help="Input folder containing the shapefiles to process")

    parser.epilog = (
        f"{Colors.HEADER}Note : {Colors.GREEN}to generate shp files in therion, add in thconfig file the commande\n"
        f"\t{Colors.GREEN}-> {Colors.ENDC}export model -fmt esri -o Outputs/SHP/ -enc UTF-8{Colors.ENDC}\n"
        f"\n"
        f"{Colors.HEADER}Usage examples :{Colors.ENDC}\n"
        f'\t{Colors.GREEN}-> {Colors.ENDC}python pyThtoQgis.py --folder "../../Outputs/SHP/"{Colors.ENDC}\n'
        f"\t{Colors.GREEN}-> {Colors.ENDC}python pyThtoQgis.py --option manual{Colors.ENDC}\n"
    )

    # Analyser les arguments de ligne de commande
    args = parser.parse_args()

    if os.name == "posix":
        os.system("clear")  # Linux, MacOS
    elif os.name == "nt":
        os.system("cls")  # Windows
    else:
        print("\n" * 100)

    #################################################################################################
    if args.folder:
        input_folder = os.path.normpath(args.folder)
        output_folder = os.path.join(input_folder, globalDat.outputfolder)

        if not os.path.exists(input_folder):
            log = setup_logger(globalDat.output_log, globalDat.debug_log)
            log.error(f"ERROR the folder {Colors.ENDC}{input_folder}{Colors.ERROR} does not exist'{Colors.ENDC}")
            globalDat.errorCount += 1
            sys.exit()

        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        log = setup_logger(os.path.join(output_folder, globalDat.file_log), globalDat.debug_log)

        log.info(f"{Colors.HEADER}╔{'═' * 99}╗")
        log.info(
            f"{Colors.HEADER}║ Script to generate QGis {Colors.HEADER2}(.gpkg){Colors.HEADER} files from Therion {Colors.HEADER2}(.shp){Colors.HEADER} files with auto-correction if possible  ║"
        )
        log.info(f"{Colors.HEADER}║        original written by X. Robert, ISTerre : {Colors.HEADER2}October 2022{Colors.HEADER}".ljust(136) + "║")
        log.info(f"{Colors.HEADER}║        updated by : {Colors.HEADER2}alexandre.pont@yahoo.fr{Colors.HEADER}".ljust(136) + "║")
        log.info(f"{Colors.HEADER}║        version : {Colors.HEADER2}{globalDat.Version}{Colors.HEADER}".ljust(136) + "║")
        log.info(f"{Colors.HEADER}║        mode : {Colors.HEADER2}commande line mode{Colors.HEADER}".ljust(136) + "║")
        log.info(f"{Colors.HEADER}║        input folder :  {Colors.HEADER2}{safe_relpath(input_folder)}{Colors.HEADER}".ljust(136) + "║")
        log.info(f"{Colors.HEADER}║        output folder : {Colors.HEADER2}{safe_relpath(output_folder)}{Colors.HEADER}".ljust(136) + "║")
        log.info(
            f"{Colors.HEADER}║        log file      : {Colors.HEADER2}{safe_relpath(next((h.baseFilename for h in log.handlers if isinstance(h, logging.FileHandler)), None))}{Colors.HEADER}".ljust(
                136
            )
            + "║"
        )
        log.info(f"{Colors.HEADER}╚{'═' * 99}╝")

        # sys.exit()

        ThtoQGis(input_folder, output_folder)

    elif args.option == "auto":
        log = setup_logger(globalDat.output_log, globalDat.debug_log)

        if not os.path.exists(globalDat.outputspath):
            os.makedirs(globalDat.outputspath)

        log.info(f"{Colors.HEADER}╔{'═' * 99}╗")
        log.info(
            f"{Colors.HEADER}║ Script to generate QGis {Colors.HEADER2}(.gpkg){Colors.HEADER} files from Therion {Colors.HEADER2}(.shp){Colors.HEADER} files with auto-correction if possible  ║"
        )
        log.info(f"{Colors.HEADER}║        original written by X. Robert, ISTerre : {Colors.HEADER2}October 2022{Colors.HEADER}".ljust(136) + "║")
        log.info(f"{Colors.HEADER}║        updated by : {Colors.HEADER2}alexandre.pont@yahoo.fr{Colors.HEADER}".ljust(136) + "║")
        log.info(f"{Colors.HEADER}║        version : {Colors.HEADER2}{globalDat.Version}{Colors.HEADER}".ljust(136) + "║")
        log.info(f"{Colors.HEADER}║        mode : {Colors.HEADER2}auto{Colors.HEADER}".ljust(136) + "║")
        log.info(f"{Colors.HEADER}║        input folder :  {Colors.HEADER2}{globalDat.pathshp}{Colors.HEADER}".ljust(136) + "║")
        log.info(f"{Colors.HEADER}║        output folder : {Colors.HEADER2}{globalDat.outputspath}{Colors.HEADER}".ljust(136) + "║")
        log.info(
            f"{Colors.HEADER}║        log file      : {Colors.HEADER2}{safe_relpath(next((h.baseFilename for h in log.handlers if isinstance(h, logging.FileHandler)), None))}{Colors.HEADER}".ljust(
                136
            )
            + "║"
        )
        log.info(f"{Colors.HEADER}╚{'═' * 99}╝")

        ThtoQGis(globalDat.pathshp, globalDat.outputspath)

    elif args.option == "manual":
        root = tk.Tk()
        root.withdraw()  # Cacher la fenêtre principale de Tkinter
        input_folder_name = filedialog.askdirectory(title="Choose the shp folder")

        input_folder = input_folder_name + "\\"
        output_folder = input_folder + globalDat.outputfolder

        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        log = setup_logger(output_folder + globalDat.file_log, globalDat.debug_log)

        if not input_folder_name:
            log.error("No folder selected. The program will terminate")
            globalDat.errorCount += 1
            sys.exit()

        log.info(f"{Colors.HEADER}*********************************************************************************************************")
        log.info(f"{Colors.HEADER}Script to generate QGis (.gpkg) files from Therion (.shp) files with auto-correction if possible")
        log.info(f"{Colors.HEADER}        original written by X. Robert, ISTerre : {Colors.ENDC}October 2022")
        log.info(f"{Colors.HEADER}        updated by : {Colors.ENDC}alexandre.pont@yahoo.fr")
        log.info(f"{Colors.HEADER}        version : {Colors.ENDC}{globalDat.Version}")
        log.info(f"{Colors.HEADER}        manual mode")
        log.info(f"{Colors.HEADER}        input folder :  {Colors.ENDC}{safe_relpath(input_folder)}")
        log.info(f"{Colors.HEADER}        output folder : {Colors.ENDC}{safe_relpath(output_folder)}")
        log.info(f"{Colors.HEADER}*********************************************************************************************************")

        ThtoQGis(input_folder, output_folder)

    elif args.option == "test":
        log = setup_logger(globalDat.output_log, globalDat.debug_log)

        if not os.path.exists(globalDat.outputspath):
            os.makedirs(globalDat.outputspath)

        log.info(f"{Colors.HEADER}*********************************************************************************************************")
        log.info(f"{Colors.HEADER}Script to generate QGis (.gpkg) files from Therion (.shp) files with auto-correction if possible")
        log.info(f"{Colors.HEADER}        original written by X. Robert, ISTerre : {Colors.ENDC}October 2022")
        log.info(f"{Colors.HEADER}        updated by : {Colors.ENDC}alexandre.pont@yahoo.fr")
        log.info(f"{Colors.HEADER}        version : {Colors.ENDC}{globalDat.Version}")
        log.info(f"{Colors.HEADER}        test mode")
        log.info(f"{Colors.HEADER}        input folder :  {Colors.ENDC}{globalDat.pathshp}")
        log.info(f"{Colors.HEADER}        output folder : {Colors.ENDC}{globalDat.outputspath}")
        log.info(f"{Colors.HEADER}*********************************************************************************************************")

        extractVertices(globalDat.outputspath + "lines2dMasked.gpkg", globalDat.outputspath + "points2d.gpkg")

        sys.exit(0)

        diagnostic(globalDat.pathshp + "lines2d.shp")
        count_topology_errors(globalDat.pathshp + "lines2d.shp")
        shp2gpkg(globalDat.pathshp, "lines2d", globalDat.outputspath, "lines2d")
        diagnostic(globalDat.outputspath + "lines2d.gpkg")

        diagnostic(globalDat.pathshp + "outline2d.shp")
        shp2gpkg(globalDat.pathshp, "outline2d", globalDat.outputspath, "outline2d")
        diagnostic(globalDat.outputspath + "outline2d.gpkg")

        # diagnostic(globalDat.pathshp + 'points2d.shp')
        # shp2gpkg(globalDat.pathshp, 'points2d', globalDat.outputspath, 'points2d')
        # diagnostic(globalDat.outputspath + 'points2d.gpkg')

        diagnostic(globalDat.pathshp + "areas2d.shp")
        shp2gpkg(globalDat.pathshp, "areas2d", globalDat.outputspath, "areas2d")
        diagnostic(globalDat.outputspath + "areas2d.gpkg")

        # diagnostic(globalDat.pathshp + 'walls3d.shp')
        # shp2gpkg(globalDat.pathshp, 'walls3d', globalDat.outputspath, 'walls3d')
        # diagnostic(globalDat.outputspath + 'walls3d.gpkg')

        cutGPKG(globalDat.outputspath + "lines2d.gpkg", globalDat.outputspath + "outline2d.gpkg", globalDat.outputspath + "lines2dMasked.gpkg")
        diagnostic(globalDat.outputspath + "lines2dMasked.gpkg")

        cutGPKG(globalDat.outputspath + "areas2d.gpkg", globalDat.outputspath + "outline2d.gpkg", globalDat.outputspath + "areas2dMasked.gpkg")
        diagnostic(globalDat.outputspath + "areas2dMasked.gpkg")

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

log.info(f"{Colors.HEADER}Step 3 : final summary {Colors.ENDC}{Colors.HEADER2}".ljust(129))
log.info(f"Execution completed in {Colors.ENDC}{elapsed:.2f}{Colors.INFO} s")

if globalDat.errorCount == 0:
    log.info(f"{'═' * 101}")
    log.info("Execution completed without errors")
    log.info(f"{'═' * 101}")

else:
    log.error(f"{'═' * 100}")
    log.error(f"Execution completed with {Colors.ENDC}{globalDat.errorCount}{Colors.ERROR} errors")
    for i, error in enumerate(globalDat.geometryErrors, start=1):
        log.error(f" {error}")
    log.error(f"{'═' * 100}")


if len(globalDat.geometryWarning) > 0:
    log.warning(f"{'═' * 98}")
    log.warning(f"Execution completed with {Colors.ENDC}{len(globalDat.geometryWarning)}{Colors.WARNING} warning")
    for i, error in enumerate(globalDat.geometryWarning, start=1):
        log.warning(f" {error}")
    log.warning(f"{'═' * 98}")
