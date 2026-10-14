#!/usr/bin/env python3
"""#####################################################################################################################################
#                                                        	                                                                           #
#                                                                                                                                      #
#####################################################################################################################################"""

import argparse, shutil, os, sys, subprocess, time, logging  # noqa: I001
import requests
from urllib.parse import quote
from pathlib import Path
from dotenv import load_dotenv
from alive_progress import alive_bar

from mergin import MerginClient
from mergin.client_pull import download_project_async, download_project_is_running, download_project_finalize
from mergin.client_push import push_project_async, push_project_is_running, push_project_finalize

from Lib.Librairies import setup_logger, Colors
from Lib import GlobalData

GITHUB_API = "https://api.github.com"


############################################################################################################################################
def suivre_transfert(job, verifier, titre: str) -> None:
    """Affiche la progression et le débit d'un transfert Mergin Maps."""

    taille_totale = job.total_size

    if taille_totale <= 0:
        while verifier(job):
            time.sleep(0.2)
        logger.info(f"{Colors.ENDC}{titre}{Colors.INFO} : transfert terminé.")
        return

    precedent = 0
    interactif = sys.stdout.isatty() and sys.stderr.isatty() and os.environ.get("TERM", "").lower() != "dumb"

    if interactif:
        with alive_bar(taille_totale, title=f"{Colors.YELLOW}{titre}{Colors.ENDC}", stats=True, dual_line=True, scale="SI", unit="o") as barre:
            while verifier(job):
                actuel = job.transferred_size
                delta = actuel - precedent

                if delta > 0:
                    barre(delta)
                    precedent = actuel

                time.sleep(0.2)

            # Comptabilise les derniers octets transférés.
            delta = job.transferred_size - precedent
            if delta > 0:
                barre(delta)
    else:
        logger.info(f"{Colors.ENDC}{titre}{Colors.INFO} : transfert démarré ({Colors.ENDC}{taille_totale}{Colors.INFO} octets).")

        while verifier(job):
            actuel = job.transferred_size
            delta = actuel - precedent

            if delta > 0:
                precedent = actuel
                logger.debug(
                    f"({Colors.ENDC}{titre}{Colors.DEBUG} : {Colors.ENDC}{actuel * 100 / taille_totale:.1f}{Colors.DEBUG} ({Colors.ENDC}{actuel}{Colors.DEBUG} / {Colors.ENDC}{taille_totale}{Colors.DEBUG} octets)"
                )

            time.sleep(0.2)

        logger.info(f"{Colors.ENDC}{titre}{Colors.INFO} : transfert terminé.")


############################################################################################################################################
def telecharger_avec_progression(client: MerginClient, projet: str, dossier: Path) -> None:
    """Télécharge un projet Mergin Maps avec suivi de progression."""

    job = download_project_async(client, projet, str(dossier))
    suivre_transfert(job, download_project_is_running, "Téléchargement")
    download_project_finalize(job)


############################################################################################################################################
def envoyer_avec_progression(client: MerginClient, dossier: Path) -> None:
    """Envoie les modifications vers Mergin Maps avec suivi."""

    job = push_project_async(client, str(dossier))
    if job is None:
        logger.warning("Aucune modification à envoyer.")
        return
    suivre_transfert(job, push_project_is_running, "Envoi vers Mergin")
    push_project_finalize(job)


############################################################################################################################################
def supprimer_dossier_temporaire(dossier: Path, tentatives: int = 5) -> bool:
    """Supprime un dossier temporaire en réessayant si un fichier est verrouillé."""

    for tentative in range(tentatives):
        try:
            shutil.rmtree(dossier)
            logger.info(f"Dossier temporaire supprimé : {Colors.ENDC}{dossier}")
            return True

        except PermissionError as erreur:
            if tentative == tentatives - 1:
                logger.warning(f"Suppression impossible, dossier conservé : {Colors.ENDC}{dossier}{Colors.WARNING},{Colors.ENDC}{erreur}")
                return False
            time.sleep(1)
    return False


############################################################################################################################################
def fermer_journaux_mergin() -> None:
    """Ferme les gestionnaires de fichiers de journalisation Mergin."""

    loggers = [logging.getLogger()]

    loggers.extend(logging.Logger.manager.loggerDict.values())

    for logger in loggers:
        if not isinstance(logger, logging.Logger):
            continue

        for handler in logger.handlers[:]:
            if isinstance(handler, logging.FileHandler):
                handler.flush()
                handler.close()
                logger.removeHandler(handler)


