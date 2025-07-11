"""
#############################################################################################
global_data.py for pyCreateTh.py                                                           
#############################################################################################
"""


#################################################################################################

error_count = 0                # Compteur d'erreurs

## [Survey_Data]  default values
Author = "Created by pyCreateTh.py"
Copyright = "# global_data.Copyright (C) pyCreateTh.py"
CopyrightShort = "Licence (C) pyCreateTh.py"
mapComment = "Created by pyCreateTh.py"
cs = "UTM30"
club = "Therion"
thanksto = "Therion"
datat = "https://therion.speleo.sk/"
wpage = "https://therion.speleo.sk/"

## [Application_data] default values
templatePath = "./Template"
stationByScrap = 20
finalTherion_exe = True
therionPath = "C:/Therion/therion.exe"
SurveyPrefixName = f"Survey_"
linesInTh2 = True
stationNamesInTh2 = True
wallLineInTh2 = True
kSmooth = 0.5
XVIScale = 100

#################################################################################################
totfile = """\t## Survey file:
\tinput Data/{TH_NAME}.th
            
\t## Plan file:
\t{ERR}{Plan}input Data/{TH_NAME}-Plan.th2
            
\t## Extended file:
\t{ERR}{Extended}input Data/{TH_NAME}-Extended.th2
            
\t## Maps file:
\t{ERR}{Maps}input {TH_NAME}-maps.th
"""


#################################################################################################
thFileDat = """
encoding utf-8
# File generated by pyCreateTh.py version: {VERSION} date: {DATE}

survey {SURVEY_NAME} -title "{SURVEY_TITLE}"
\t# {COMMENT}
\tcenterline
\t\tdate {SURVEY_DATE}
\t\t# team "{SURVEY_TEAM}"
{FIX_POINTS}

\t\texplo-date {EXPLO_DATE}
\t\t# explo-team "{EXPLO_TEAM}"
{CORRECTIONS}{DECLINATION}
\t\tunits {LENGTH}
\t\tunits {COMPASS}
\t\tunits {CLINO}
\t\t{DATA_FORMAT} 

\t#{DATA}

\tendcenterline
endsurvey

{SOURCE}
"""


#################################################################################################
thconfigTemplate = """
source "{th_file}"
layout minimal
scale 1 {XVIscale}
endlayout

select {selector}

#export model -o "{th_name}.lox"
export map -projection plan -o "{th_name}-Plan.xvi" -layout minimal -layout-debug station-names
export map -projection extended -o "{th_name}-Extended.xvi" -layout minimal -layout-debug station-names
"""


#################################################################################################
th2FileHeader = """encoding  utf-8"""

th2File = """
##XTHERION## xth_me_area_adjust {X_Min} {Y_Min} {X_Max} {Y_Max}
##XTHERION## xth_me_area_zoom_to 25
##XTHERION## xth_me_image_insert {insert_XVI} 

{Copyright}
# File generated by pyCreateTh.py version {version} date: {date}

# x_min: {X_Min}, x_max: {X_Max} ecart : {X_Max_X_Min}
# y_min: {Y_Min}, y_max: {Y_Max} ecart : {Y_Max_Y_Min}

scrap S{projection_short}-{name}_01 -station-names "" "@{name}" -projection {projection} -author {year} "{author}" -copyright {year} "{Copyright_Short}"
    
{names}    
{lines}
{walls}

{points}
    
endscrap
"""

th2Point = """\tpoint {x} {y} station -name {station}"""
th2Name  = """\tpoint {x} {y} station-name -align tr -scale xs -text {station}"""

th2Line  = """
line u:Shot_Survey
\t{x1} {y1}
\t{x2} {y2}     
endline
"""

th2wall = """{list}"""

th2Scrap = """
                        
scrap S{projection_short}-{name}_{num:02} -station-names "" "@{name}" -projection {projection} -author {year} "{author}" -copyright {year} "{Copyright_Short}" 
    
endscrap
"""


#################################################################################################
datumToEPSG = {
     # Datums globaux
     "wgs84": "326",   # UTM Nord (WGS84) - EPSG:326XX
     "etrs89": "258",   # UTM Nord (ETRS89) - Europe
     
     # Datums européens
     "european1950": "230",  # ED50 / UTM Nord - Europe
     "ed50": "230",
     
     # Datums nord-américains
     "nad27": "267",    # UTM Nord (NAD27) - Amérique du Nord
     "northamericandatum1927": "267",
     "northamerican1927": "267",
     "nad83": "269",    # UTM Nord (NAD83) - Amérique du Nord
     "northamericandatum1983": "269",
     "northamerican1983" : "269",
     
     # Datums français
     "ntf": "275",      # UTM Nord (NTF) - France (Paris)
     "nouvelletriangulationfrançaise": "275",
     
     # Datums africains
     "clarke1880": "297",  # UTM Nord (Clarke 1880) - Afrique
     
     # Datums australiens
     "agd66": "202",    # UTM Nord (AGD66) - Australie
     "australiangeodeticdatum1966": "202",
     "australiangeodetic1966": "202",
     "agd84": "203",    # UTM Nord (AGD84) - Australie
     "australiangeodeticdatum1984": "203",
     "australiangeodetic1984": "203",
     "gda94": "283",    # UTM Nord (GDA94) - Australie
     "geocentricdatumofaustralia1994": "283",
     "geocentricofaustralia1994": "283",
     
     # Datums asiatiques
     "pulkovo1942": "284",  # UTM Nord (Pulkovo 1942) - Russie/CEI
     "beijing1954": "214",  # UTM Nord (Beijing 1954) - Chine
     
     # Datums sud-américains
     "sad69": "291",    # UTM Nord (SAD69) - Amérique du Sud
     "southamericandatum1969": "291",
     "southamerican1969": "291",
     "sirgas2000": "319",  # UTM Nord (SIRGAS 2000) - Amérique Latine
}
    