"""
scheduler.py — Orchestrateur du pipeline d'automatisation

Deux modes disponibles :
  - TEST : intervalles courts (minutes) pour valider le pipeline rapidement
  - PROD : intervalles longs (heures + hebdomadaire) pour un usage reel

Pipeline execute à chaque cycle :
  Cas 1 (stock) --> si ruptures > 0 : Cas 3 (email)
                --> si ruptures >= SEUIL : Cas 6 (formulaire d'alerte)

Jobs independants :
  Cas 2 (rapport hebdo) --> planifie selon PROD_JOUR_RAPPORT_HEBDO
  Cas 5 (scraping)      --> planifie selon l'intervalle defini
"""
from pathlib import Path
from types import ModuleType
import importlib.util
import sys
import time
from datetime import datetime

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from schedule import every, run_pending, clear, next_run  # type: ignore[attr-defined]
import config


def _load_script(name: str) -> ModuleType:
    """Charge un module depuis scripts/ par chemin absolu (compatible IDE)."""
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Impossible de charger le script : {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


cas1_stock      = _load_script("cas1_stock")
cas2_fusion     = _load_script("cas2_fusion")
cas3_email      = _load_script("cas3_email")
cas5_scraping   = _load_script("cas5_scraping")
cas6_formulaire = _load_script("cas6_formulaire")


SEP = "=" * 60


class PipelineScheduler:
    """Orchestre tous les jobs d'automatisation sur un inventaire donne."""

    def __init__(self, inventaire_path: Path, mode: str) -> None:
        self.inventaire  = inventaire_path
        self.mode        = mode.upper()
        self.output_dir  = config.get_output_dir(inventaire_path)
        self.prod_dir    = config.get_production_dir(inventaire_path)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── Pipeline principal ────────────────────────────────────────────────────

    def _pipeline_surveillance(self) -> None:
        heure = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{heure}] Pipeline surveillance — {self.inventaire.name}")

        ruptures: int = cas1_stock.run(self.inventaire, self.output_dir)

        if ruptures > 0:
            print(f"  {ruptures} rupture(s) — envoi alerte email...")
            cas3_email.run(self.inventaire, self.output_dir)

        if ruptures >= config.SEUIL_FORMULAIRE:
            print(f"  Seuil atteint ({ruptures} >= {config.SEUIL_FORMULAIRE}) — formulaire d'alerte...")
            cas6_formulaire.run()

        prochaine = next_run()
        if prochaine:
            print(f"  Prochain cycle : {prochaine.strftime('%H:%M:%S')}")

    # ── Jobs independants ─────────────────────────────────────────────────────

    def _job_rapport_hebdo(self) -> None:
        heure = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{heure}] Rapport hebdomadaire — {self.prod_dir.name}/")
        cas2_fusion.run(self.prod_dir, self.output_dir)

    def _job_scraping(self) -> None:
        heure = datetime.now().strftime("%H:%M:%S")
        url = config.get_scraping_url(self.inventaire)
        print(f"\n[{heure}] Scraping produits — {url}")
        cas5_scraping.run(url=url, output_dir=self.output_dir)

    # ── Configuration des planifications ─────────────────────────────────────

    def _setup_test(self) -> None:
        intervalle_stock: int    = config.TEST_INTERVALLE_STOCK_MINUTES
        intervalle_rapport: int  = config.TEST_INTERVALLE_RAPPORT_MINUTES
        intervalle_scraping: int = config.TEST_INTERVALLE_SCRAPING_MINUTES

        print(f"\n  Mode TEST actif :")
        print(f"    Surveillance stock  : toutes les {intervalle_stock} minute(s)")
        print(f"    Rapport production  : toutes les {intervalle_rapport} minute(s)")
        print(f"    Scraping produits   : toutes les {intervalle_scraping} minute(s)")

        every(intervalle_stock).minutes.do(self._pipeline_surveillance)
        every(intervalle_rapport).minutes.do(self._job_rapport_hebdo)
        every(intervalle_scraping).minutes.do(self._job_scraping)

    def _setup_prod(self) -> None:
        intervalle_stock: int    = config.PROD_INTERVALLE_STOCK_MINUTES
        intervalle_scraping: int = config.PROD_INTERVALLE_SCRAPING_HEURES
        jour_rapport: str        = config.PROD_JOUR_RAPPORT_HEBDO

        print(f"\n  Mode PRODUCTION actif :")
        print(f"    Surveillance stock  : toutes les {intervalle_stock} minutes")
        print(f"    Scraping produits   : toutes les {intervalle_scraping} heure(s)")
        print(f"    Rapport hebdo       : chaque {jour_rapport} a 08:00")

        every(intervalle_stock).minutes.do(self._pipeline_surveillance)
        every(intervalle_scraping).hours.do(self._job_scraping)
        getattr(every(), jour_rapport).at("08:00").do(self._job_rapport_hebdo)

    # ── Demarrage ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        clear()

        print(f"\n{SEP}")
        print(f"  Pipeline d'automatisation")
        print(f"  Inventaire : {self.inventaire.name}")
        print(f"  Sortie     : output/{self.inventaire.stem.replace('inventaire_', '')}/")
        print(f"  Production : data/production/{self.prod_dir.name}/")
        print(SEP)

        if self.mode == "TEST":
            self._setup_test()
        else:
            self._setup_prod()

        print(f"\n  Arret : Ctrl+C")
        print(SEP)

        print("\n  Execution immediate du premier cycle...")
        self._pipeline_surveillance()

        try:
            while True:
                run_pending()
                time.sleep(10)
        except KeyboardInterrupt:
            clear()
            print(f"\n\n{SEP}")
            print("  Pipeline arrete.")
            print(SEP)
