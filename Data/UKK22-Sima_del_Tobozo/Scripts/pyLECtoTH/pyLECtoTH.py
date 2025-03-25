import os
import re

def transform_lec_to_th_Old(content):
    """Transforme le contenu d'un fichier LEC en format TH."""
    lines = content.split("\n")
    transformed_lines = []
    station_id = None

    for line in lines:
        # Détecter une nouvelle station
        match_station = re.match(r"\s*STATION\s+(\d+)\s*:\s*([\d\s-]+)", line)
        if match_station:
            station_id = match_station.group(1)
            coords = match_station.group(2).strip()
            transformed_lines.append(f"0 {station_id} {coords}")
            continue

        # Détecter un point de profil (avec des coordonnées)
        match_point = re.match(r"\s*[\w\s-]+:\s*([\d\s-]+)", line)
        if match_point and station_id:
            coords = match_point.group(1).strip()
            transformed_lines.append(f"1 - {coords}")

    return "\n".join(transformed_lines)


def transform_lec_to_th(content, num):
     """
     Transforme le contenu d'un fichier .LEC au format désiré pour un fichier .th
     """
     lines = content.split("\n")
     output_lines = []
     current_station = None
     previous_station = None
     x, y, z = 0, 0, 0  # Coordonnées de la station
     x1, y1, z1 = 0, 0, 0  # Coordonnées de la station
     previous_x, previous_y, previous_z = 0, 0, 0  # Coordonnées de la station
     station = 0
     
     # print ("num : " + num)
    
     # Extraction du nombre de stations depuis la première ligne
     nbre_stations = int(lines[0].strip()) if lines[0].strip().isdigit() else None
     lines = lines[1:]  # Supprimer la première ligne de `lines`
     # print(f"nbre_stations : {nbre_stations}")
     output_lines.append("# ")
     output_lines.append(f"# Nbre de stations : {nbre_stations}")
              
     for line in lines:
          line = line.strip()

          # Détecter une nouvelle station
          match_station =   re.match(r"\s*STATION\s+(\d+)\s*:\s*([\d\s-]+)", line)
          match_station_S = re.match(r"\s*STATION (\d+)\s*S\s*:\s*([\d\s-]+)", line)
          match_point = re.match(r"(point .+)\s*:\s*([\d\s-]+)", line)
          
          
          if match_station:
               previous_station = current_station
               current_station = int(match_station.group(1))
               coords = list(map(int, match_station.group(2).split()))
               if len(coords) == 3:
                    x, y, z = coords  # Affectation des coordonnées
               
               # print(f"Station : {current_station} Coordonnées : {x-previous_x} {y-previous_y} {z-previous_z}, Previous {previous_station}")
               
               if previous_station is not None:
                    output_lines.append(f"{previous_station} {current_station} {round(((x-previous_x)/100), 2)} {round(((y-previous_y)/100), 2)} {round(((z-previous_z)/100), 2)}")
               else :
                    output_lines.append("# ")
                    output_lines.append(f"# 0 {current_station} {round(((x-previous_x)/100), 2)} {round(((y-previous_y)/100), 2)} {round(((z-previous_z)/100), 2)}")
               previous_x = x
               previous_y = y
               previous_z = z
               station += 1
               
          elif match_station_S :
               previous_station = current_station
               current_station = int(match_station_S.group(1))
               coords = list(map(int, match_station_S.group(2).split()))
               
               if len(coords) == 3:
                    x, y, z = coords  # Affectation des coordonnées
               
               # print(f"Station : {current_station} Coordonnées : {x-previous_x} {y-previous_y} {z-previous_z}, Previous {previous_station}")
               
               if previous_station is not None:
                    output_lines.append(f"{previous_station} {current_station} {round(((x-previous_x)/100), 2)} {round(((y-previous_y)/100), 2)} {round(((z-previous_z)/100), 2)} # S")
               else :
                    output_lines.append(f"# 0 {current_station} {round(((x-previous_x)/100), 2)} {round(((y-previous_y)/100), 2)} {round(((z-previous_z)/100), 2)} #S")
                    
               # print(f"match_station_S : {match_station_S}")
               previous_x = x
               previous_y = y
               previous_z = z
               station += 1

          elif match_point and current_station is not None:
               # print(f"Match-Point {match_point}")
               coords = list(map(int, match_point.group(2).split()))
               if len(coords) == 3:
                    x1, y1, z1 = coords  # Affectation des coordonnées
               output_lines.append(f"{current_station} - {round(((x1-x)/100), 2)} {round(((y1-y)/100), 2)} {round(((z1-z)/100), 2)}")
               
          elif line.startswith("******************************************"):
               if current_station is not None:
                    output_lines.append("#\n")
          elif line.startswith("********************"):
               None
          elif line.startswith("*******************"):
               None
          elif line.startswith("PROFIL STATION"):
               None
          elif ( line.startswith("Développement") or line.startswith("Galerie de raccord") or line.startswith("Station de raccord") ):
                output_lines.append(f"# {line}")
          elif line =="":
               None
          elif line =="":
               None
          elif line == num:
               None
          else :
               print(f"Line : {line}")
               
               
     if (station - nbre_stations) != 1 :
          print (f"Erreur : station {station}, nbre_station {nbre_stations}")
          output_lines.append(f"Erreur de conversion : station {station-1}, nbre station attendu : {nbre_stations}")
     else :
          output_lines.append(f"# Conversion OK : station {station - 1}" )
          
     return "\n".join(output_lines).strip()


# Définition des dossiers
input_folder = "./LEC"
output_folder = "./TH"

# Création du dossier de sortie s'il n'existe pas
os.makedirs(output_folder, exist_ok=True)

# Parcours des fichiers .LEC
for filename in os.listdir(input_folder):
    if filename.endswith(".LEC"):
        input_path = os.path.join(input_folder, filename)
        output_filename = "Tobozo_" + filename
        output_path = os.path.join(output_folder, output_filename.replace(".LEC", ".th"))

        # Lecture et conversion
        with open(input_path, "r", encoding="cp863") as infile:
            lec_content  = infile.read()

       # Transformation
        th_content = transform_lec_to_th(lec_content, os.path.splitext(filename)[0])
        th_entete = f"""
encoding  utf-8

# Copyright (C) ARSIP 2025
# This work is under the Creative Commons Attribution-NonCommercial-NoDerivatives License:
# <http://creativecommons.org/licenses/by-nc-nd/4.0/>

# Conversion d'après fichier {filename} de coordonnées cartésiens Lambert Martin / CRS par Alex 03/2025

survey Tobozo_{os.path.splitext(filename)[0]} -title "Sima del Tobozo (galerie {os.path.splitext(filename)[0]})"

centerline

     date 1987.08.01
     team "Lambert Martin"
     explo-date 1987
     explo-team "CRS"
     
        
     data cartesian from to easting northing altitude
     
     """
        
        th_pied = """
endcenterline

endsurvey
"""
        
        # Écriture en UTF-8
        with open(output_path, "w", encoding="utf-8") as outfile:
            outfile.write(th_entete) 
            outfile.write(th_content)
            outfile.write(th_pied) 

        print(f"Converti : {filename} -> {os.path.basename(output_path)}")

print("Conversion terminée.")