############################################################################################################################################
def _entetes_github(token: str | None, brut: bool = False) -> dict:
    accept = "application/vnd.github.raw+json" if brut else "application/vnd.github+json"
    entetes = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        entetes["Authorization"] = f"Bearer {token}"
    return entetes


############################################################################################################################################
def lister_fichiers_github(session: requests.Session, depot: str, branche: str, chemin: str, token: str | None) -> list[dict]:
    """Liste récursivement les fichiers d'un dossier GitHub (ou le fichier lui-même)."""

    url = f"{GITHUB_API}/repos/{depot}/contents/{quote(chemin)}"
    reponse = session.get(url, params={"ref": branche}, headers=_entetes_github(token), timeout=60)

    if reponse.status_code == 404:
        raise FileNotFoundError(f"Chemin introuvable (ou jeton manquant) : {depot}@{branche}:{chemin}")
    reponse.raise_for_status()
    contenu = reponse.json()

    if isinstance(contenu, dict):  # le chemin désigne un fichier
        return [contenu]

    fichiers = []
    for entree in contenu:
        if entree["type"] == "file":
            fichiers.append(entree)
        elif entree["type"] == "dir":
            fichiers.extend(lister_fichiers_github(session, depot, branche, entree["path"], token))
    return fichiers


############################################################################################################################################
def telecharger_depuis_github(depot: str, branche: str, chemin: str, dossier_cible: Path, token: str | None = None) -> Path:
    """Télécharge uniquement un fichier ou un dossier d'un dépôt GitHub.

    chemin : chemin dans le dépôt, ex. 'data/gpkg' ou 'data/couche.gpkg' ('' = tout le dépôt)
    Retourne le fichier ou le dossier local téléchargé.
    """

    chemin = chemin.strip("/")

    if dossier_cible.exists():
        shutil.rmtree(dossier_cible)
    dossier_cible.mkdir(parents=True)

    with requests.Session() as session:
        fichiers = lister_fichiers_github(session, depot, branche, chemin, token)
        if not fichiers:
            raise ValueError(f"Aucun fichier trouvé dans : {chemin or '/'}")

        # Un fichier demandé : destination à plat ; sinon, conserver l'arborescence.
        est_fichier = len(fichiers) == 1 and fichiers[0]["path"] == chemin
        base = chemin.rpartition("/")[0] if est_fichier else chemin
        total = sum(f.get("size", 0) for f in fichiers) or None

        interactif = sys.stdout.isatty() and sys.stderr.isatty() and os.environ.get("TERM", "").lower() != "dumb"
        precedent = 0

        def telecharger_fichiers(barre=None) -> None:
            nonlocal precedent

            for fichier in fichiers:
                relatif = fichier["path"][len(base) :].lstrip("/") if base else fichier["path"]
                local = dossier_cible / relatif
                local.parent.mkdir(parents=True, exist_ok=True)

                url = f"{GITHUB_API}/repos/{depot}/contents/{quote(fichier['path'])}"
                with session.get(url, params={"ref": branche}, headers=_entetes_github(token, brut=True), stream=True, timeout=120) as reponse:
                    reponse.raise_for_status()

                    with open(local, "wb") as sortie:
                        for morceau in reponse.iter_content(chunk_size=1024 * 256):
                            if not morceau:
                                continue

                            sortie.write(morceau)
                            precedent += len(morceau)

                            if barre:
                                barre(len(morceau))
                            else:
                                logger.debug(
                                    "GitHub : %s — %.1f %% (%s / %s octets)", fichier["path"], precedent * 100 / total if total else 0, precedent, total or "?"
                                )

        logger.info(
            f"Téléchargement GitHub : {Colors.ENDC}{depot}{Colors.INFO}/{Colors.ENDC}{branche}{Colors.INFO}, chemin {Colors.ENDC}{chemin or '/'}{Colors.INFO}"
        )

        if interactif and total:
            with alive_bar(total, title=f"{Colors.YELLOW}Téléchargement GitHub{Colors.ENDC}", stats=True, scale="SI", unit="o") as barre:
                telecharger_fichiers(barre)
        else:
            telecharger_fichiers()

        logger.info(f"Téléchargement GitHub terminé : {Colors.ENDC}{len(fichiers)}{Colors.INFO} fichier(s), {Colors.ENDC}{precedent}{Colors.INFO} octets.")

    return dossier_cible / Path(chemin).name if est_fichier else dossier_cible


