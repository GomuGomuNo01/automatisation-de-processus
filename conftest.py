"""
conftest.py — Configuration pytest à la racine du projet.
Garantit que `import config`, `from webapp import ...` et le chargement des
scripts fonctionnent quelle que soit la cwd au moment de lancer pytest.
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
