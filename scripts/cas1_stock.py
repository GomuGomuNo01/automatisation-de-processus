"""
Cas 1 — Rapport de stock automatique
Détecte les produits en rupture et génère un rapport Excel horodaté.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from datetime import datetime
import config


def run(inventaire_path: Path, output_dir: Path) -> int:
    """
    Lit le fichier inventaire, détecte les ruptures et génère un rapport.

    Args:
        inventaire_path : chemin vers le fichier Excel inventaire
        output_dir      : dossier de sortie pour le rapport généré

    Returns:
        Nombre de produits en alerte
    """
    print(f"\nLecture : {inventaire_path.name}")
    df = pd.read_excel(inventaire_path)

    alertes = df[df["Quantite"] <= df["Seuil_Minimum"]].copy()
    alertes["Statut"] = "RUPTURE"

    print(f"\n--- PRODUITS EN ALERTE  {len(alertes)}/{len(df)} ---")
    if alertes.empty:
        print("  Aucune rupture — stock nominal.")
    else:
        for _, r in alertes.iterrows():
            print(
                f"  {r['Produit']:<40}"
                f"  Qte : {int(r['Quantite']):>5}"
                f"  /  Seuil : {int(r['Seuil_Minimum']):>5}"
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.now().strftime("%Y-%m-%d_%H-%M")
    rapport = output_dir / f"rapport_alerte_{horodatage}.xlsx"
    alertes.to_excel(rapport, index=False)
    print(f"\n  Rapport : {rapport.name}")
    return len(alertes)


if __name__ == "__main__":
    _inv = config.DATA_DIR / "inventaire_gaming_multimedia.xlsx"
    run(_inv, config.get_output_dir(_inv))
