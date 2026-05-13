"""
Cas 2 — Rapport de production hebdomadaire
Fusionne les CSV journaliers en un rapport Excel multi-onglets.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from typing import cast
from datetime import datetime
import config


def run(production_dir: Path, output_dir: Path) -> None:
    """
    Fusionne tous les CSV du dossier production_dir en un rapport Excel.

    Args:
        production_dir : dossier contenant les CSV journaliers
        output_dir     : dossier de sortie pour le rapport généré
    """
    fichiers = sorted(production_dir.glob("*.csv"))
    if not fichiers:
        print(f"\nAucun fichier CSV trouvé dans : {production_dir}")
        return

    print(f"\n{len(fichiers)} fichier(s) trouvé(s) dans '{production_dir.name}/'")

    frames: list[pd.DataFrame] = []
    for f in fichiers:
        df = cast(pd.DataFrame, pd.read_csv(f))  # type: ignore[call-overload]
        df["Jour"] = f.stem.capitalize()
        frames.append(df)
        print(f"  Chargé : {f.name}  ({len(df)} lignes)")

    df_final = pd.concat(frames, ignore_index=True)
    df_final = df_final[["Jour", "Produit", "Quantite_Produite", "Ligne_Production"]]

    recap = (
        df_final.groupby("Produit")["Quantite_Produite"]
        .sum()
        .reset_index()
        .rename(columns={"Quantite_Produite": "Total_Semaine"})
        .sort_values("Total_Semaine", ascending=False)
    )

    print("\n--- RÉCAPITULATIF PAR PRODUIT ---")
    print(recap.to_string(index=False))

    output_dir.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.now().strftime("%Y-%m-%d_%H-%M")
    rapport = output_dir / f"rapport_semaine_{horodatage}.xlsx"

    with pd.ExcelWriter(rapport, engine="openpyxl") as writer:
        df_final.to_excel(writer, sheet_name="Detail journalier", index=False)
        recap.to_excel(writer, sheet_name="Recapitulatif semaine", index=False)

    print(f"\n  Rapport : {rapport.name}")
    print(f"  Onglet 1 : Detail journalier     ({len(df_final)} lignes)")
    print(f"  Onglet 2 : Recapitulatif semaine ({len(recap)} produits)")


if __name__ == "__main__":
    _inv = config.DATA_DIR / "inventaire_gaming_multimedia.xlsx"
    run(config.get_production_dir(_inv), config.get_output_dir(_inv))
