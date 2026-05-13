"""
config.py — Configuration centrale du projet

Toutes les valeurs sont lues depuis le fichier .env.
Aucune valeur par defaut n'est definie ici — le .env fait autorite.
Pour modifier un comportement, editez uniquement .env.
"""
from pathlib import Path
from dotenv import load_dotenv
import os

# ── Chemins de base (calcules automatiquement, pas dans .env) ─────────────────
BASE_DIR       = Path(__file__).resolve().parent
DATA_DIR       = BASE_DIR / "data"
OUTPUT_DIR     = BASE_DIR / "output"
PRODUCTION_DIR = DATA_DIR / "production"

# ── Chargement du fichier .env ─────────────────────────────────────────────────
load_dotenv(BASE_DIR / ".env")


def _require(key: str) -> str:
    """Lit une variable .env obligatoire — leve une RuntimeError si absente."""
    val = os.getenv(key)
    if val is None:
        raise RuntimeError(
            f"Variable manquante dans .env : {key}\n"
            f"  Ajoutez '{key}=...' dans votre fichier .env (voir .env.example)"
        )
    return val


# ── Email — Cas 3 ─────────────────────────────────────────────────────────────
EMAIL_EXPEDITEUR   = _require("EMAIL_EXPEDITEUR")
MOT_DE_PASSE_APP   = _require("MOT_DE_PASSE_APP")
EMAIL_DESTINATAIRE = _require("EMAIL_DESTINATAIRE")

# ── Intervalles TEST (minutes) ────────────────────────────────────────────────
TEST_INTERVALLE_STOCK_MINUTES    = int(_require("TEST_INTERVALLE_STOCK_MINUTES"))
TEST_INTERVALLE_RAPPORT_MINUTES  = int(_require("TEST_INTERVALLE_RAPPORT_MINUTES"))
TEST_INTERVALLE_SCRAPING_MINUTES = int(_require("TEST_INTERVALLE_SCRAPING_MINUTES"))

# ── Intervalles PRODUCTION ────────────────────────────────────────────────────
PROD_INTERVALLE_STOCK_MINUTES   = int(_require("PROD_INTERVALLE_STOCK_MINUTES"))
PROD_INTERVALLE_SCRAPING_HEURES = int(_require("PROD_INTERVALLE_SCRAPING_HEURES"))
PROD_JOUR_RAPPORT_HEBDO         = _require("PROD_JOUR_RAPPORT_HEBDO")

# ── Pipeline ──────────────────────────────────────────────────────────────────
SEUIL_FORMULAIRE = int(_require("SEUIL_DECLENCHEMENT_FORMULAIRE"))

# ── Web scraping — Cas 5 (une URL par inventaire) ────────────────────────────
_SCRAPING_URLS: dict[str, str] = {
    "gaming_multimedia":   _require("SCRAPING_URL_GAMING_MULTIMEDIA"),
    "consommables_bureau": _require("SCRAPING_URL_CONSOMMABLES_BUREAU"),
    "stockage_securite":   _require("SCRAPING_URL_STOCKAGE_SECURITE"),
}

# ── Formulaire web — Cas 6 ────────────────────────────────────────────────────
FORMULAIRE_URL = _require("FORMULAIRE_URL")
FORMULAIRE_DONNEES: dict[str, str] = {
    "texte":            _require("FORM_TEXTE"),
    "mot_de_passe":     _require("FORM_PASSWORD"),
    "zone_texte":       _require("FORM_TEXTAREA"),
    "liste_deroulante": _require("FORM_SELECT"),
}


# ── Helpers — chemins et URLs dynamiques par inventaire ──────────────────────

def get_production_dir(inventaire_path: Path) -> Path:
    """Retourne le dossier de production associe a un fichier inventaire."""
    name = inventaire_path.stem.replace("inventaire_", "")
    return PRODUCTION_DIR / name


def get_output_dir(inventaire_path: Path) -> Path:
    """Retourne le dossier de sortie associe a un fichier inventaire."""
    name = inventaire_path.stem.replace("inventaire_", "")
    return OUTPUT_DIR / name


def get_scraping_url(inventaire_path: Path) -> str:
    """Retourne l'URL de scraping associee a un fichier inventaire."""
    name = inventaire_path.stem.replace("inventaire_", "")
    url = _SCRAPING_URLS.get(name)
    if url is None:
        raise ValueError(
            f"Aucune URL de scraping definie pour l'inventaire '{name}'.\n"
            f"  Ajoutez SCRAPING_URL_{name.upper()}=... dans .env"
        )
    return url
