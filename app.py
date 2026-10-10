"""
app.py — Point d'entrée de l'interface web

Le frontend (webapp/static) et l'API du pipeline (webapp/api.py) sont des
routes Starlette servies par st.App ; Streamlit ne sert que la page
« Page introuvable » (webapp/fallback.py) pour les adresses inconnues.

Lancement :
    streamlit run app.py      (fonctionne aussi sur Streamlit Community Cloud)
    uvicorn app:app           (n'importe quel serveur ASGI)

La ligne de commande d'origine reste disponible : python main.py
"""

import os
import time

# Les hébergeurs tournent en UTC : la démo raisonne à l'heure française, comme la
# ligne de commande sur un poste en France (horodatage des fichiers, journal,
# « chaque vendredi à 08:00 » du mode PRODUCTION). RELAIS_TZ permet d'en changer.
os.environ["TZ"] = os.environ.get("RELAIS_TZ", "Europe/Paris")
if hasattr(time, "tzset"):  # absent sous Windows, où l'heure locale du poste s'applique
    time.tzset()

import streamlit as st  # noqa: E402

from webapp.api import creer_middlewares, creer_routes  # noqa: E402

PAGE_DE_REPLI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp", "fallback.py")

app = st.App(PAGE_DE_REPLI, routes=creer_routes(), middleware=creer_middlewares())
