"""
main.py — Point d'entree unique du systeme d'automatisation

Usage :
    python main.py

Deux etapes seulement :
  1. Choisir le fichier inventaire à surveiller
  2. Choisir le mode (TEST ou PRODUCTION)

Tout le reste est automatique et recurrent via le PipelineScheduler.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import config
from scheduler import PipelineScheduler


SEP  = "=" * 60
SEP2 = "-" * 60


# ── Selection du fichier inventaire ────────────────────────────────────────────

def _selectionner_inventaire() -> Path:
    fichiers: list[Path] = sorted(config.DATA_DIR.glob("inventaire_*.xlsx"))

    if not fichiers:
        print(f"\n  Aucun fichier inventaire dans : {config.DATA_DIR}")
        print("  Attendu : data/inventaire_*.xlsx")
        sys.exit(1)

    print(f"\n{SEP}")
    print("  Fichiers inventaire disponibles")
    print(SEP2)
    for i, f in enumerate(fichiers, 1):
        print(f"  {i}. {f.name}")
    print(SEP2)

    while True:
        choix = input(f"\n  Selectionnez un fichier (1-{len(fichiers)}) : ").strip()
        if choix.isdigit() and 1 <= int(choix) <= len(fichiers):
            inventaire = fichiers[int(choix) - 1]
            print(f"  Inventaire : {inventaire.name}")
            return inventaire
        print("  Choix invalide.")


# ── Selection du mode ──────────────────────────────────────────────────────────

def _selectionner_mode() -> str:
    print(f"\n{SEP}")
    print("  Mode d'execution")
    print(SEP2)
    print("  1. TEST       — intervalles courts (minutes)")
    print("                  Valide le pipeline rapidement")
    print("  2. PRODUCTION — intervalles reels  (heures/semaine)")
    print("                  Surveillance continue pour un usage metier")
    print(SEP2)

    while True:
        choix = input("\n  Selectionnez un mode (1 ou 2) : ").strip()
        if choix == "1":
            print("  Mode : TEST")
            return "TEST"
        if choix == "2":
            print("  Mode : PRODUCTION")
            return "PROD"
        print("  Choix invalide.")


# ── Point d'entree ─────────────────────────────────────────────────────────────

def main() -> None:
    print(f"\n{SEP}")
    print("  Systeme d'automatisation Python")
    print(SEP)

    inventaire = _selectionner_inventaire()
    mode       = _selectionner_mode()

    pipeline = PipelineScheduler(inventaire, mode)
    pipeline.start()


if __name__ == "__main__":
    main()