############################################################################################################################################
def envoyer_mergin(
    projet: str,
    client: MerginClient,
    depot: str,
    chemin: str,
    branche: str = "main",
    token: str | None = None,
    destination: str = "",
    dossier_temporaire: Path = Path(__file__).parent / GlobalData.Temp_folder,
):
    """#####################################################################################################################################
        Télécharge un fichier ou un dossier depuis GitHub puis l'envoie vers Mergin Maps.

        Le dossier temporaire est conservé en cas d'erreur.
        La copie GitHub est supprimée après un succès complet.
    #####################################################################################################################################"""

    logger.info("═" * 95)
    logger.info(f"{Colors.YELLOW}Envoi des données GitHub vers Mergin Maps")
    logger.info("═" * 95)

    dossier_temporaire = Path(dossier_temporaire).resolve()
    destination = Path(destination)

    if destination.is_absolute() or ".." in destination.parts:
        raise ValueError("La destination doit être un chemin relatif.")

    if ".mergin" in destination.parts:
        raise ValueError("Le dossier .mergin est réservé à Mergin Maps.")

    dossier_temporaire.mkdir(parents=True, exist_ok=True)
    dossier_github = dossier_temporaire / "Github"
    dossier_projet = dossier_temporaire / "Projet"

    try:
        # 1. Téléchargement du fichier ou dossier nécessaire depuis GitHub.
        logger.info(f"[1/5]{Colors.YELLOW} Téléchargement desfichiers depuis le GitHub : {Colors.ENDC}{depot}@{branche}:{chemin}")
        source = telecharger_depuis_github(depot, branche, chemin, dossier_github, token)

        # 2. Projet Mergin local.
        if not (dossier_projet / ".mergin").is_dir():
            logger.info(f"[2/5]{Colors.YELLOW} Téléchargement initial du projet : {Colors.ENDC}{dossier_projet}")
            telecharger_avec_progression(client, projet, dossier_projet)

        else:
            logger.info(f"[2/5] {Colors.YELLOW}Synchronisation du projet local existant : {Colors.ENDC}{dossier_projet}")
            client.sync_project(str(dossier_projet))

        # 3. Copie des fichiers GitHub dans le projet Mergin.
        logger.info(f"[3/5]{Colors.YELLOW} Copie des fichiers {Colors.ENDC}{source}")
        cible = dossier_projet / destination
        cible.mkdir(parents=True, exist_ok=True)

        if source.is_file():
            fichiers = [(source, cible / source.name)]

        elif source.is_dir():
            fichiers = [
                (f, cible / f.relative_to(source))
                for f in source.rglob("*")
                if f.is_file() and ".mergin" not in f.relative_to(source).parts and "__pycache__" not in f.relative_to(source).parts
            ]

        else:
            raise ValueError(f"Source non prise en charge : {Colors.ENDC}{source}")

        if not fichiers:
            raise ValueError("Aucun fichier à envoyer.")

        for origine, destination_fichier in fichiers:
            destination_fichier.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origine, destination_fichier)
            logger.info(f"  + {Colors.ENDC}{destination_fichier.relative_to(dossier_projet)}")

        # 4. Push vers le serveur.
        logger.info(f"[4/5]{Colors.YELLOW} Push vers Mergin Maps...")
        envoyer_avec_progression(client, dossier_projet)

        # 5. Nettoyage de la copie GitHub uniquement après succès.
        logger.info(f"[5/5]{Colors.YELLOW} Push terminé. Nettoyage...")
        shutil.rmtree(dossier_github, ignore_errors=True)

        logger.info("Envoi terminé avec succès.")

    except Exception:
        logger.error("ERREUR : le dossier temporaire est conservé pour diagnostic :")
        logger.error(f"{Colors.ENDC}{dossier_temporaire}")
        raise


