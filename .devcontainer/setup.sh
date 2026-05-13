#!/bin/bash
set -e

SEP="============================================================"

echo ""
echo "$SEP"
echo "  Configuration de l'environnement Codespaces"
echo "$SEP"

# ── 1. Chromium (requis pour Cas 5 et 6 — Selenium headless) ─────────────────
echo ""
echo "  [1/3] Installation de Chromium..."
sudo apt-get update -qq
sudo apt-get install -y -qq chromium chromium-driver 2>/dev/null || \
  sudo apt-get install -y -qq chromium-browser 2>/dev/null || \
  echo "  Avertissement : Chromium non installe — Cas 5 et 6 ne fonctionneront pas."

CHROME_VERSION=$(chromium --version 2>/dev/null || chromium-browser --version 2>/dev/null || echo "non installe")
echo "  Chromium : $CHROME_VERSION"

# ── 2. Dependances Python ─────────────────────────────────────────────────────
echo ""
echo "  [2/3] Installation des dependances Python..."
pip install --quiet -r requirements.txt
echo "  Dependances installees (pandas, openpyxl, selenium, schedule, python-dotenv)"

# ── 3. Fichier .env ───────────────────────────────────────────────────────────
echo ""
echo "  [3/3] Configuration .env..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo "  .env cree depuis .env.example"
else
  echo "  .env existant conserve"
fi

# ── Recapitulatif ─────────────────────────────────────────────────────────────
echo ""
echo "$SEP"
echo "  Environnement pret !"
echo "$SEP"
echo ""
echo "  Cas testables immediatement (sans modifier .env) :"
echo "    python scripts/cas1_stock.py      # Rapport de stock"
echo "    python scripts/cas2_fusion.py     # Rapport hebdomadaire"
echo "    python scripts/cas5_scraping.py   # Scraping produits"
echo "    python scripts/cas6_formulaire.py # Formulaire automatique"
echo ""
echo "  Cas 3 (email) — editez .env avec vos credentials Gmail :"
echo "    EMAIL_EXPEDITEUR, MOT_DE_PASSE_APP, EMAIL_DESTINATAIRE"
echo ""
echo "  Pipeline complet :"
echo "    python main.py"
echo "$SEP"
