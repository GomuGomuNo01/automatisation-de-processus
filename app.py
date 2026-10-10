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

import streamlit as st

from webapp.api import creer_middlewares, creer_routes

PAGE_DE_REPLI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp", "fallback.py")

app = st.App(PAGE_DE_REPLI, routes=creer_routes(), middleware=creer_middlewares())
