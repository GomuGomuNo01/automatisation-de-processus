"""
Cas 3 — Alertes email automatiques
Détecte les ruptures et envoie un email HTML avec le rapport en pièce jointe.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from html import escape
import config


def _construire_html(alertes: pd.DataFrame) -> str:
    if alertes.empty:
        return "<p>Aucun produit en rupture de stock aujourd'hui.</p>"

    lignes = "".join(
        f"<tr>"
        f"<td style='padding:8px;border:1px solid #ddd'>{escape(str(r['Produit']))}</td>"
        f"<td style='padding:8px;border:1px solid #ddd;color:red;text-align:center'>{int(r['Quantite'])}</td>"
        f"<td style='padding:8px;border:1px solid #ddd;text-align:center'>{int(r['Seuil_Minimum'])}</td>"
        f"</tr>"
        for _, r in alertes.iterrows()
    )
    date_str = datetime.now().strftime("%d/%m/%Y a %H:%M")
    return f"""
    <html><body style='font-family:Arial,sans-serif'>
    <h2 style='color:#cc0000'>Alerte Rupture de Stock</h2>
    <p>Bonjour,<br>
    Le rapport automatique du <b>{date_str}</b> identifie
    <b>{len(alertes)} produit(s)</b> en rupture ou en seuil critique.</p>
    <table style='border-collapse:collapse;width:65%'>
      <thead>
        <tr style='background:#cc0000;color:white'>
          <th style='padding:10px;text-align:left'>Produit</th>
          <th style='padding:10px'>Qte actuelle</th>
          <th style='padding:10px'>Seuil minimum</th>
        </tr>
      </thead>
      <tbody>{lignes}</tbody>
    </table>
    <p style='margin-top:20px'>
      Le rapport complet est disponible en piece jointe.<br><br>
      <i>Systeme d'automatisation Python</i>
    </p>
    </body></html>"""


def construire_message(
    alertes: pd.DataFrame,
    rapport: bytes,
    nom_rapport: str,
    expediteur: str,
    destinataire: str,
    repondre_a: str | None = None,
) -> MIMEMultipart:
    """Email d'alerte : tableau HTML des ruptures + rapport Excel en pièce jointe."""
    msg = MIMEMultipart()
    msg["From"]    = expediteur
    msg["To"]      = destinataire
    if repondre_a:
        msg["Reply-To"] = repondre_a
    msg["Subject"] = (
        f"[ALERTE STOCK] {len(alertes)} produit(s) en rupture - "
        f"{datetime.now().strftime('%d/%m/%Y')}"
    )
    msg.attach(MIMEText(_construire_html(alertes), "html"))

    pj = MIMEBase("application", "octet-stream")
    pj.set_payload(rapport)
    encoders.encode_base64(pj)
    pj.add_header("Content-Disposition", f"attachment; filename={nom_rapport}")
    msg.attach(pj)
    return msg


def envoyer(msg: MIMEMultipart, compte: str, mot_de_passe: str, destinataire: str) -> None:
    """Envoie le message par Gmail (SMTP SSL, port 465). Lève une exception en cas d'échec."""
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as srv:
        srv.login(compte, mot_de_passe)
        srv.sendmail(compte, destinataire, msg.as_string())


def run(inventaire_path: Path, output_dir: Path) -> None:
    """
    Lit l'inventaire, genere le rapport Excel et envoie l'email d'alerte.

    Args:
        inventaire_path : chemin vers le fichier Excel inventaire
        output_dir      : dossier de sortie pour le rapport genere
    """
    if not config.EMAIL_EXPEDITEUR:
        print("\n  Email non configure — renseignez EMAIL_EXPEDITEUR dans .env")
        return

    df = pd.read_excel(inventaire_path)
    alertes = df[df["Quantite"] <= df["Seuil_Minimum"]].copy()
    alertes["Statut"] = "RUPTURE"

    # Rapport Excel
    output_dir.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.now().strftime("%Y-%m-%d_%H-%M")
    rapport = output_dir / f"rapport_alerte_{horodatage}.xlsx"
    alertes.to_excel(rapport, index=False)
    print(f"  Rapport : {rapport.name}")

    # Construction du mail (piece jointe : le rapport Excel)
    msg = construire_message(
        alertes, rapport.read_bytes(), rapport.name,
        config.EMAIL_EXPEDITEUR, config.EMAIL_DESTINATAIRE,
    )

    # Envoi
    print(f"  Envoi vers {config.EMAIL_DESTINATAIRE} ...")
    try:
        envoyer(msg, config.EMAIL_EXPEDITEUR, config.MOT_DE_PASSE_APP, config.EMAIL_DESTINATAIRE)
        print("  Email envoye avec succes.")
    except Exception as e:
        print(f"  Erreur envoi : {e}")


if __name__ == "__main__":
    _inv = config.DATA_DIR / "inventaire_gaming_multimedia.xlsx"
    run(_inv, config.get_output_dir(_inv))
