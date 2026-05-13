"""
scripts/config.py — Redirecteur vers config.py (racine)

Charge la configuration par chemin absolu (evite les conflits sys.path)
et re-exporte chaque attribut avec un type explicite pour la resolution IDE.
"""
from pathlib import Path
from typing import Callable
import importlib.util

_root_path = Path(__file__).resolve().parent.parent / "config.py"
_spec = importlib.util.spec_from_file_location("_root_config", _root_path)

if _spec is None or _spec.loader is None:
    raise ImportError(f"Impossible de charger la configuration depuis : {_root_path}")

_root = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_root)  # type: ignore[union-attr]

# ── Chemins ───────────────────────────────────────────────────────────────────
BASE_DIR:       Path = _root.BASE_DIR
DATA_DIR:       Path = _root.DATA_DIR
OUTPUT_DIR:     Path = _root.OUTPUT_DIR
PRODUCTION_DIR: Path = _root.PRODUCTION_DIR

# ── Email ─────────────────────────────────────────────────────────────────────
EMAIL_EXPEDITEUR:   str = _root.EMAIL_EXPEDITEUR
MOT_DE_PASSE_APP:   str = _root.MOT_DE_PASSE_APP
EMAIL_DESTINATAIRE: str = _root.EMAIL_DESTINATAIRE

# ── Intervalles TEST ──────────────────────────────────────────────────────────
TEST_INTERVALLE_STOCK_MINUTES:    int = _root.TEST_INTERVALLE_STOCK_MINUTES
TEST_INTERVALLE_RAPPORT_MINUTES:  int = _root.TEST_INTERVALLE_RAPPORT_MINUTES
TEST_INTERVALLE_SCRAPING_MINUTES: int = _root.TEST_INTERVALLE_SCRAPING_MINUTES

# ── Intervalles PRODUCTION ────────────────────────────────────────────────────
PROD_INTERVALLE_STOCK_MINUTES:   int = _root.PROD_INTERVALLE_STOCK_MINUTES
PROD_INTERVALLE_SCRAPING_HEURES: int = _root.PROD_INTERVALLE_SCRAPING_HEURES
PROD_JOUR_RAPPORT_HEBDO:         str = _root.PROD_JOUR_RAPPORT_HEBDO

# ── Pipeline ──────────────────────────────────────────────────────────────────
SEUIL_FORMULAIRE: int = _root.SEUIL_FORMULAIRE

# ── Formulaire ────────────────────────────────────────────────────────────────
FORMULAIRE_URL:     str            = _root.FORMULAIRE_URL
FORMULAIRE_DONNEES: dict[str, str] = _root.FORMULAIRE_DONNEES

# ── Helpers ───────────────────────────────────────────────────────────────────
get_production_dir: Callable[[Path], Path] = _root.get_production_dir
get_output_dir:     Callable[[Path], Path] = _root.get_output_dir
get_scraping_url:   Callable[[Path], str]  = _root.get_scraping_url
