######!/usr/bin/env python
# -*- coding: utf-8 -*-  # noqa: UP009
# coding: utf8

# Copyright (c) 2020 Xavier Robert <xavier.robert@ird.fr>
# SPDX-License-Identifier: GPL-3.0-or-later
# Modifié Alex 2025 07 01

"""
Script to build Therion files
By Xavier Robert
Lima, 2016.06.21

USAGE :
  1- Run in the terminal: $ python buildthconfig.py


INPUTS:
The inputs are in the script file, in the "# Define data to analysis" section.
The different arguments are described.

"""

###### To DO :  #######
#    - Test the MTL pdfs (I have not tested it, even if it should be OK)
#    - Add error bars on data graphs ?
#      For that we should read the input data file given in topo_parameters.txt
#                    (paragraphe N°12 of topo_parameters.txt)
#
###### End To DO #######

from __future__ import division  # noqa: I001, UP010
# This to be sure that the result of the division of integers is a real, not an integer
# from __future__ import unicode_literals

# Import modules
from Lib.general_fonctions import sanitize_filename
import sys, os, copy, datetime  # noqa: F401
from pyproj import Proj, transform


#################################################################################################
def writeheader_th(file, cavename, entrance):
    """
    Function to write the header of the file.th

    INPUTS:
       file     : variable that sets the file.th
       cavename : name of the cave
       entrance : name of the entrance station

    OUTPUTS:
            None

    USAGE:
            writeheader_th(file, cavename, entrance)

    Author: Xavier Robert, Lima 2016/06/27

    """

    file.write('encoding utf-8 \n\nsurvey %s -title "%s" -entrance "%s" \n' % (sanitize_filename(cavename), cavename, entrance))  # noqa: UP031

    return  # noqa: PLR1711


