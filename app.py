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
# Windows n'a pas tzset et comprend mal « Europe/Paris » dans TZ : l'heure du poste s'y applique.
if hasattr(time, "tzset"):
    os.environ["TZ"] = os.environ.get("RELAIS_TZ", "Europe/Paris")
    time.tzset()

import streamlit as st  # noqa: E402

# Secrets de l'hébergeur (Streamlit Cloud : Settings > Secrets) : le compte Gmail
# d'envoi de la démo. Copiés dans l'environnement avant la lecture de config.py,
# où ils priment sur .env.example. Sans secrets, l'email reste téléchargeable.
try:
    for _cle in ("EMAIL_EXPEDITEUR", "MOT_DE_PASSE_APP"):
        if _cle in st.secrets and str(st.secrets[_cle]).strip():
            os.environ[_cle] = str(st.secrets[_cle]).strip()
except Exception:  # aucun fichier de secrets : rien à copier
    pass

from webapp.api import creer_middlewares, creer_routes  # noqa: E402

PAGE_DE_REPLI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp", "fallback.py")

app = st.App(PAGE_DE_REPLI, routes=creer_routes(), middleware=creer_middlewares())
