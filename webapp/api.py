"""
api.py — Routes HTTP de l'interface web (Starlette, servies par st.App)

Expose le frontend statique (webapp/static), l'API du pipeline (flux NDJSON
alimenté par un thread de travail), l'import de fichiers, les téléchargements
et deux middlewares : compression GZip sélective et en-têtes HTTP.
"""

import asyncio
import json
import logging
import os
import re
import threading
from typing import Callable, Optional

from starlette.datastructures import MutableHeaders, UploadFile
from starlette.exceptions import HTTPException
from starlette.formparsers import MultiPartException
from starlette.middleware import Middleware
from starlette.middleware.gzip import DEFAULT_EXCLUDED_CONTENT_TYPES, GZipMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import BaseRoute, Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from webapp import service

logger = logging.getLogger(__name__)

DOSSIER_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
INDEX_HTML     = os.path.join(DOSSIER_STATIC, "index.html")
DOSSIER_ASSETS = os.path.join(DOSSIER_STATIC, "assets")

# ============================================================
# PARAMÈTRES
# ============================================================

TAILLE_MAX_JSON   = 1024 * 1024                                       # requête de pipeline
TAILLE_MAX_IMPORT = (1 + service.MAX_FICHIERS_PROD) * service.TAILLE_MAX_FICHIER + 64 * 1024

MEDIA_NDJSON     = "application/x-ndjson"
GZIP_TAILLE_MIN  = 1000
# En plus des exclusions par défaut de Starlette : le flux NDJSON (doit partir
# ligne par ligne) et les fichiers déjà compressés (xlsx, zip, polices).
EXCLUSIONS_GZIP  = (MEDIA_NDJSON, service.MEDIA_XLSX, "application/zip", "application/octet-stream", "font/*")
CACHE_ASSETS     = "public, max-age=604800"  # 7 jours : polices et images
# CSS et modules JS : revalidés à chaque visite (ETag, réponse 304 légère), pour
# qu'un déploiement ne mélange jamais d'anciens et de nouveaux modules
CACHE_CODE       = "no-cache"
EXTENSIONS_CODE  = (".css", ".js")
ENTETES_SECURITE = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy":        "strict-origin-when-cross-origin",
}
ENTETES_FLUX = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}

RE_IDENTIFIANT   = re.compile(r"^[0-9a-f]{32}$")
RE_EXEMPLE_XLSX  = re.compile(r"^inventaire_([a-z_]+)\.xlsx$")
RE_EXEMPLE_ZIP   = re.compile(r"^production_([a-z_]+)\.zip$")
MESSAGE_INTROUVABLE = "Fichier introuvable ou expiré (conservé 1 heure). Relancez le pipeline."
MESSAGE_TROP_VOLUMINEUX = "Les fichiers envoyés sont trop volumineux (2 Mo maximum par fichier)."
MESSAGE_ILLISIBLE = "Le formulaire envoyé est illisible."

# Préfixes servis par nos routes (le reste appartient à Streamlit)
PREFIXES_APPLI = ("/api/", "/assets/", "/exemples/")


def _est_route_appli(chemin: str) -> bool:
    return chemin == "/" or chemin == "/assets" or chemin.startswith(PREFIXES_APPLI)


def _reponse_erreurs(erreurs: dict, statut: int = 422) -> JSONResponse:
    return JSONResponse({"erreurs": erreurs}, status_code=statut)


# ============================================================
# LIMITE DE TAILLE DU CORPS
# ============================================================

class CorpsTropVolumineux(Exception):
    """Le corps de la requête dépasse la taille maximale (levée pendant la lecture)."""


def recevoir_avec_limite(receive: Receive, limite: int) -> Receive:
    """
    Enveloppe `receive` : lève CorpsTropVolumineux dès que plus de `limite`
    octets sont arrivés. Couvre les envois sans Content-Length (chunked).
    """
    recus = 0

    async def recevoir() -> Message:
        nonlocal recus
        message = await receive()
        if message["type"] == "http.request":
            recus += len(message.get("body", b""))
            if recus > limite:
                raise CorpsTropVolumineux()
        return message

    return recevoir