#################################################################################################
def writecenterlineheader(file, entrance, settings, comments, data, coordsyst, coordinates, club, icomments, thlang, cavename):
    """
    Function to write the centerline header


    INPUTS:
            file        : variable that sets the file.th
            entrance    : name of the entrance station
            settings    : List of the settings of this survey section
            comments    : String that correspond to the end of the string "Line"
                          that do not correspond to the settings
            data        : data from this survey section
            coordsyst   : Coordinates system to set the entrance coordinates
            coordinates : Entrance coordinates
            club        : Name of the group that explored the cave
            icomments   : True if comments in the file
                          False if not
            thlang      : 'fr' for french
                          'en' for english
                          ... other languages not implemented

    OUTPUTS:
            None

    USAGE:
            writeheader_th(file, cavename, entrance)

    Author: Xavier Robert, Lima 2016/06/27

    """
    # First, define dictionaries to help the coding
    # angleU: define the angle unit
    angleU = {"Deg": "degrees", "Degd": "degrees", "Gra": "grad"}
    # compass dir:
    dir = {"Dir": "", "Inv": "back"}
    # lruddir: Set the LRUD
    lruddir = {"Dir": "left right up down", "Inv": "right left up down", "Nod": ""}
    # unitcounter: set the unit of the counter (for the length)
    unitcounter = {"Vulc": "centi", "Prof": "", "Deniv": ""}
    # unitclino: used to correct the clino if topoVulcain
    unitclino = {"Deg": "90", "Degd": "90", "Gra": "100"}
    # typelen: type of length measures
    # typelem = {u'Deca' : u'normal',
    #          u'Topof' : u'topofil',
    #          u'Vulc' : u'topofil',
    #          u'Prof' : u'diving',
    #          u'Deniv' : u'deniv'}
    # style: data style
    style = {
        "Deca": "normal",
        "Topof": "topofil",
        "Diving": "diving",
        "Prof": "diving",
        "Carth": "carthesian",
        "Cylp": "cylpolar",
        "Dim": "dimensions",
        "Nosy": "nosurvey",
    }
    # station: type of stations
    station = {"station": "station", "from": "from", "to": "to", "vtopo": "from to"}
    # lensurv: how are set the length measurements
    lensurv = {"Deca": "length", "Topof": "fromcount tocount", "Diving": "length", "Prof": "length"}
    # slopesurv: how are set the slope measurements
    slopesurv = {"Clino": "clino", "Vulc": "clino", "Deniv": "depthchange", "Prof": "depth"}

    # Begin the centerline
    file.write("\n\tcenterline \n")

    # if entrance in the data, write the entrance coordinates
    if [datal for datal in data if entrance in datal] != []:
        if icomments:
            if thlang == "fr":
                file.write(
                    "\t\t# Si le système de coordonnées n'est pas le système"
                    " Lambert français, voir le Thbook et le fichier"
                    " extern/proj4/nad/epsg dans le dossier source de Therion \n"
                )
                file.write("\t\t# Si les coordonnées de l'entrée sont connues, copier dans la centerline correspondante et décommenter les 2 lignes suivantes : \n")
            elif thlang == "en":
                file.write(
                    "\t\t# If your are not in the french Lambert system, "
                    " To find number of your system, see"
                    " extern/proj4/nad/epsg file in the Therion"
                    " source distribution \n"
                )
                file.write("\t\t# If the entrance coordinates are known, uncomment and copy in the corresponding centerline the next 2 lines: \n")
        if coordsyst != None:
            file.write(
                '\t\tcs %s\n\t\tfix %s %s %s %s\n\t\tstation %s "%s" entrance\n\n'  # noqa: UP031
                % (coordsyst, entrance, coordinates[0], coordinates[1], coordinates[2], entrance, cavename)
            )  # [Correction Alex 2026 11 19]  # noqa: RUF100, UP031
        else:
            file.write(
                '\t\t#cs %s\n\t\t#fix %s %s %s %s\n\t\t#station %s "%s" entrance\n\n'  # noqa: UP031
                % (coordsyst, entrance, coordinates[0], coordinates[1], coordinates[2], entrance, cavename)
            )  # [Correction Alex 2026 11 19]  # noqa: RUF100, UP031

    typem = "Deca"
    if "Topof" not in settings:
        settings[1:1] = " "
        typem = "Topof"
    if "Prof" in settings or "Deniv" in settings:
        settings[4:4] = " "
    # next line used to debug
    # file.write(u'\t' + str(settings) + u'\n')
    # write the survey characteristics
    file.write("\t\tdate %s\n" % str(settings[9]))  # noqa: UP031
    if icomments:
        if thlang == "fr":
            file.write('\t\t# Si date est utilisé, commenter la ligne "declination", la date sera utilisée pour la calculer\n')
        elif thlang == "en":
            file.write('\t\t# If date is used, comment the ligne "declination", the date will be use to compute it\n')
    if str(settings[9]) == "":
        file.write("\t\tdeclination %s %s \n" % (str(settings[5]), angleU[settings[2]]))  # noqa: UP031
    else:
        file.write("\t\t# declination %s %s \n" % (str(settings[5]), angleU[settings[2]]))  # noqa: UP031

    # file.write(u'\t\t\tteam "G.S. Vulcain" \n')
    file.write('\t\t# team "%s" \n' % club)  # noqa: UP031
    file.write("\t\t# explo-date %s\n" % str(settings[9]))  # noqa: UP031
    # file.write(u'\t\t\texplo-team "G.S. Vulcain" \n')
    if club.count(" ") >= 2:
        _club = club.replace(" ", "/", 1)
    else:
        _club = club
    file.write('\t\texplo-team "%s" \n' % _club)  # noqa: UP031

    if icomments:
        if thlang == "en":
            file.write("\t\t# (to be completed, add many lines as you need) \n")
        elif thlang == "fr":
            file.write("\t\t# (peut être complété en ajoutant le nombre de lignes nécessaires) \n")

    dirs = settings[6].rstrip("\n\r").split(",")

    file.write("\n\t\tunits length meters \n")
    if "Topof" in settings:
        file.write("\t\tunits counter %smeters \n" % unitcounter[settings[3]])  # noqa: UP031
        file.write("\t\tcalibrate counter 0 %s \n" % settings[1])  # noqa: UP031
        # To set the slope
        if "Vulc" in settings:
            file.write("\t\tcalibrate clino 1 %s -1\n" % unitclino[settings[4]])  # noqa: UP031
    if "Prof" in settings:
        file.write("\t\tunits depth meters \n")
        typem = "Prof"
    elif "Deniv" in settings:
        file.write("\t\tunits depth meters \n")
        typem = "Diving"

    file.write("\t\tunits compass %s \n" % (angleU[settings[2]]))  # noqa: UP031
    if "Vulc" in settings or "Clino" in settings:
        file.write("\t\tunits clino %s \n" % (angleU[settings[4]]))  # noqa: UP031

    file.write(
        "\n\t\tdata %s %s %s %scompass %s%s %s\n"  # noqa: UP031
        % (style[typem], station["vtopo"], lensurv[settings[0]], dir[dirs[0]], dir[dirs[1]], slopesurv[settings[3]], lruddir[dirs[2]])
    )
    if comments != "":
        file.write("\t\t\t#" + comments + "\n")

    return  # noqa: PLR1711


