"""
Cas 5 — Web scraping de donnees produits
Extrait automatiquement les produits d'un site e-commerce et exporte en Excel.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
import pandas as pd
from datetime import datetime
import config


def _chrome(headless: bool) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--log-level=3")
    return webdriver.Chrome(options=opts)


def run(url: str = None, output_dir: Path = None, headless: bool = True) -> None:
    """
    Scrape les produits d'un site e-commerce et exporte les donnees en Excel.

    Args:
        url        : URL cible (defaut : config.SCRAPING_URL)
        output_dir : dossier de sortie (defaut : config.OUTPUT_DIR)
        headless   : True = navigateur invisible, False = navigateur visible
    """
    if url is None:
        _inv = config.DATA_DIR / "inventaire_gaming_multimedia.xlsx"
        url = config.get_scraping_url(_inv)
    if output_dir is None:
        _inv = config.DATA_DIR / "inventaire_gaming_multimedia.xlsx"
        output_dir = config.get_output_dir(_inv)

    mode = "headless" if headless else "visible"
    print(f"\n  Lancement Chrome ({mode})...")
    driver = _chrome(headless)

    try:
        driver.get(url)
        print(f"  Page chargee : {url}")

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "thumbnail"))
        )

        elements = driver.find_elements(By.CLASS_NAME, "thumbnail")
        print(f"  {len(elements)} produit(s) detecte(s)...")

        data = []
        for el in elements:
            try:
                data.append({
                    "Produit":     el.find_element(By.CLASS_NAME, "title").get_attribute("title"),
                    "Prix":        el.find_element(By.CLASS_NAME, "price").text,
                    "Description": el.find_element(By.CLASS_NAME, "description").text,
                    "Note (/ 5)":  len(el.find_elements(By.CSS_SELECTOR, ".ratings .glyphicon-star")),
                })
            except NoSuchElementException:
                pass

        df = pd.DataFrame(data)
        print("\n--- PRODUITS COLLECTES ---")
        print(df[["Produit", "Prix", "Note (/ 5)"]].to_string(index=False))

        output_dir.mkdir(parents=True, exist_ok=True)
        horodatage = datetime.now().strftime("%Y-%m-%d_%H-%M")
        rapport = output_dir / f"scraping_produits_{horodatage}.xlsx"
        df.to_excel(rapport, index=False)
        print(f"\n  {len(df)} produit(s) exportes -> {rapport.name}")

    finally:
        driver.quit()
        print("  Navigateur ferme.")


if __name__ == "__main__":
    run(headless=False)
