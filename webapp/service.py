"""
service.py — Le pipeline d'automatisation, exécuté à la demande depuis le web

Même enchaînement que scheduler.PipelineScheduler au démarrage :

  Cas 1 (stock) --> si ruptures > 0     : Cas 3 (email d'alerte)
                --> si ruptures >= seuil : Cas 6 (formulaire d'urgence)
  puis les jobs indépendants : Cas 2 (rapport hebdo), Cas 5 (scraping),
  et Cas 4 : la planification qu'appliquerait le mode TEST ou PRODUCTION.

Différences avec la ligne de commande, propres à un service public :
  - rien n'est écrit sur le disque : chaque fichier généré reste en mémoire
    une heure (CACHE_EXECUTIONS) et se télécharge depuis l'interface ;
  - l'email d'alerte est construit (même message, même pièce jointe) mais
    pas envoyé : il se télécharge en .eml ;
  - Cas 5 et 6 passent par de simples requêtes HTTP (webapp/navigateur.py).

Chaque étape émet des événements (dict) consommés par l'API en flux NDJSON.
"""

from __future__ import annotations

import importlib.util
import io
import json
import logging
import re
import secrets
import sys
import threading
import time
import unicodedata
import zipfile
from collections import OrderedDict, deque
from email.utils import formataddr
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Callable, Optional

import pandas as pd
import schedule

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import config  # noqa: E402  (config.py à la racine)

from webapp import navigateur  # noqa: E402

logger = logging.getLogger(__name__)

Emetteur = Callable[[dict], None]


