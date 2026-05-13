"""
Cas 4 — Surveillance planifiee
Boucle de verification du stock a intervalle fixe, sans intervention humaine.
Reutilise la logique du Cas 1 pour eviter la duplication de code.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from schedule import every, run_pending, clear, next_run  # type: ignore[attr-defined]
import time
from datetime import datetime
import config
import cas1_stock


def _cycle(inventaire_path: Path, output_dir: Path) -> None:
    heure = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{heure}] Cycle de surveillance...")
    cas1_stock.run(inventaire_path, output_dir)
    prochaine = next_run()
    if prochaine:
        print(f"  Prochaine execution : {prochaine.strftime('%H:%M:%S')}")


def run(inventaire_path: Path, output_dir: Path, intervalle_minutes: int = None) -> None:
    """
    Lance la surveillance en boucle avec rapport genere a chaque cycle.

    Args:
        inventaire_path    : fichier inventaire a surveiller
        output_dir         : dossier de sortie des rapports
        intervalle_minutes : frequence en minutes (defaut : config.TEST_INTERVALLE_STOCK_MINUTES)
    """
    if intervalle_minutes is None:
        intervalle_minutes = config.TEST_INTERVALLE_STOCK_MINUTES

    sep = "=" * 54
    print(f"\n{sep}")
    print(f"  Surveillance : {inventaire_path.name}")
    print(f"  Frequence    : toutes les {intervalle_minutes} minute(s)")
    print("  Arret        : Ctrl+C")
    print(sep)

    _cycle(inventaire_path, output_dir)

    clear()
    every(intervalle_minutes).minutes.do(_cycle, inventaire_path, output_dir)

    try:
        while True:
            run_pending()
            time.sleep(15)
    except KeyboardInterrupt:
        clear()
        print("\n  Surveillance arretee.")


if __name__ == "__main__":
    _inv = config.DATA_DIR / "inventaire_gaming_multimedia.xlsx"
    run(_inv, config.get_output_dir(_inv), config.TEST_INTERVALLE_STOCK_MINUTES)