def _annonce_trop_volumineux(request: Request, limite: int) -> bool:
    try:
        return int(request.headers.get("content-length", "0")) > limite
    except ValueError:
        return False


# ============================================================
# FLUX NDJSON (thread de travail → queue → réponse)
# ============================================================

def ligne_ndjson(evenement: dict) -> bytes:
    """Un objet JSON compact par ligne ; jamais de NaN (JSON invalide)."""
    try:
        texte = json.dumps(evenement, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError):
        logger.exception("Événement non sérialisable en JSON")
        texte = json.dumps({"type": "erreur", "message": service.MESSAGE_ERREUR_INATTENDUE},
                           ensure_ascii=False, separators=(",", ":"))
    return (texte + "\n").encode("utf-8")


def flux_evenements(tache: Callable[[service.Emetteur], object]):
    """
    Lance `tache(emettre)` dans un thread et retourne un générateur asynchrone
    des lignes NDJSON, émises au fur et à mesure. Si le client se déconnecte,
    le thread va quand même au bout (les fichiers restent en cache).
    """
    boucle = asyncio.get_running_loop()
    file_attente: asyncio.Queue = asyncio.Queue()
    fin = object()

    def emettre(evenement) -> None:
        try:
            boucle.call_soon_threadsafe(file_attente.put_nowait, evenement)
        except RuntimeError:  # boucle fermée (arrêt du serveur) : plus personne n'écoute
            pass

    def travailler() -> None:
        try:
            tache(emettre)
        finally:
            emettre(fin)

    threading.Thread(target=travailler, name="pipeline-web", daemon=True).start()

    async def lignes():
        while True:
            evenement = await file_attente.get()
            if evenement is fin:
                return
            yield ligne_ndjson(evenement)

    return lignes()


# ============================================================
# ENDPOINTS
# ============================================================

async def page_accueil(request: Request) -> Response:
    if not os.path.isfile(INDEX_HTML):
        return HTMLResponse("<!doctype html><html lang=\"fr\"><body>Interface indisponible.</body></html>",
                            status_code=503)
    return FileResponse(INDEX_HTML, media_type="text/html", headers={"Cache-Control": "no-cache"})


async def inventaires(request: Request) -> Response:
    return JSONResponse({"inventaires": service.lister_inventaires(),
                         "seuil_formulaire": service.config.SEUIL_FORMULAIRE})


async def inventaire(request: Request) -> Response:
    contenu = service.lire_inventaire(request.path_params["cle"])
    if contenu is None:
        return JSONResponse({"erreur": "Inventaire d'exemple inconnu."}, status_code=404)
    return JSONResponse(contenu)


async def importer(request: Request) -> Response:
    """Multipart : `inventaire` (un .xlsx ou .csv) et `production` (CSV journaliers, facultatifs)."""
    if _annonce_trop_volumineux(request, TAILLE_MAX_IMPORT):
        return _reponse_erreurs({"fichier": MESSAGE_TROP_VOLUMINEUX})
    request = Request(request.scope, recevoir_avec_limite(request.receive, TAILLE_MAX_IMPORT))
    try:
        formulaire = await request.form(max_files=service.MAX_FICHIERS_PROD + 1, max_fields=10)
    except CorpsTropVolumineux:
        return _reponse_erreurs({"fichier": MESSAGE_TROP_VOLUMINEUX})
    except MultiPartException:
        return _reponse_erreurs({"fichier": MESSAGE_ILLISIBLE})
    except HTTPException as e:  # st.App convertit MultiPartException en 400
        if e.status_code != 400:
            raise
        return _reponse_erreurs({"fichier": MESSAGE_ILLISIBLE})

    fichier = formulaire.get("inventaire")
    if not isinstance(fichier, UploadFile) or not fichier.filename:
        return _reponse_erreurs({"fichier": "Choisissez un fichier d'inventaire (.xlsx ou .csv)."})
    nom = os.path.basename(fichier.filename.replace("\\", "/"))
    try:
        lignes = await asyncio.to_thread(service.importer_inventaire, nom, await fichier.read())
        envois = [f for f in formulaire.getlist("production") if isinstance(f, UploadFile) and f.filename]
        production = None
        if envois:
            contenus = [(os.path.basename(f.filename.replace("\\", "/")), await f.read()) for f in envois]
            production = await asyncio.to_thread(service.importer_production, contenus)
    except service.ErreurValidation as e:
        return _reponse_erreurs(e.erreurs)
    return JSONResponse({"nom": nom, "lignes": lignes, "production": production})