def _charger_script(nom: str) -> ModuleType:
    """Charge un module de scripts/ par chemin absolu (même méthode que scheduler.py)."""
    if nom in sys.modules:
        return sys.modules[nom]
    chemin = RACINE / "scripts" / f"{nom}.py"
    spec = importlib.util.spec_from_file_location(nom, chemin)
    if spec is None or spec.loader is None:
        raise ImportError(f"Impossible de charger le script : {chemin}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[nom] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


cas1_stock  = _charger_script("cas1_stock")
cas2_fusion = _charger_script("cas2_fusion")
cas3_email  = _charger_script("cas3_email")

# ============================================================
# PARAMÈTRES
# ============================================================

INVENTAIRES = OrderedDict([
    ("gaming_multimedia", {
        "titre": "Gaming & multimédia",
        "domaine": "Manettes, casques, streaming, écrans",
        "categorie_scraping": "Téléphones tactiles",
    }),
    ("consommables_bureau", {
        "titre": "Consommables de bureau",
        "domaine": "Câbles, piles, papeterie, petit matériel",
        "categorie_scraping": "Tablettes",
    }),
    ("stockage_securite", {
        "titre": "Stockage & sécurité",
        "domaine": "SSD, NAS, licences, sauvegarde",
        "categorie_scraping": "Ordinateurs",
    }),
])

MAX_PRODUITS          = 300
LONGUEUR_MAX_TEXTE    = 120
QUANTITE_MAX          = 1_000_000
SEUIL_FORMULAIRE_MAX  = 50
TAILLE_MAX_FICHIER    = 2 * 1024 * 1024
MAX_FICHIERS_PROD     = 7
MAX_LIGNES_PROD       = 500
EXECUTIONS_SIMULTANEES = 3
ATTENTE_MAX_PLACE     = 30          # secondes
DUREE_CACHE           = 3600        # secondes : fichiers téléchargeables pendant 1 h
MAX_EXECUTIONS_CACHE  = 40
DUREE_CACHE_SCRAPING  = 600         # secondes : on ne sollicite pas le site à chaque visite

EXPEDITEUR_DEMO   = "alertes-stock@example.com"
DESTINATAIRE_DEMO = "responsable.logistique@example.com"

# Envoi réel de l'alerte (Cas 3) : un compte Gmail dédié à la démo envoie, ses
# identifiants viennent des secrets de l'hébergeur (EMAIL_EXPEDITEUR, MOT_DE_PASSE_APP).
# Le visiteur choisit le destinataire ; son adresse d'expéditeur va en « Répondre à ».
NOM_EXPEDITEUR_DEMO = "Relais · alertes stock"
VALEURS_MODELE = {"votre.adresse@gmail.com", "xxxx xxxx xxxx xxxx", ""}
RE_EMAIL = re.compile(r"[^@\s<>()\[\]\\,;:\"']+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
LONGUEUR_MAX_EMAIL = 254
ENVOIS_PAR_VISITEUR_HEURE = 3
ENVOIS_PAR_DESTINATAIRE_JOUR = 2
ENVOIS_PAR_JOUR = 50

FICHIER_SECOURS_SCRAPING = Path(__file__).resolve().parent / "donnees" / "scraping_secours.json"

MESSAGE_ERREUR_INATTENDUE = "Une erreur inattendue a interrompu le pipeline. Réessayez dans un instant."
MESSAGE_OCCUPE = "Le serveur exécute déjà plusieurs pipelines. Réessayez dans quelques secondes."

ETAPES = [
    ("cas1", 1, "Détection des ruptures"),
    ("cas3", 3, "Alerte email"),
    ("cas6", 6, "Formulaire d'urgence"),
    ("cas2", 2, "Rapport hebdomadaire"),
    ("cas5", 5, "Scraping des prix"),
    ("cas4", 4, "Planification"),
]

JOURS_SEMAINE = {
    "monday": "lundi", "tuesday": "mardi", "wednesday": "mercredi", "thursday": "jeudi",
    "friday": "vendredi", "saturday": "samedi", "sunday": "dimanche",
}


class ErreurValidation(Exception):
    """Données envoyées invalides : `erreurs` = {champ: message}."""

    def __init__(self, erreurs: dict):
        super().__init__("; ".join(erreurs.values()))
        self.erreurs = erreurs


# ============================================================
# CACHE DES EXÉCUTIONS (fichiers générés, en mémoire)
# ============================================================

@dataclass
class Fichier:
    nom: str
    contenu: bytes
    media: str
    cas: int
    libelle: str


@dataclass
class Execution:
    identifiant: str
    nom_archive: str
    fichiers: "OrderedDict[str, Fichier]" = field(default_factory=OrderedDict)
    creee: float = field(default_factory=time.monotonic)

    def archive(self) -> bytes:
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in self.fichiers.values():
                zf.writestr(f.nom, f.contenu)
        return tampon.getvalue()


class CacheExecutions:
    def __init__(self, duree: float = DUREE_CACHE, maximum: int = MAX_EXECUTIONS_CACHE):
        self._duree = duree
        self._maximum = maximum
        self._entrees: "OrderedDict[str, Execution]" = OrderedDict()
        self._verrou = threading.Lock()

    def _purger(self) -> None:
        limite = time.monotonic() - self._duree
        for cle in [c for c, e in self._entrees.items() if e.creee < limite]:
            del self._entrees[cle]
        while len(self._entrees) > self._maximum:
            self._entrees.popitem(last=False)

    def ajouter(self, execution: Execution) -> None:
        with self._verrou:
            self._entrees[execution.identifiant] = execution
            self._purger()

    def obtenir(self, identifiant: str) -> Optional[Execution]:
        with self._verrou:
            self._purger()
            return self._entrees.get(identifiant)


CACHE_EXECUTIONS = CacheExecutions()
_PLACES = threading.BoundedSemaphore(EXECUTIONS_SIMULTANEES)


# ============================================================
# ENVOI RÉEL DE L'EMAIL : configuration et limites anti-abus
# ============================================================

def envoi_email_actif() -> bool:
    """Vrai si un vrai compte d'envoi est configuré (pas les valeurs du modèle .env.example)."""
    compte = (config.EMAIL_EXPEDITEUR or "").strip()
    mot_de_passe = (config.MOT_DE_PASSE_APP or "").strip()
    return compte not in VALEURS_MODELE and "@" in compte and mot_de_passe not in VALEURS_MODELE


def email_valide(adresse: str) -> bool:
    return len(adresse) <= LONGUEUR_MAX_EMAIL and bool(RE_EMAIL.fullmatch(adresse))


class LimiteurEnvois:
    """
    Fenêtres glissantes en mémoire : par visiteur (heure), par destinataire (jour)
    et au total (jour). Une seule instance de serveur : c'est suffisant.
    """

    MESSAGES = {
        "visiteur": "limite de {max} envois par heure atteinte, réessayez dans {attente} min",
        "destinataire": "cette adresse a déjà reçu {max} alertes aujourd'hui",
        "total": "limite quotidienne d'envois de la démo atteinte, réessayez demain",
    }

    def __init__(self, par_visiteur: int = ENVOIS_PAR_VISITEUR_HEURE,
                 par_destinataire: int = ENVOIS_PAR_DESTINATAIRE_JOUR, total: int = ENVOIS_PAR_JOUR):
        self.regles = {"visiteur": (par_visiteur, 3600), "destinataire": (par_destinataire, 86400),
                       "total": (total, 86400)}
        self._historique: dict = {}
        self._verrou = threading.Lock()

    def _file(self, cle: tuple, maintenant: float, duree: float) -> deque:
        file = self._historique.setdefault(cle, deque())
        while file and maintenant - file[0] > duree:
            file.popleft()
        return file

    def reserver(self, visiteur: str, destinataire: str) -> Optional[str]:
        """Enregistre l'envoi et renvoie None, ou renvoie la raison du refus."""
        maintenant = time.monotonic()
        cles = {"visiteur": ("visiteur", visiteur), "destinataire": ("destinataire", destinataire.lower()),
                "total": ("total",)}
        with self._verrou:
            for nom, cle in cles.items():
                maximum, duree = self.regles[nom]
                file = self._file(cle, maintenant, duree)
                if len(file) >= maximum:
                    attente = max(1, round((duree - (maintenant - file[0])) / 60))
                    return self.MESSAGES[nom].format(max=maximum, attente=attente)
            for cle in cles.values():
                self._historique[cle].append(maintenant)
        return None


LIMITEUR_ENVOIS = LimiteurEnvois()


# ============================================================
# INVENTAIRES ET PRODUCTION D'EXEMPLE
# ============================================================

def chemin_inventaire(cle: str) -> Path:
    return config.DATA_DIR / f"inventaire_{cle}.xlsx"


def _lignes_inventaire(df: pd.DataFrame) -> list:
    return [
        {"produit": str(r.Produit), "quantite": int(r.Quantite), "seuil": int(r.Seuil_Minimum)}
        for r in df.itertuples(index=False)
    ]


@lru_cache(maxsize=None)
def _inventaire_exemple(cle: str) -> tuple:
    df = pd.read_excel(chemin_inventaire(cle))
    return tuple(_lignes_inventaire(df))


def lister_inventaires() -> list:
    resultat = []
    for cle, meta in INVENTAIRES.items():
        if not chemin_inventaire(cle).is_file():
            continue
        lignes = _inventaire_exemple(cle)
        resultat.append({
            "cle": cle,
            "fichier": chemin_inventaire(cle).name,
            "titre": meta["titre"],
            "domaine": meta["domaine"],
            "categorie_scraping": meta["categorie_scraping"],
            "produits": len(lignes),
            "ruptures": sum(1 for l in lignes if l["quantite"] <= l["seuil"]),
        })
    return resultat


def lire_inventaire(cle: str) -> Optional[dict]:
    if cle not in INVENTAIRES or not chemin_inventaire(cle).is_file():
        return None
    return {
        "cle": cle,
        "fichier": chemin_inventaire(cle).name,
        "titre": INVENTAIRES[cle]["titre"],
        "lignes": list(_inventaire_exemple(cle)),
        "production": [p["jour"] for p in _production_exemple(cle)],
    }


@lru_cache(maxsize=None)
def _production_exemple_cache(cle: str) -> tuple:
    dossier = config.PRODUCTION_DIR / cle
    journees = []
    for f in sorted(dossier.glob("*.csv"), key=lambda f: cas2_fusion.ordre_jour(f.stem)):
        df = pd.read_csv(f)
        journees.append({"jour": f.stem.capitalize(), "lignes": [
            {"produit": str(r.Produit), "quantite": int(r.Quantite_Produite), "ligne": str(r.Ligne_Production)}
            for r in df.itertuples(index=False)
        ]})
    return tuple(journees)


def _production_exemple(cle: str) -> list:
    return list(_production_exemple_cache(cle))


def archive_production_exemple(cle: str) -> Optional[bytes]:
    dossier = config.PRODUCTION_DIR / cle
    if cle not in INVENTAIRES or not dossier.is_dir():
        return None
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(dossier.glob("*.csv"), key=lambda f: cas2_fusion.ordre_jour(f.stem)):
            zf.write(f, arcname=f"production_{cle}/{f.name}")
    return tampon.getvalue()


# ============================================================
# IMPORT DE FICHIERS (inventaire .xlsx/.csv, production .csv)
# ============================================================

def _normaliser(nom: str) -> str:
    sans_accents = unicodedata.normalize("NFKD", str(nom)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", sans_accents.lower()).strip("_")


COLONNES_INVENTAIRE = {
    "produit": "Produit", "nom": "Produit", "article": "Produit",
    "quantite": "Quantite", "stock": "Quantite", "qte": "Quantite",
    "seuil_minimum": "Seuil_Minimum", "seuil": "Seuil_Minimum", "seuil_min": "Seuil_Minimum",
}
COLONNES_PRODUCTION = {
    "produit": "Produit",
    "quantite_produite": "Quantite_Produite", "quantite": "Quantite_Produite",
    "ligne_production": "Ligne_Production", "ligne": "Ligne_Production",
}


def _lire_tableau(nom: str, contenu: bytes, nrows: int) -> pd.DataFrame:
    extension = Path(nom).suffix.lower()
    if extension == ".xlsx":
        return pd.read_excel(io.BytesIO(contenu), nrows=nrows)
    if extension == ".csv":
        texte = contenu.decode("utf-8-sig", errors="replace")
        separateur = ";" if texte.split("\n", 1)[0].count(";") > texte.split("\n", 1)[0].count(",") else ","
        return pd.read_csv(io.StringIO(texte), sep=separateur, nrows=nrows)
    raise ErreurValidation({"fichier": f"« {nom} » : formats acceptés .xlsx et .csv."})


def _renommer(df: pd.DataFrame, correspondances: dict, attendues: list, nom: str) -> pd.DataFrame:
    renommees = {}
    for colonne in df.columns:
        canonique = correspondances.get(_normaliser(colonne))
        if canonique and canonique not in renommees.values():
            renommees[colonne] = canonique
    df = df.rename(columns=renommees)
    manquantes = [c for c in attendues if c not in df.columns]
    if manquantes:
        raise ErreurValidation({"fichier": f"« {nom} » : colonne(s) manquante(s) : {', '.join(manquantes)}."})
    return df[attendues].dropna(how="all")


def _entier(valeur, contexte: str, minimum: int = 0) -> int:
    try:
        nombre = float(str(valeur).replace(",", ".").replace(" ", "").replace(" ", ""))
    except ValueError:
        raise ErreurValidation({"fichier": f"{contexte} : « {valeur} » n'est pas un nombre."})
    if nombre != nombre or not nombre.is_integer():  # NaN ou décimal
        raise ErreurValidation({"fichier": f"{contexte} : un nombre entier est attendu."})
    if not minimum <= nombre <= QUANTITE_MAX:
        raise ErreurValidation({"fichier": f"{contexte} : valeur hors limites ({minimum} à {QUANTITE_MAX})."})
    return int(nombre)


def _texte_court(valeur, contexte: str) -> str:
    texte = " ".join(str(valeur if valeur == valeur else "").split())  # NaN → ""
    if not texte:
        raise ErreurValidation({"fichier": f"{contexte} : nom de produit vide."})
    return texte[:LONGUEUR_MAX_TEXTE]


def importer_inventaire(nom: str, contenu: bytes) -> list:
    if len(contenu) > TAILLE_MAX_FICHIER:
        raise ErreurValidation({"fichier": f"« {nom} » dépasse 2 Mo."})
    try:
        df = _lire_tableau(nom, contenu, MAX_PRODUITS + 1)
    except ErreurValidation:
        raise
    except Exception:
        raise ErreurValidation({"fichier": f"« {nom} » est illisible. Vérifiez qu'il s'agit d'un vrai fichier .xlsx ou .csv."})
    df = _renommer(df, COLONNES_INVENTAIRE, ["Produit", "Quantite", "Seuil_Minimum"], nom)
    if df.empty:
        raise ErreurValidation({"fichier": f"« {nom} » ne contient aucun produit."})
    if len(df) > MAX_PRODUITS:
        raise ErreurValidation({"fichier": f"{MAX_PRODUITS} produits maximum par inventaire."})
    lignes = []
    for i, r in enumerate(df.itertuples(index=False), start=2):
        contexte = f"Ligne {i}"
        lignes.append({
            "produit": _texte_court(r.Produit, contexte),
            "quantite": _entier(r.Quantite, f"{contexte}, Quantite"),
            "seuil": _entier(r.Seuil_Minimum, f"{contexte}, Seuil_Minimum"),
        })
    return lignes


def importer_production(fichiers: list) -> list:
    """fichiers : [(nom, contenu)] — un CSV par jour, nommé d'après le jour (Lundi.csv…)."""
    if len(fichiers) > MAX_FICHIERS_PROD:
        raise ErreurValidation({"production": f"{MAX_FICHIERS_PROD} fichiers de production maximum (un par jour)."})
    journees = []
    for nom, contenu in fichiers:
        if Path(nom).suffix.lower() != ".csv":
            raise ErreurValidation({"production": f"« {nom} » : les fichiers de production sont des .csv."})
        if len(contenu) > TAILLE_MAX_FICHIER:
            raise ErreurValidation({"production": f"« {nom} » dépasse 2 Mo."})
        try:
            df = _lire_tableau(nom, contenu, MAX_LIGNES_PROD + 1)
            df = _renommer(df, COLONNES_PRODUCTION, ["Produit", "Quantite_Produite", "Ligne_Production"], nom)
            if len(df) > MAX_LIGNES_PROD:
                raise ErreurValidation({"fichier": f"« {nom} » : {MAX_LIGNES_PROD} lignes maximum."})
            lignes = [{
                "produit": _texte_court(r.Produit, f"« {nom} », ligne {i}"),
                "quantite": _entier(r.Quantite_Produite, f"« {nom} », ligne {i}"),
                "ligne": str(r.Ligne_Production)[:LONGUEUR_MAX_TEXTE],
            } for i, r in enumerate(df.itertuples(index=False), start=2)]
        except ErreurValidation as e:
            raise ErreurValidation({"production": next(iter(e.erreurs.values()))})
        except Exception:
            raise ErreurValidation({"production": f"« {nom} » est illisible."})
        journees.append({"jour": Path(nom).stem.capitalize()[:LONGUEUR_MAX_TEXTE], "lignes": lignes})
    journees.sort(key=lambda j: cas2_fusion.ordre_jour(j["jour"]))
    return journees


# ============================================================
# REQUÊTE DE PIPELINE (JSON envoyé par l'interface)
# ============================================================

@dataclass
class Requete:
    nom_inventaire: str
    cle_exemple: Optional[str]
    lignes: list
    production: Optional[list]
    mode: str
    seuil_formulaire: int
    rapport: bool
    scraping: bool
    destinataire: Optional[str] = None   # envoi réel de l'alerte (Cas 3)
    expediteur: Optional[str] = None     # placé en « Répondre à »


def _entier_requete(valeur, champ: str, minimum: int, maximum: int, erreurs: dict, message: str) -> int:
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)) or not float(valeur).is_integer() \
            or not minimum <= valeur <= maximum:
        erreurs.setdefault(champ, message)
        return minimum
    return int(valeur)


def valider_requete(donnees) -> Requete:
    if not isinstance(donnees, dict):
        raise ErreurValidation({"requete": "La requête doit être un objet JSON."})
    erreurs: dict = {}

    source = donnees.get("source")
    cle = donnees.get("inventaire") if source == "exemple" else None
    if source not in ("exemple", "import"):
        erreurs["source"] = "Choisissez un inventaire d'exemple ou importez le vôtre."
    elif source == "exemple" and cle not in INVENTAIRES:
        erreurs["inventaire"] = "Inventaire d'exemple inconnu."

    nom = donnees.get("nom") if source == "import" else (chemin_inventaire(cle).name if cle in INVENTAIRES else "")
    if not isinstance(nom, str) or not nom.strip():
        nom = "inventaire_importe.xlsx"
    nom = Path(nom.replace("\\", "/")).name[:LONGUEUR_MAX_TEXTE]

    lignes = []
    brutes = donnees.get("lignes")
    if not isinstance(brutes, list) or not brutes:
        erreurs["lignes"] = "L'inventaire ne contient aucun produit."
    elif len(brutes) > MAX_PRODUITS:
        erreurs["lignes"] = f"{MAX_PRODUITS} produits maximum."
    else:
        for i, ligne in enumerate(brutes, start=1):
            if not isinstance(ligne, dict) or not isinstance(ligne.get("produit"), str) or not ligne["produit"].strip():
                erreurs["lignes"] = f"Produit n° {i} : nom manquant."
                break
            message = f"Produit n° {i} : quantité et seuil sont des entiers de 0 à {QUANTITE_MAX}."
            lignes.append({
                "produit": " ".join(ligne["produit"].split())[:LONGUEUR_MAX_TEXTE],
                "quantite": _entier_requete(ligne.get("quantite"), "lignes", 0, QUANTITE_MAX, erreurs, message),
                "seuil": _entier_requete(ligne.get("seuil"), "lignes", 0, QUANTITE_MAX, erreurs, message),
            })

    production = None
    if source == "import" and donnees.get("production"):
        production = donnees["production"]
        valide = (isinstance(production, list) and len(production) <= MAX_FICHIERS_PROD and all(
            isinstance(j, dict) and isinstance(j.get("jour"), str) and isinstance(j.get("lignes"), list)
            and len(j["lignes"]) <= MAX_LIGNES_PROD and all(
                isinstance(l, dict) and isinstance(l.get("produit"), str)
                and isinstance(l.get("quantite"), int) and not isinstance(l.get("quantite"), bool)
                and 0 <= l["quantite"] <= QUANTITE_MAX
                for l in j["lignes"])
            for j in production))
        if not valide:
            erreurs["production"] = "Les données de production envoyées sont invalides."
            production = None

    mode = donnees.get("mode")
    if mode not in ("TEST", "PROD"):
        erreurs["mode"] = "Choisissez le mode TEST ou PRODUCTION."
    seuil = _entier_requete(donnees.get("seuil_formulaire"), "seuil_formulaire", 1, SEUIL_FORMULAIRE_MAX, erreurs,
                            f"Le seuil du formulaire est un entier de 1 à {SEUIL_FORMULAIRE_MAX}.")
    cas = donnees.get("cas") if isinstance(donnees.get("cas"), dict) else {}

    # Envoi réel de l'email : adresses valides, et contenu verrouillé (inventaire
    # d'exemple, noms de produits identiques à ceux du serveur : seules les
    # quantités changent). Impossible d'y glisser du texte libre.
    email = donnees.get("email") if isinstance(donnees.get("email"), dict) else {}
    destinataire = email.get("destinataire") if isinstance(email.get("destinataire"), str) else ""
    expediteur = email.get("expediteur") if isinstance(email.get("expediteur"), str) else ""
    destinataire, expediteur = destinataire.strip(), expediteur.strip()
    if destinataire and not email_valide(destinataire):
        erreurs["destinataire"] = "Adresse email du destinataire invalide."
    if expediteur and not email_valide(expediteur):
        erreurs["expediteur"] = "Adresse email de l'expéditeur invalide."
    if expediteur and not destinataire:
        erreurs.setdefault("destinataire", "Indiquez le destinataire de l'alerte.")
    if destinataire and source == "import":
        erreurs["destinataire"] = "L'envoi réel est réservé aux inventaires d'exemple."
    if destinataire and source == "exemple" and cle in INVENTAIRES and "lignes" not in erreurs:
        attendus = [l["produit"] for l in _inventaire_exemple(cle)]
        if [l["produit"] for l in lignes] != attendus:
            erreurs["destinataire"] = "Pour l'envoi réel, seules les quantités de l'inventaire d'exemple sont modifiables."

    if erreurs:
        raise ErreurValidation(erreurs)
    return Requete(nom, cle, lignes, production, mode, seuil,
                   rapport=cas.get("rapport", True) is not False,
                   scraping=cas.get("scraping", True) is not False,
                   destinataire=destinataire or None, expediteur=expediteur or None)


# ============================================================
# CAS 5 — scraping avec cache et copie de secours
# ============================================================

_cache_scraping: dict = {}
_verrou_scraping = threading.Lock()


@lru_cache(maxsize=1)
def _copie_secours() -> dict:
    try:
        return json.loads(FICHIER_SECOURS_SCRAPING.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def produits_en_ligne(url: str) -> dict:
    """
    {"produits", "source": "direct" | "cache" | "secours", "duree_ms", "date"} ;
    lève navigateur.ErreurReseau si le site est injoignable et qu'aucune copie n'existe.
    """
    with _verrou_scraping:
        en_cache = _cache_scraping.get(url)
        if en_cache and time.monotonic() - en_cache["instant"] < DUREE_CACHE_SCRAPING:
            return {**en_cache["resultat"], "source": "cache"}
    try:
        produits, page = navigateur.scraper(url)
        if not produits:
            raise navigateur.ErreurReseau("Aucun produit trouvé sur la page.")
    except navigateur.ErreurReseau:
        secours = _copie_secours().get("pages", {}).get(url)
        if not secours:
            raise
        return {"produits": secours, "source": "secours", "duree_ms": 0, "date": _copie_secours().get("date")}
    resultat = {"produits": produits, "duree_ms": page.duree_ms, "date": datetime.now().strftime("%Y-%m-%d")}
    with _verrou_scraping:
        _cache_scraping[url] = {"instant": time.monotonic(), "resultat": resultat}
    return {**resultat, "source": "direct"}


def _prix(texte: str) -> Optional[float]:
    nombre = re.sub(r"[^0-9.,]", "", texte).replace(",", "")
    try:
        return float(nombre)
    except ValueError:
        return None


# ============================================================
# CAS 4 — planification (même bibliothèque que scheduler.py)
# ============================================================

def _occurrences(premiere: datetime, periode: timedelta, maintenant: datetime, horizon: timedelta) -> list:
    secondes, instant = [], premiere
    while instant - maintenant <= horizon:
        secondes.append(round((instant - maintenant).total_seconds()))
        instant += periode
    return secondes


def planifier(mode: str) -> dict:
    """
    Prochaines exécutions de chaque job, en secondes à partir de maintenant,
    calculées par la bibliothèque `schedule` avec les intervalles de .env.
    La surveillance démarre aussi immédiatement (premier cycle de start()).
    """
    planif = schedule.Scheduler()
    rien = lambda: None  # noqa: E731
    if mode == "TEST":
        stock, rapport, scraping = (config.TEST_INTERVALLE_STOCK_MINUTES, config.TEST_INTERVALLE_RAPPORT_MINUTES,
                                    config.TEST_INTERVALLE_SCRAPING_MINUTES)
        taches = [
            ("surveillance", "Surveillance du stock", "Cas 1 → 3 → 6", f"toutes les {stock} min",
             planif.every(stock).minutes.do(rien), timedelta(minutes=stock)),
            ("rapport", "Rapport hebdomadaire", "Cas 2", f"toutes les {rapport} min",
             planif.every(rapport).minutes.do(rien), timedelta(minutes=rapport)),
            ("scraping", "Scraping des prix", "Cas 5", f"toutes les {scraping} min",
             planif.every(scraping).minutes.do(rien), timedelta(minutes=scraping)),
        ]
        horizon = timedelta(minutes=max(10, 3 * max(stock, rapport, scraping)))
    else:
        stock, scraping, jour = (config.PROD_INTERVALLE_STOCK_MINUTES, config.PROD_INTERVALLE_SCRAPING_HEURES,
                                 config.PROD_JOUR_RAPPORT_HEBDO.lower())
        taches = [
            ("surveillance", "Surveillance du stock", "Cas 1 → 3 → 6", f"toutes les {stock} min",
             planif.every(stock).minutes.do(rien), timedelta(minutes=stock)),
            ("rapport", "Rapport hebdomadaire", "Cas 2", f"chaque {JOURS_SEMAINE.get(jour, jour)} à 08:00",
             getattr(planif.every(), jour).at("08:00").do(rien), timedelta(days=7)),
            ("scraping", "Scraping des prix", "Cas 5", f"toutes les {scraping} h",
             planif.every(scraping).hours.do(rien), timedelta(hours=scraping)),
        ]
        horizon = timedelta(days=7)

    maintenant = datetime.now()
    resultat = []
    for cle, titre, cas, frequence, job, periode in taches:
        prochaines = _occurrences(job.next_run, periode, maintenant, horizon)
        if cle == "surveillance":
            prochaines = [0] + prochaines
        resultat.append({"cle": cle, "titre": titre, "cas": cas, "frequence": frequence, "prochaines": prochaines})
    return {"mode": mode, "horizon_s": round(horizon.total_seconds()), "taches": resultat}


# ============================================================
# EXÉCUTION
# ============================================================

def _excel(df: pd.DataFrame) -> bytes:
    """Même fichier que df.to_excel(chemin, index=False) dans les scripts, mais en mémoire."""
    tampon = io.BytesIO()
    df.to_excel(tampon, index=False, engine="openpyxl")
    return tampon.getvalue()


def _excel_onglets(feuilles: dict) -> bytes:
    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon, engine="openpyxl") as writer:
        for nom, feuille in feuilles.items():
            feuille.to_excel(writer, sheet_name=nom, index=False)
    return tampon.getvalue()


MEDIA_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class _Pipeline:
    """Une exécution : émet les événements et collecte les fichiers produits."""

    def __init__(self, requete: Requete, emettre: Emetteur, visiteur: str = ""):
        self.requete = requete
        self.visiteur = visiteur
        self._emettre = emettre
        self.horodatage = datetime.now().strftime("%Y-%m-%d_%H-%M")
        base = Path(requete.nom_inventaire).stem.replace("inventaire_", "") or "inventaire"
        self.execution = Execution(secrets.token_hex(16), f"relais_{_normaliser(base)[:40] or 'inventaire'}_{self.horodatage}.zip")

    # ---------- événements ----------
    def log(self, texte: str, niveau: str = "info") -> None:
        self._emettre({"type": "log", "niveau": niveau, "heure": datetime.now().strftime("%H:%M:%S"), "texte": texte})

    def etat(self, cle: str, etat: str, **details) -> None:
        self._emettre({"type": "etape", "cle": cle, "etat": etat, **details})

    def resultat(self, cle: str, donnees: dict) -> None:
        self._emettre({"type": "resultat", "cle": cle, "donnees": donnees})

    def fichier(self, nom: str, contenu: bytes, media: str, cas: int, libelle: str) -> str:
        self.execution.fichiers[nom] = Fichier(nom, contenu, media, cas, libelle)
        return nom

    @contextmanager
    def etape(self, cle: str, fatale: bool = False):
        debut = time.perf_counter()
        suivi = {"resume": "", "etat": "termine", "details": {}}
        self.etat(cle, "en_cours")
        try:
            yield suivi
        except navigateur.ErreurReseau as e:
            self.log(f"  Erreur : {e}", "erreur")
            suivi.update(etat="erreur", resume=str(e))
        except Exception:
            if fatale:
                raise
            logger.exception("Étape %s en échec", cle)
            self.log("  Erreur inattendue pendant cette étape.", "erreur")
            suivi.update(etat="erreur", resume="Erreur inattendue pendant cette étape.")
        self.etat(cle, suivi["etat"], resume=suivi["resume"],
                  duree_ms=round((time.perf_counter() - debut) * 1000), **suivi["details"])

    # ---------- pipeline ----------
    def executer(self) -> None:
        r = self.requete
        debut = time.perf_counter()
        self._emettre({
            "type": "debut",
            "id": self.execution.identifiant,
            "inventaire": r.nom_inventaire,
            "mode": r.mode,
            "heure": datetime.now().strftime("%H:%M:%S"),
            "etapes": [{"cle": cle, "cas": cas, "titre": titre} for cle, cas, titre in ETAPES],
        })
        self.log("Pipeline d'automatisation")
        self.log(f"  Inventaire : {r.nom_inventaire}")
        self.log(f"  Mode {'TEST' if r.mode == 'TEST' else 'PRODUCTION'} actif — seuil formulaire : {r.seuil_formulaire}")

        inventaire = pd.DataFrame({
            "Produit": [l["produit"] for l in r.lignes],
            "Quantite": [l["quantite"] for l in r.lignes],
            "Seuil_Minimum": [l["seuil"] for l in r.lignes],
        })

        ruptures = self._cas1(inventaire)
        self._cas3(ruptures)
        self._cas6(len(ruptures))
        self._cas2()
        self._cas5()
        self._cas4()

        CACHE_EXECUTIONS.ajouter(self.execution)
        base = f"api/executions/{self.execution.identifiant}"
        duree = round((time.perf_counter() - debut) * 1000)
        self.log(f"Pipeline terminé en {duree / 1000:.1f} s — {len(self.execution.fichiers)} fichier(s) prêt(s).", "ok")
        self._emettre({
            "type": "fin",
            "id": self.execution.identifiant,
            "duree_ms": duree,
            "fichiers": [{"nom": f.nom, "taille": len(f.contenu), "cas": f.cas, "libelle": f.libelle,
                          "url": f"{base}/fichiers/{f.nom}"} for f in self.execution.fichiers.values()],
            "archive": {"nom": self.execution.nom_archive, "url": f"{base}/archive.zip"},
        })

    def _cas1(self, inventaire: pd.DataFrame) -> pd.DataFrame:
        with self.etape("cas1", fatale=True) as suivi:
            self.log(f"Lecture : {self.requete.nom_inventaire}")
            alertes = cas1_stock.detecter_ruptures(inventaire)
            self.log(f"--- PRODUITS EN ALERTE  {len(alertes)}/{len(inventaire)} ---", "alerte" if len(alertes) else "ok")
            if alertes.empty:
                self.log("  Aucune rupture — stock nominal.", "ok")
            for a in alertes.itertuples(index=False):
                self.log(f"  {a.Produit} — Qté : {a.Quantite} / Seuil : {a.Seuil_Minimum}", "alerte")
            nom = self.fichier(f"rapport_alerte_{self.horodatage}.xlsx", _excel(alertes), MEDIA_XLSX, 1,
                               "Rapport d'alerte")
            self.log(f"  Rapport : {nom}", "ok")
            self.resultat("cas1", {
                "total": len(inventaire),
                "ruptures": len(alertes),
                "produits": [{"produit": l["produit"], "quantite": l["quantite"], "seuil": l["seuil"],
                              "rupture": l["quantite"] <= l["seuil"]} for l in self.requete.lignes],
                "fichier": nom,
            })
            suivi["resume"] = f"{len(alertes)} rupture(s) sur {len(inventaire)} produits"
            suivi["details"] = {"valeur": len(alertes)}
            self._rapport_alerte = (nom, self.execution.fichiers[nom].contenu)
        return alertes

    def _cas3(self, alertes: pd.DataFrame) -> None:
        r = self.requete
        with self.etape("cas3") as suivi:
            if alertes.empty:
                self.log("Aucune rupture — pas d'alerte email.")
                suivi.update(etat="ignore", resume="0 rupture : aucune alerte à envoyer")
                return
            self.log(f"{len(alertes)} rupture(s) — préparation de l'alerte email…")
            nom_rapport, rapport = self._rapport_alerte
            envoi_reel = bool(r.destinataire) and envoi_email_actif()
            expediteur = formataddr((NOM_EXPEDITEUR_DEMO, config.EMAIL_EXPEDITEUR)) if envoi_reel else EXPEDITEUR_DEMO
            destinataire = r.destinataire or DESTINATAIRE_DEMO
            message = cas3_email.construire_message(alertes, rapport, nom_rapport, expediteur, destinataire,
                                                    repondre_a=r.expediteur)
            nom = self.fichier(f"alerte_stock_{self.horodatage}.eml", message.as_bytes(), "message/rfc822", 3,
                               "Email d'alerte (.eml)")
            self.log(f"  Email prêt pour {destinataire} (pièce jointe : {nom_rapport})", "ok")

            envoi = {"etat": "non_demande"}
            if r.destinataire and not envoi_email_actif():
                envoi = {"etat": "indisponible", "message": "L'envoi réel n'est pas configuré sur ce serveur."}
                self.log("  Envoi réel non configuré sur ce serveur : l'email se télécharge en .eml.", "alerte")
            elif envoi_reel:
                refus = LIMITEUR_ENVOIS.reserver(self.visiteur, r.destinataire)
                if refus:
                    envoi = {"etat": "refuse", "message": refus[0].upper() + refus[1:] + "."}
                    self.log(f"  Envoi refusé : {refus}.", "alerte")
                else:
                    self.log(f"  Envoi vers {r.destinataire} via Gmail (SMTP SSL)…")
                    try:
                        cas3_email.envoyer(message, config.EMAIL_EXPEDITEUR, config.MOT_DE_PASSE_APP, r.destinataire)
                        envoi = {"etat": "envoye", "heure": datetime.now().strftime("%H:%M")}
                        self.log("  Email envoyé avec succès.", "ok")
                    except Exception:
                        logger.exception("Envoi de l'email d'alerte en échec")
                        envoi = {"etat": "echec", "message": "Le serveur d'envoi a refusé le message. Réessayez plus tard."}
                        self.log("  Erreur d'envoi : le serveur d'envoi a refusé le message.", "erreur")
            else:
                self.log("  Sans adresse de destinataire, l'email n'est pas envoyé : il se télécharge en .eml.")

            self.resultat("cas3", {
                "de": f"{NOM_EXPEDITEUR_DEMO} <{config.EMAIL_EXPEDITEUR}>" if envoi_reel else expediteur,
                "a": destinataire,
                "repondre_a": r.expediteur,
                "objet": message["Subject"],
                "html": cas3_email._construire_html(alertes),
                "piece_jointe": nom_rapport,
                "fichier": nom,
                "envoi": envoi,
            })
            if envoi["etat"] == "envoye":
                suivi["resume"] = f"Email envoyé à {r.destinataire}"
            elif envoi["etat"] in ("refuse", "echec", "indisponible"):
                raison = envoi["message"][0].lower() + envoi["message"][1:]
                suivi.update(etat="erreur" if envoi["etat"] == "echec" else "termine",
                             resume=f"Email prêt, non envoyé : {raison}")
            else:
                suivi["resume"] = f"Email prêt : {len(alertes)} produit(s) signalé(s)"

    def _cas6(self, ruptures: int) -> None:
        seuil = self.requete.seuil_formulaire
        with self.etape("cas6") as suivi:
            if ruptures < seuil:
                self.log(f"{ruptures} rupture(s) < seuil {seuil} — formulaire non déclenché.")
                self.resultat("cas6", {"declenche": False, "ruptures": ruptures, "seuil": seuil})
                suivi.update(etat="ignore", resume=f"{ruptures} < {seuil} : formulaire non déclenché")
                return
            self.log(f"Seuil atteint ({ruptures} >= {seuil}) — formulaire d'alerte…", "alerte")
            self.log(f"  Page : {config.FORMULAIRE_URL}")
            try:
                soumission = navigateur.soumettre_formulaire(config.FORMULAIRE_URL, config.FORMULAIRE_DONNEES)
            except navigateur.ErreurReseau as e:
                self.resultat("cas6", {"declenche": True, "ruptures": ruptures, "seuil": seuil, "reussie": False,
                                       "erreur": str(e), "url_formulaire": config.FORMULAIRE_URL})
                raise
            for libelle, valeur in soumission.saisies:
                self.log(f"  {libelle} : {valeur}")
            self.log(f"  Réponse : {soumission.titre or 'sans titre'} — {soumission.message or 'HTTP ' + str(soumission.statut)}",
                     "ok" if soumission.reussie else "erreur")
            self.resultat("cas6", {
                "declenche": True, "ruptures": ruptures, "seuil": seuil, "reussie": soumission.reussie,
                "url_formulaire": soumission.url_formulaire, "url_resultat": soumission.url_resultat,
                "statut": soumission.statut, "titre": soumission.titre, "message": soumission.message,
                "saisies": soumission.saisies, "duree_ms": soumission.duree_ms,
            })
            if soumission.reussie:
                suivi["resume"] = f"Formulaire soumis : « {soumission.message or soumission.titre} »"
            else:
                suivi.update(etat="erreur", resume="Le site n'a pas confirmé la soumission.")

    def _cas2(self) -> None:
        r = self.requete
        with self.etape("cas2") as suivi:
            if not r.rapport:
                self.log("Rapport hebdomadaire désactivé pour cette exécution.")
                suivi.update(etat="ignore", resume="Désactivé dans les paramètres")
                return
            journees = _production_exemple(r.cle_exemple) if r.cle_exemple else (r.production or [])
            if not journees:
                self.log("Aucun fichier de production — rapport hebdomadaire ignoré.")
                suivi.update(etat="ignore", resume="Aucun fichier de production importé")
                return
            self.log(f"Rapport hebdomadaire — {len(journees)} fichier(s) de production")
            frames = []
            for j in journees:
                df = pd.DataFrame({
                    "Produit": [l["produit"] for l in j["lignes"]],
                    "Quantite_Produite": [l["quantite"] for l in j["lignes"]],
                    "Ligne_Production": [l.get("ligne", "") for l in j["lignes"]],
                })
                frames.append((j["jour"], df))
                self.log(f"  Chargé : {j['jour']}.csv  ({len(df)} lignes)")
            detail, recap = cas2_fusion.fusionner(frames)
            nom = self.fichier(f"rapport_semaine_{self.horodatage}.xlsx",
                               _excel_onglets({"Detail journalier": detail, "Recapitulatif semaine": recap}),
                               MEDIA_XLSX, 2, "Rapport hebdomadaire")
            jours = [j for j, _ in sorted(frames, key=lambda f: cas2_fusion.ordre_jour(f[0]))]
            jours = list(dict.fromkeys(j.capitalize() for j in jours))
            pivot = detail.pivot_table(index="Produit", columns="Jour", values="Quantite_Produite",
                                       aggfunc="sum", fill_value=0)
            produits = [{"produit": str(p.Produit), "total": int(p.Total_Semaine),
                         "par_jour": [int(pivot.loc[p.Produit].get(j, 0)) for j in jours]}
                        for p in recap.itertuples(index=False)]
            self.log(f"  Rapport : {nom} — 2 onglets ({len(detail)} lignes, {len(recap)} produits)", "ok")
            self.resultat("cas2", {"jours": jours, "produits": produits, "lignes": len(detail), "fichier": nom})
            suivi["resume"] = f"{len(recap)} produits · {int(recap['Total_Semaine'].sum()):,} unités".replace(",", " ")

    def _cas5(self) -> None:
        r = self.requete
        with self.etape("cas5") as suivi:
            if not r.scraping:
                self.log("Scraping désactivé pour cette exécution.")
                suivi.update(etat="ignore", resume="Désactivé dans les paramètres")
                return
            inventaire_url = Path(f"inventaire_{r.cle_exemple}.xlsx") if r.cle_exemple else chemin_inventaire(
                next(iter(INVENTAIRES)))
            url = config.get_scraping_url(inventaire_url)
            self.log(f"Scraping produits — {url}")
            donnees = produits_en_ligne(url)
            produits = donnees["produits"]
            if donnees["source"] == "secours":
                self.log(f"  Site injoignable : copie de secours du {donnees['date']}.", "alerte")
            elif donnees["source"] == "cache":
                self.log("  Page lue il y a moins de 10 min : résultat réutilisé.")
            else:
                self.log(f"  Page chargée en {donnees['duree_ms']} ms")
            self.log(f"  {len(produits)} produit(s) détecté(s)", "ok")
            df = pd.DataFrame(produits, columns=["Produit", "Prix", "Description", "Note (/ 5)"])
            nom = self.fichier(f"scraping_produits_{self.horodatage}.xlsx", _excel(df), MEDIA_XLSX, 5,
                               "Prix relevés en ligne")
            self.log(f"  {len(df)} produit(s) exportés -> {nom}", "ok")
            self.resultat("cas5", {
                "url": url, "source": donnees["source"], "date": donnees.get("date"),
                "produits": [{"produit": p["Produit"], "prix": p["Prix"], "prix_num": _prix(p["Prix"]),
                              "description": p["Description"], "note": p["Note (/ 5)"]} for p in produits],
                "fichier": nom,
            })
            suivi["resume"] = f"{len(produits)} produits relevés" + (" (copie de secours)" if donnees["source"] == "secours" else "")
            if donnees["source"] == "secours":
                suivi["details"] = {"secours": True}

    def _cas4(self) -> None:
        r = self.requete
        with self.etape("cas4") as suivi:
            plans = {"TEST": planifier("TEST"), "PROD": planifier("PROD")}
            actif = plans[r.mode]
            self.log(f"Planification — mode {'TEST' if r.mode == 'TEST' else 'PRODUCTION'} :")
            for t in actif["taches"]:
                self.log(f"  {t['titre']} : {t['frequence']}")
            self.resultat("cas4", {"mode": r.mode, "plans": plans})
            surveillance = next(t for t in actif["taches"] if t["cle"] == "surveillance")
            suivi["resume"] = f"Surveillance {surveillance['frequence']}"


def executer_pipeline(requete: Requete, emettre: Emetteur, visiteur: str = "") -> None:
    """Point d'entrée de l'API : exécute le pipeline et émet ses événements."""
    if not _PLACES.acquire(timeout=ATTENTE_MAX_PLACE):
        emettre({"type": "erreur", "message": MESSAGE_OCCUPE})
        return
    try:
        _Pipeline(requete, emettre, visiteur).executer()
    except Exception:
        logger.exception("Pipeline en échec")
        emettre({"type": "erreur", "message": MESSAGE_ERREUR_INATTENDUE})
    finally:
        _PLACES.release()
