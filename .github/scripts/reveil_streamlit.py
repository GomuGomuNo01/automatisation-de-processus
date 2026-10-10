"""
reveil_streamlit.py — Visite la démo comme un vrai visiteur (lancé par GitHub Actions)

Streamlit Community Cloud met l'application en veille après 12 heures sans
visite, et un simple ping HTTP ne compte pas : il s'arrête sur la redirection
de connexion de Streamlit. Ce script ouvre donc la page dans Chromium, clique
sur le bouton de réveil si l'application dort, puis lance le pipeline jusqu'à
ce que le lien de l'archive des fichiers soit prêt.

    pip install playwright && playwright install chromium
    python .github/scripts/reveil_streamlit.py [URL]
"""

import os
import re
import sys

from playwright.sync_api import TimeoutError as DelaiDepasse
from playwright.sync_api import sync_playwright

CAPTURE_ECHEC = "reveil-echec.png"

DELAI_PAGE      = 120_000  # ms : chargement de la page hôte de Streamlit
DELAI_VEILLE    = 15_000   # ms : apparition éventuelle du bouton de réveil
DELAI_DEMARRAGE = 300_000  # ms : redémarrage complet après une mise en veille
DELAI_PIPELINE  = 120_000  # ms : exécution du pipeline


def visiter(url: str) -> None:
    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        page = navigateur.new_page(locale="fr-FR", viewport={"width": 1280, "height": 900})
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=DELAI_PAGE)

            reveil = page.get_by_role("button", name=re.compile(r"get this app back up", re.I))
            try:
                reveil.wait_for(timeout=DELAI_VEILLE)
                reveil.click()
                print("Application en veille : réveil demandé.")
            except DelaiDepasse:
                print("Application déjà éveillée.")

            # L'application tourne dans une iframe servie sous /~/+/
            appli = page.frame_locator('iframe[src*="/~/+/"]')
            appli.locator("[data-launch]:not([disabled])").wait_for(timeout=DELAI_DEMARRAGE)
            appli.locator(".hero [data-action='run-default']").click()
            appli.locator("[data-archive][href*='api/executions']").wait_for(state="attached", timeout=DELAI_PIPELINE)
            print("Pipeline exécuté : l'application répond.")
        except Exception:
            page.screenshot(path=CAPTURE_ECHEC, full_page=True)
            raise
        finally:
            navigateur.close()


if __name__ == "__main__":
    adresse = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("STREAMLIT_URL")
    if not adresse:
        sys.exit("Indiquez l'adresse de la démo (argument ou variable STREAMLIT_URL).")
    visiter(adresse)