############################################################################################################################################
def envoyer_dossier_old_fichierslocaux(
    source: Path, projet: str, client: MerginClient, destination: str = "", dossier_temporaire: Path = Path(__file__).parent / GlobalData.Temp_folder
):
    """#####################################################################################################################################
        Envoie un fichier ou un dossier vers Mergin Maps.

        Le dossier temporaire est supprimé au début du traitement.
        Il est conservé en cas d'erreur et supprimé après un succès complet.                                                               #
    #                                                                                                                                      #
    #####################################################################################################################################"""

    logger.info("═" * 95)
    logger.info(f"{Colors.YELLOW}Envoie des donnée vers Mergin Maps")
    logger.info("═" * 95)

    source = Path(source).resolve()
    dossier_temporaire = Path(dossier_temporaire).resolve()
    destination = Path(destination)

    if not source.exists():
        raise FileNotFoundError(f"Source introuvable : {Colors.ENDC}{source}")

    if destination.is_absolute() or ".." in destination.parts:
        raise ValueError("La destination doit être un chemin relatif.")

    if ".mergin" in destination.parts:
        raise ValueError("Le dossier .mergin est réservé à Mergin Maps.")

    if dossier_temporaire == source or source in dossier_temporaire.parents:
        raise ValueError("Le dossier temporaire ne doit pas se trouver dans la source.")

    dossier_temporaire.mkdir(parents=True, exist_ok=True)
    dossier_temporaire = dossier_temporaire / "Projet"

    try:
        if not (dossier_temporaire / ".mergin").is_dir():
            logger.info(f"[1/4]{Colors.YELLOW} Téléchargement initial du projet : {Colors.ENDC}{dossier_temporaire}")
            telecharger_avec_progression(client, projet, dossier_temporaire)

        else:
            logger.info(f"[1/4] {Colors.YELLOW}Synchronisation du projet local existant : {Colors.ENDC}{dossier_temporaire}")
            client.sync_project(str(dossier_temporaire))

        # 2. Copier le fichier ou les fichiers source.
        logger.info(f"[2/4]{Colors.YELLOW} Copie des fichiers {Colors.ENDC}{source}")
        cible = dossier_temporaire / destination
        cible.mkdir(parents=True, exist_ok=True)

        if source.is_file():
            fichiers = [(source, cible / source.name)]

        elif source.is_dir():
            fichiers = [
                (f, cible / f.relative_to(source))
                for f in source.rglob("*")
                if f.is_file() and ".mergin" not in f.relative_to(source).parts and "__pycache__" not in f.relative_to(source).parts
            ]

        else:
            raise ValueError(f"Source non prise en charge : {Colors.ENDC}{source}")

        if not fichiers:
            raise ValueError("Aucun fichier à envoyer.")

        for origine, destination_fichier in fichiers:
            destination_fichier.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origine, destination_fichier)
            logger.info(f"  + {Colors.ENDC}{destination_fichier.relative_to(dossier_temporaire)}")

        # 3. Synchroniser avec le serveur.
        logger.info(f"[3/4]{Colors.YELLOW} Push vers Mergin Maps...")
        # client.sync_project(str(dossier_temporaire))
        envoyer_avec_progression(client, dossier_temporaire)

        # 4. Nettoyer uniquement après le succès.
        logger.info(f"[4/4]{Colors.YELLOW} Push terminé. Nettoyage...")
        # fermer_journaux_mergin()
        # supprimer_dossier_temporaire(dossier_temporaire)

        logger.info("Envoi terminé avec succès.")

    except Exception:
        logger.error("ERREUR : le dossier temporaire est conservé pour diagnostic :")
        logger.error(f"{Colors.ENDC}{dossier_temporaire}")
        raise


############################################################################################################################################
def information_depot_mergin(projet, client):
    """#####################################################################################################################################
    #   Affiche les informations d'un projet Mergin Maps.
            projet : nom complet du projet, sous la forme 'espace/nom_projet',
                 ou chemin du dossier local du projet.
            client : instance de MerginClient.                                                                                                                                #
    #                                                                                                                                      #
    #####################################################################################################################################"""

    logger.info("═" * 95)
    logger.info(f"{Colors.YELLOW}INFORMATIONS DU PROJET MERGIN MAPS")
    logger.info("═" * 95)

    # Récupération des informations distantes
    try:
        info = client.project_info(str(projet))

    except Exception as e:  # noqa: BLE001
        logger.error(f"Erreur lors de la récupération du projet : {Colors.ENDC}{e}")
        return

    logger.info(f"Projet           : {Colors.ENDC}{info.get('name', projet)}")
    logger.info(f"Identifiant      : {Colors.ENDC}{info.get('id', 'Non renseigné')}")
    logger.info(f"Version          : {Colors.ENDC}{info.get('version', 'Non renseignée')}")
    logger.info(f"Créé le          : {Colors.ENDC}{info.get('created', 'Non renseigné')}")
    logger.info(f"Mis à jour       : {Colors.ENDC}{info.get('updated', 'Non renseigné')}")
    logger.info(f"Taille totale    : {Colors.ENDC}{info.get('disk_usage', 'Non renseignée')}{Colors.INFO} Octets")
    logger.info(f"Public           : {Colors.ENDC}{info.get('public', 'Non renseigné')}")

    # Liste des fichiers distants
    fichiers = info.get("files", [])

    logger.info(f"Nbre de fichiers : {Colors.ENDC}{len(fichiers)}")

    tailleTotale = 0.0
    if fichiers:
        for fichier in fichiers:
            taille = fichier.get("size", 0)
            tailleTotale += taille
        logger.info(f"Taille totale    : {Colors.ENDC}{tailleTotale / (1024 * 1024):.2f}{Colors.INFO} Mo")
        logger.info("━" * 95)

        for fichier in sorted(fichiers, key=lambda f: f.get("path", "")):
            chemin = fichier.get("path", "?")
            taille = fichier.get("size", 0)
            taille_mo = taille / (1024 * 1024)

            logger.info(f"{Colors.ENDC}{chemin:<83} {Colors.CYAN}{taille_mo:>8.3f}{Colors.INFO} Mo")
    else:
        logger.warning("Aucun fichier répertorié dans les informations reçues.")

    logger.info("━" * 95)


