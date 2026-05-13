"""
Cas 6 — Automatisation de formulaire web
Remplit et soumet automatiquement un formulaire en ligne champ par champ.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
from datetime import datetime
import config


def _chrome(visible: bool) -> webdriver.Chrome:
    opts = Options()
    if not visible:
        opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--log-level=3")
    return webdriver.Chrome(options=opts)


def run(url: str = None, donnees: dict = None, visible: bool = False) -> None:
    """
    Remplit et soumet automatiquement un formulaire web.

    Args:
        url     : URL du formulaire (defaut : config.FORMULAIRE_URL)
        donnees : dict des valeurs a saisir (defaut : config.FORMULAIRE_DONNEES)
        visible : True = navigateur visible (demo), False = headless (production)
    """
    if url is None:
        url = config.FORMULAIRE_URL
    if donnees is None:
        donnees = config.FORMULAIRE_DONNEES

    mode = "visible" if visible else "headless"
    print(f"\n  Lancement Chrome ({mode})...")
    driver = _chrome(visible)

    try:
        driver.get(url)
        print(f"  Page chargee : {url}\n")

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "my-text"))
        )

        print("--- SAISIE AUTOMATIQUE ---")

        driver.find_element(By.NAME, "my-text").send_keys(donnees["texte"])
        print(f"  Texte    : {donnees['texte']}")

        driver.find_element(By.NAME, "my-password").send_keys(donnees["mot_de_passe"])
        print(f"  Password : {'*' * len(donnees['mot_de_passe'])}")

        driver.find_element(By.NAME, "my-textarea").send_keys(donnees["zone_texte"])
        print(f"  Textarea : {donnees['zone_texte']}")

        Select(driver.find_element(By.NAME, "my-select")).select_by_visible_text(
            donnees["liste_deroulante"]
        )
        print(f"  Select   : {donnees['liste_deroulante']}")

        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(2)

        heure = datetime.now().strftime("%H:%M:%S")
        print(f"\n  [{heure}] Formulaire soumis avec succes !")
        print(f"  URL apres soumission : {driver.current_url}")

    except Exception as e:
        print(f"\n  Erreur : {e}")
    finally:
        driver.quit()
        print("  Navigateur ferme.")


if __name__ == "__main__":
    run(visible=False)
