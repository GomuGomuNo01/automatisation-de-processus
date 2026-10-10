# Image de l'interface web (frontend + API du pipeline)
#   docker build -t relais .
#   docker run -p 8501:8501 relais   →  http://localhost:8501
# Hébergeurs : la plateforme injecte PORT (Cloud Run : 8080, Render : 10000).
# Guide complet : docs/DEPLOIEMENT.md
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8501

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Utilisateur non-root ; le code reste en lecture seule. L'interface web n'écrit
# rien sur le disque (fichiers générés gardés en mémoire) : elle tourne aussi
# sur un système de fichiers en lecture seule (--read-only --tmpfs /tmp).
RUN useradd --create-home --uid 1000 app
COPY . .
USER 1000

EXPOSE 8501
HEALTHCHECK CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ[\"PORT\"]}/_stcore/health', timeout=5)"

# exec : Streamlit devient le PID 1 et reçoit SIGTERM (arrêt propre au redéploiement)
CMD ["sh", "-c", "exec streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0"]