############################################################################################################################################
#                                                         Main fonction                                                                    #
#                                                                                                                                          #
############################################################################################################################################
if __name__ == "__main__":
    if os.name == "nt":
        subprocess.run("cls", shell=True, check=False)
    elif os.environ.get("TERM"):
        subprocess.run(["clear"], check=False)

    INTERACTIF = sys.stdout.isatty() and sys.stderr.isatty() and os.environ.get("TERM", "").lower() != "dumb"
    print(f"stdout={sys.stdout.isatty()}, stderr={sys.stderr.isatty()}, TERM={os.environ.get('TERM')!r}, interactif={INTERACTIF}", file=sys.stderr)

    parser = argparse.ArgumentParser(description="Envoi de fichiers vers Mergin Maps")
    # parser.add_argument("--source", required=True, help="Dossier contenant les fichiers à envoyer")
    # parser.add_argument("--projet-local", required=True, help="Dossier local du projet Mergin Maps")
    args = parser.parse_args()

    logger = setup_logger(GlobalData.Output_log, GlobalData.Debug_log)

    titre = [
        f"{Colors.TITRE}╔{'═' * 99}",
        "║" + ("Synchronisation des fichiers gpkg vers Mergin Maps").center(99),
        "║" + (f"Par : {Colors.TITRE_2}alexandre.pont@yahoo.fr{Colors.TITRE}").center(119),
        "║" + (f"Version : {Colors.TITRE_2}{GlobalData.Version}{Colors.TITRE}").center(119),
        "║" + (f"Serveur MerginMaps : {Colors.TITRE_2}{GlobalData.Mergin_url}{Colors.TITRE}").center(119),
        "║" + (f"Projet MerginMaps : {Colors.TITRE_2}{GlobalData.Dest_project}{Colors.TITRE}").center(119),
        "║" + (f"Dossier source : {Colors.TITRE_2}{GlobalData.Inputs_folder}{Colors.TITRE}").center(119),
        "║" + (f"Fichier log : {Colors.TITRE_2}{GlobalData.Output_log}{Colors.TITRE}").center(119),
        "║                                      ",
        f"╚{'═' * 99}",
    ]

    for i in range(10):
        fin = "╗" if i == 0 else "╝" if i == 9 else "║"
        print(f"{Colors.TITRE}" + titre[i].ljust(100) + f"{fin}{Colors.ENDC}")

    fichier_env = Path(__file__).resolve().parent / ".env"
    load_dotenv(fichier_env)

    login = os.getenv("MERGIN_USERNAME")
    password = os.getenv("MERGIN_PASSWORD")

    if not login or not password:
        sys.exit("Définir MERGIN_USERNAME et MERGIN_PASSWORD.")

    client = MerginClient(url=GlobalData.Mergin_url, login=login, password=password)

    information_depot_mergin(GlobalData.Dest_project, client)

    envoyer_mergin(
        GlobalData.Dest_project,
        client,
        depot=GlobalData.Github_repo,
        chemin=GlobalData.Github_path,  # ex. "data/gpkg" ou "data/couche.gpkg"
        branche=GlobalData.Github_branch,
        # token=os.environ.get("GITHUB_TOKEN"),
        destination=GlobalData.Dest_folder,
    )

    # envoyer_dossier(GlobalData.Inputs_folder, GlobalData.Dest_project, client, destination=GlobalData.Dest_folder)

    information_depot_mergin(GlobalData.Dest_project, client)