async def lancer_pipeline(request: Request) -> Response:
    if _annonce_trop_volumineux(request, TAILLE_MAX_JSON):
        return _reponse_erreurs({"requete": "Requête trop volumineuse."})
    request = Request(request.scope, recevoir_avec_limite(request.receive, TAILLE_MAX_JSON))
    try:
        donnees = json.loads(await request.body())
    except CorpsTropVolumineux:
        return _reponse_erreurs({"requete": "Requête trop volumineuse."})
    except ValueError:
        return _reponse_erreurs({"requete": "La requête doit être un objet JSON."})
    try:
        requete = service.valider_requete(donnees)
    except service.ErreurValidation as e:
        return _reponse_erreurs(e.erreurs)
    flux = flux_evenements(lambda emettre: service.executer_pipeline(requete, emettre))
    return StreamingResponse(flux, media_type=MEDIA_NDJSON, headers=ENTETES_FLUX)


def _execution(request: Request) -> Optional[service.Execution]:
    identifiant = request.path_params["identifiant"]
    if not RE_IDENTIFIANT.match(identifiant):
        return None
    return service.CACHE_EXECUTIONS.obtenir(identifiant)


def _introuvable() -> JSONResponse:
    return JSONResponse({"erreur": MESSAGE_INTROUVABLE}, status_code=404)


def _piece_jointe(nom: str) -> dict:
    return {"Content-Disposition": f'attachment; filename="{nom}"', "Cache-Control": "no-store"}


async def telecharger_fichier(request: Request) -> Response:
    execution = _execution(request)
    fichier = execution.fichiers.get(request.path_params["nom"]) if execution else None
    if fichier is None:
        return _introuvable()
    return Response(fichier.contenu, media_type=fichier.media, headers=_piece_jointe(fichier.nom))


async def telecharger_archive(request: Request) -> Response:
    execution = _execution(request)
    if execution is None:
        return _introuvable()
    contenu = await asyncio.to_thread(execution.archive)
    return Response(contenu, media_type="application/zip", headers=_piece_jointe(execution.nom_archive))


async def exemple(request: Request) -> Response:
    """Fichiers d'exemple, sur liste blanche : les 3 inventaires et leur production."""
    nom = request.path_params["nom"]
    if (m := RE_EXEMPLE_XLSX.match(nom)) and m.group(1) in service.INVENTAIRES:
        chemin = service.chemin_inventaire(m.group(1))
        if chemin.is_file():
            return FileResponse(chemin, media_type=service.MEDIA_XLSX, filename=nom)
    if (m := RE_EXEMPLE_ZIP.match(nom)) and m.group(1) in service.INVENTAIRES:
        contenu = service.archive_production_exemple(m.group(1))
        if contenu:
            return Response(contenu, media_type="application/zip",
                            headers={"Content-Disposition": f'attachment; filename="{nom}"'})
    return JSONResponse({"erreur": "Fichier d'exemple introuvable."}, status_code=404)


async def api_introuvable(request: Request) -> Response:
    return JSONResponse({"erreur": "Ressource introuvable."}, status_code=404)


# ============================================================
# MIDDLEWARES
# ============================================================