#################################################################################################
def writedata(file, settings, data, dataold):
    """
    function to write the data in the .th file

    INPUTS:
            file     : variable that sets the file.th
            settings : List of the settings of this survey section
            data     : data from this survey section
            dataold  : data from the previous survey section

    OUTPUTS:
            None

    USAGE:
            writeheader_th(file, cavename, entrance)

    Author: Xavier Robert, Lima 2016/06/27

    """

    # dictl = length of the data line
    dictl = {"Deca": 9, "Topof": 10}

    i = 0
    for elems in data:
        for k in [0, 2]:
            if elems[k] == "*":
                # remove the '*', and replace them with the right data !
                if i == 0:
                    elems[k] = dataold[len(dataold) - 1][k + 1]
                else:
                    elems[k] = data[i - 1][k + 1]

        if elems[0] == elems[1]:
            elems[1] = elems[1] + "d"

        for k in range(dictl[settings[0]] - 4, dictl[settings[0]]):
            # Check that LRUD != '*'; If yes, change them to 0
            if elems[k] == "*":
                elems[k] = "0"

            # Si le premier caractère est '-', on le remplace par '+' [Ajout Alex 2025 11 10]
            elif elems[k].startswith("-"):
                elems[k] = "+" + elems[k][1:]

        # Check if option 'E'
        if "E" in elems:
            file.write("\t\t\tflags duplicate\n")
        # We write the data
        # if elems[0:1] == "*":
        # 	elems[0:1] = "-"
        file.write("\t\t\t" + "\t".join("-" if i == 1 and x == "*" else x for i, x in enumerate(elems[0 : dictl[settings[0]]])))

        # file.write(u'\t\t\t' + u'\t'.join(x for x in elems[0:dictl[settings[0]]]))

        if len(elems) > (dictl[settings[0]] + 2):
            if elems[dictl[settings[0]] + 1] != "N" and elems[dictl[settings[0]] + 1] != "I":
                # we add the comment if there is one
                file.write("\t# " + " ".join(x for x in elems[(dictl[settings[0]] + 1) : len(elems)])[1:-1] + "\n")
            elif len(elems) > (dictl[settings[0]] + 3):
                file.write("\t# " + " ".join(x for x in elems[(dictl[settings[0]] + 2) : len(elems)])[1:-1] + "\n")
            else:
                file.write("\n")
        else:
            file.write("\n")
        if elems[(dictl[settings[0]])] == "I":
            file.write("\t\t\textend reverse \n")
        if "E" in elems:
            file.write("\t\t\tflags not duplicate\n")
        i += 1  # noqa: SIM113

    return  # noqa: PLR1711


#################################################################################################
def write_thtot(file, cavename="cave", icomments=True, thlang="en"):
    """
    Function to write the file cavename-tot.th

    INPUTS:
       file         : variable that sets the file.th
       cavename     : name of the cave
       icomments    : True if comments in the file
                          False if not
            thlang      : 'fr' for french
                          'en' for english
                          ... other languages not implemented

    OUTPUTS:
            None

    USAGE:
            write_thtot(file, cavename,  icomments, thlang)

    Author: Xavier Robert, Grenoble 2021/01/03

    """

    file.write("encoding utf-8 \n\n")

    # file.write(u'encoding utf-8' \n\nsurvey %s -title "%s" -entrance "%s" \n'
    #           %(cavename.replace(u' ', u'_'), cavename, entrance))

    if icomments:
        if thlang == "fr":
            file.write("# Copyright (C) %s Xavier Robert <xavier.robert***@***ird.fr>\n" % (str(datetime.datetime.now().year)))  # noqa: DTZ005, UP031
            file.write("# Ce travaille est sous la License Creative Commons Attribution-ShareAlike-NonCommecial :\n")
            file.write("#	<http://creativecommons.org/licenses/by-nc-sa/4.0/>\n\n")
    elif thlang == "en":
        file.write("# Copyright (C) %s Xavier Robert <xavier.robert***@***ird.fr>\n" % (str(datetime.datetime.now().year)))  # noqa: DTZ005, UP031
        file.write("# This work is under the Creative Commons Attribution-ShareAlike-NonCommecial License:\n")
        file.write("#	<http://creativecommons.org/licenses/by-nc-sa/4.0/>\n\n")

    file.write('survey %s -title "%s"\n\n' % (sanitize_filename(cavename), cavename.replace(" ", "_")))  # noqa: UP031
    # file.write(u'survey %s -title "%s"\n\n' %(cavename.replace(u' ', u'_'), cavename.replace(u' ', u'_')))

    if icomments:
        if thlang == "fr":
            file.write("\t# Pour importer les différentes données de différents fichiers topos :\n")
        if thlang == "en":
            file.write("\t# To import data from different data files:\n")
    file.write("\tinput Data/%s.th\n\n" % (cavename.replace(" ", "_")))  # noqa: UP031

    file.write("#\tcenterline\n")
    if icomments:
        if thlang == "fr":
            file.write("\t\t##Rajout des longueurs explorées, non topo, ou topos perdues\n")
        elif thlang == "en":
            file.write("\t\t##Add length explored, but not surveyed, or with lost surveys\n")

        file.write('#\t\tstation Ca.31@%s "+78 m explorés " continuation explored 78m\n' % (cavename.replace(" ", "_")))  # noqa: UP031
    if icomments:
        if thlang == "fr":
            file.write("\t\t## Pour assembler plusieurs fichiers topos\n")
        elif thlang == "en":
            file.write("\t\t## To join different surveys\n")

    file.write("#\t\tequate  6@%s  0@%s\n\n" % (cavename.replace(" ", "_"), cavename.replace(" ", "_") + "2"))  # noqa: UP031

    file.write("#\tendcenterline)\n\n")

    if icomments:
        file.write("#\t##########################################################################################\n")
        if thlang == "fr":
            file.write("#\t## Pour importer les différents fichiers de dessins en plan\n")
            file.write("#\t## Et Pour assembler plusieurs scraps entre eux, il faut utiliser la commande\n")
            file.write("#\t## join scrap1 scrap2 -count n (où n = nombre de galerie à connecter, par défaut n = 1). C'est tout simple !\n")
        elif thlang == "en":
            file.write("#\t## To import different th2 files\n")
            file.write("#\t## And to join different scraps together, you need to use the command\n")
            file.write("#\t## join scrap1 scrap2 -count n (where n = number of connections, by default n = 1). This is simple!\n")

    file.write("#\tjoin scrap1 scrap2 #-count n\n\n")

    if icomments:
        if thlang == "fr":
            file.write("## Pour le plan\n")
        elif thlang == "en":
            file.write("## For plan view\n")

    file.write("input Data/%s.th2\n\n" % (cavename.replace(" ", "_")))  # noqa: UP031

    if icomments:
        if thlang == "fr":
            file.write("## Pour la coupe développée\n")
        elif thlang == "en":
            file.write("## For extended elevation\n")

    file.write("input Data/%s-coupe.th2\n\n" % (cavename.replace(" ", "_")))  # noqa: UP031

    if icomments:
        if thlang == "fr":
            file.write("## Appel des maps\n")
        elif thlang == "en":
            file.write("## Call the maps file\n")

    file.write("input %s-maps.th\n\n" % (cavename.replace(" ", "_")))  # noqa: UP031
    file.write("endsurvey\n")

    return  # noqa: PLR1711