class _SansAcceptEncoding:
    """
    Retire Accept-Encoding de la requête : les couches internes ne compressent
    plus rien. Retire aussi le « Vary: Accept-Encoding » qu'elles ajoutent quand
    même, pour que la couche GZip externe soit seule à le poser.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        entetes = [(k, v) for k, v in scope["headers"] if k.lower() != b"accept-encoding"]

        async def envoyer(message: Message) -> None:
            if message["type"] == "http.response.start":
                reponse = MutableHeaders(scope=message)
                if "vary" in reponse:
                    restants = [v.strip() for v in reponse["vary"].split(",")
                                if v.strip() and v.strip().lower() != "accept-encoding"]
                    del reponse["vary"]
                    if restants:
                        reponse["Vary"] = ", ".join(restants)
            await send(message)

        await self.app({**scope, "headers": entetes}, receive, envoyer)


class CompressionSelective:
    """
    GZip (≥ 1000 octets) pour les réponses texte de NOS routes, sauf le flux
    NDJSON, qui doit partir ligne par ligne. st.App ajoute sous nos middlewares
    son propre GZip, qui compresserait le flux : pour nos routes, on décide ici
    et on masque Accept-Encoding aux couches internes.
    """

    def __init__(self, app: ASGIApp, minimum_size: int = GZIP_TAILLE_MIN):
        self.app = app
        self.gzip = GZipMiddleware(
            _SansAcceptEncoding(app), minimum_size=minimum_size,
            exclude_content_types=DEFAULT_EXCLUDED_CONTENT_TYPES + EXCLUSIONS_GZIP)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and _est_route_appli(scope["path"]):
            await self.gzip(scope, receive, send)
        else:
            await self.app(scope, receive, send)


class EntetesStatiques:
    """En-têtes de sécurité sur nos routes ; cache adapté sur les fichiers de /assets."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        chemin = scope.get("path", "") if scope["type"] == "http" else None
        if chemin is None or not _est_route_appli(chemin):
            await self.app(scope, receive, send)
            return

        async def envoyer(message: Message) -> None:
            if message["type"] == "http.response.start":
                entetes = MutableHeaders(scope=message)
                for nom, valeur in ENTETES_SECURITE.items():
                    entetes.setdefault(nom, valeur)
                if chemin.startswith("/assets/") and message["status"] in (200, 304):
                    entetes.setdefault("Cache-Control", CACHE_CODE if chemin.endswith(EXTENSIONS_CODE) else CACHE_ASSETS)
            await send(message)

        await self.app(scope, receive, envoyer)


# ============================================================
# ASSEMBLAGE
# ============================================================

def creer_routes() -> list:
    """Routes à passer à st.App (elles passent avant les routes internes de Streamlit)."""
    routes: list[BaseRoute] = [
        Route("/", page_accueil, methods=["GET"]),
        Route("/api/inventaires", inventaires, methods=["GET"]),
        Route("/api/inventaires/{cle}", inventaire, methods=["GET"]),
        Route("/api/import", importer, methods=["POST"]),
        Route("/api/pipeline", lancer_pipeline, methods=["POST"]),
        Route("/api/executions/{identifiant}/fichiers/{nom}", telecharger_fichier, methods=["GET"]),
        Route("/api/executions/{identifiant}/archive.zip", telecharger_archive, methods=["GET"]),
        Route("/exemples/{nom}", exemple, methods=["GET"]),
        Mount("/assets", app=StaticFiles(directory=DOSSIER_ASSETS, check_dir=False), name="assets"),
        # Toute autre URL /api/... : 404 JSON plutôt que la page Streamlit de repli
        Route("/api/{chemin:path}", api_introuvable,
              methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]),
    ]
    return routes


def creer_middlewares() -> list:
    """Middlewares à passer à st.App (ils enveloppent ceux de Streamlit)."""
    return [Middleware(EntetesStatiques), Middleware(CompressionSelective)]