#################################################################################################
def write_thmaps(file, cavename="cave", icomments=True, thlang="en"):
    """
    Function to write the file cavename-maps.th

    INPUTS:
       file         : variable that sets the file.th
       cavename     : name of the cave
       icomments    : True if comments in the file
                          False if not
            thlang      : 'fr' for french
                          'en' for english
                          ... other languages not implemented

    OUTPUTS:
            None

    USAGE:
            write_thmaps(file, cavename, icomments, thlang)

    Author: Xavier Robert, Grenoble 2021/01/03

    """

    file.write("encoding utf-8 \n\n")

    # file.write(u'encoding utf-8' \n\nsurvey %s -title "%s" -entrance "%s" \n'
    #           %(cavename.replace(u' ', u'_'), cavename, entrance))

    if icomments:
        if thlang == "fr":
            file.write("# Copyright (C) %s Xavier Robert <xavier.robert***@***ird.fr>\n" % (str(datetime.datetime.now().year)))  # noqa: DTZ005, UP031
            file.write("# Ce travail est sous la License Creative Commons Attribution-ShareAlike-NonCommecial :\n")
            file.write("#	<http://creativecommons.org/licenses/by-nc-sa/4.0/>\n\n")
    elif thlang == "en":
        file.write("# Copyright (C) %s Xavier Robert <xavier.robert***@***ird.fr>\n" % (str(datetime.datetime.now().year)))  # noqa: DTZ005, UP031
        file.write("# This work is under the Creative Commons Attribution-ShareAlike-NonCommecial License:\n")
        file.write("#	<http://creativecommons.org/licenses/by-nc-sa/4.0/>\n\n")

    file.write('map MP-%s-plan-tot -title "%s"\n' % (cavename.replace(" ", "_"), cavename.replace(" ", "_")))  # noqa: UP031
    file.write("\tSP-%s-1\n" % (cavename.replace(" ", "_")))  # noqa: UP031
    file.write("\t#break\n")
    file.write("\t#SP-%s-2\n" % (cavename.replace(" ", "_")))  # noqa: UP031
    file.write("endmap\n")

    file.write('map MC-%s-coupe-tot -title "%s"\n' % (cavename.replace(" ", "_"), cavename.replace(" ", "_")))  # noqa: UP031
    file.write("\tSC-%s-1\n" % (cavename.replace(" ", "_")))  # noqa: UP031
    file.write("\t#break\n")
    file.write("\t#SC-%s-2\n" % (cavename.replace(" ", "_")))  # noqa: UP031
    file.write("endmap\n")

    return  # noqa: PLR1711


#################################################################################################
def write_thcoords(file, cavename="cave", coordinates=None, coordsyst=None, icomments=True, thlang="en"):
    """
    Function to write the file Legends/entrances_coordinates.th

    INPUTS:
            file         : variable that sets the file.th
            cavename     : name of the cave
            coordinates   : Coordinates of the Cave
            coordsyst    : Coordinates system and projection
            icomments    : True if comments in the file
                          False if not
            thlang      : 'fr' for french
                          'en' for english
                          ... other languages not implemented

    OUTPUTS:
            None

    USAGE:
            write_thcoords(file, cavename, coordinates, coordsyst, icomments, thlang)

    Author: Xavier Robert, Grenoble 2021/01/03

    """

    # Coordinates definition
    if coordinates:
        if coordsyst:
            # Transform Lambert coordinates into Lat Long coordinates
            inProj = Proj(coordsyst)
            outProj = Proj("epsg:4326")
            latc, longc = transform(inProj, outProj, float(coordinates[0]), float(coordinates[1]))
        else:
            latc = coordinates[1] + "(Check coord. syst.)"
            longc = coordinates[0] + "(Check coord. syst.)"
        altc = coordinates[2]
    else:
        latc = "None"
        longc = "None"
        altc = "None"

    file.write("encoding utf-8 \n\n")

    if icomments:
        if thlang == "fr":
            file.write("# Copyright (C) %s Xavier Robert <xavier.robert***@***ird.fr>\n" % (str(datetime.datetime.now().year)))  # noqa: DTZ005, UP031
            file.write("# Ce travail est sous la License Creative Commons Attribution-ShareAlike-NonCommecial :\n")
            file.write("#	<http://creativecommons.org/licenses/by-nc-sa/4.0/>\n\n")
    elif thlang == "en":
        file.write("# Copyright (C) %s Xavier Robert <xavier.robert***@***ird.fr>\n" % (str(datetime.datetime.now().year)))  # noqa: DTZ005, UP031
        file.write("# This work is under the Creative Commons Attribution-ShareAlike-NonCommecial License:\n")
        file.write("#	<http://creativecommons.org/licenses/by-nc-sa/4.0/>\n\n")

    file.write("layout Entrances_coords_%s\n\n" % (cavename.replace(" ", "_")))  # noqa: UP031

    if icomments:
        if thlang == "fr":
            file.write("\t# Layout qui définit les différentes variables contenant du texte avec \n")
            file.write("\t# les coordonnées de l'entrée que nous voulons ajouter au header.\n")
            file.write("\t# Nous avons besoin d'une variable par entrée.\n")
            file.write("\t# Ce layout est appelé par le layout Coords_Header ci-dessous\n\n")
        elif thlang == "en":
            file.write("\t# Layout where we define the different variables that contain the text with \n")
            file.write("\t# the entrance coordinates we want to print in the header.\n")
            file.write("\t# We need one variable per entrance.\n")
            file.write("\t# This layout is called by the layout Coords_Header below\n\n")

    file.write("\tcode tex-map\n")
    file.write("\t\t\\def\\thjunk{ }\n")
    file.write(
        "\t\t\\def\\thlocation%s{%s    --  Lat. : %s N ; Long. : %s E ; Alt. : %s m}\n"  # noqa: UP031
        % (cavename.replace(" ", "_"), cavename.replace(" ", "_"), str(latc), str(longc), str(altc))
    )
    # We probably need in the future to iterate on the number of entrances...
    # I do not know for the moment if Visual Top take in account different entrances coordinates
    file.write("\tendcode\n\n")

    file.write("\tendlayout\n\n")

    file.write("layout Coords_Header_%s\n\n" % (cavename.replace(" ", "_")))  # noqa: UP031
    if icomments:  # noqa: SIM102
        if thlang == "fr":
            file.write("\t# Layout that set the presentation for the entrance coordinates.\n\n")

    file.write("\tcopy Entrances_coords_%s\n\n" % (cavename.replace(" ", "_")))  # noqa: UP031
    if icomments:
        if thlang == "fr":
            file.write("\t# Appelle le layout ci-dessus Entrances_coords où nous avons défini les différentes \n")
            file.write("\t# variables qui contiennent le texte avec \n")
            file.write("\t# les coordonnées des entrées à écrire dans le header.\n\n")
        elif thlang == "en":
            file.write("\t# it calls the layout above Entrances_coords where we defined the different \n")
            file.write("\t# variables that contain the text with \n")
            file.write("\t# the entrance coordinates we want to print in the header.\n\n")

    file.write("\tcode tex-map\n")
    file.write("\t\t\\def\\nostring{}\n")
    file.write("\t\t\\def\\thsizexl{}\n")
    file.write("\t\t\\def\\thsizel{}\n")
    file.write("\t\t\\def\\thsizem{}\n")
    file.write("\t\t\\ifx\\thsizexl\\nostring\\def\\thsizexl{30}\\else\\fi\n")
    file.write("\t\t\\ifx\\thsizel\\nostring\\def\\thsizel{24}\\else\\fi\n")
    file.write("\t\t\\ifx\\thsizem\\nostring\\def\\thsizem{12}\\else\\fi\n\n")

    file.write("\t\t\\ECoordinates={\n")
    file.write("\t\t\t\\edef\\tmp{\\thjunk} \\ifx\\tmp\\empty \\else\n")
    file.write("\t\t\t\t{\\size[\\thsizem] \\ss\\thjunk\\vss}\n")
    file.write("\t\t\t\\fi\n")
    file.write("\t\t\t\\edef\\tmp{\\thlocation%s} \\ifx\\tmp\\empty \\else\n" % (cavename.replace(" ", "_")))  # noqa: UP031
    file.write("\t\t\t\t# The first one should be without hskip\n")
    file.write("\t\t\t\t{\\size[\\thsizem]\\hskip2cm \\ss\\thlocation%s\\vss}\n" % (cavename.replace(" ", "_")))  # noqa: UP031
    file.write("\t\t\t\\fi\n")
    file.write("\t\t\t}\n")
    file.write("\tendcode\n\n")

    file.write("\tendlayout\n\n")

    return  # noqa: PLR1711
