"""
Tests des routes HTTP de l'interface web (webapp/api.py)
Lancer : pytest tests/test_api.py -v

Les routes et middlewares sont montés dans une application Starlette
simple, avec en dessous le GZip interne de Streamlit, comme le fait st.App.
"""

import io
import json
import zipfile

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.testclient import TestClient

from webapp import api, navigateur, service

try:  # GZip qu'ajoute st.App sous nos middlewares (module interne de Streamlit)
    from streamlit.web.server.starlette.starlette_gzip_middleware import SelectiveGZipMiddleware
    MIDDLEWARES_STREAMLIT = [Middleware(SelectiveGZipMiddleware, minimum_size=1000)]
except ImportError:  # pragma: no cover
    MIDDLEWARES_STREAMLIT = []

LIGNES = [{"produit": "Hub USB", "quantite": 5, "seuil": 8}, {"produit": "Cable", "quantite": 35, "seuil": 20}]
REQUETE = {"source": "exemple", "inventaire": "gaming_multimedia", "lignes": LIGNES, "mode": "TEST",
           "seuil_formulaire": 1, "cas": {"rapport": True, "scraping": True}}


@pytest.fixture(autouse=True)
def hors_ligne(monkeypatch):
    monkeypatch.setattr(navigateur, "soumettre_formulaire", lambda url, d: navigateur.Soumission(
        url, url, 200, "Form submitted", "Received!", [("Texte", d["texte"])], 5))
    monkeypatch.setattr(navigateur, "scraper", lambda url: (
        [{"Produit": "P", "Prix": "$1.00", "Description": "d", "Note (/ 5)": 1}], navigateur.Page(url, 200, "", 3)))
    monkeypatch.setattr(service, "_cache_scraping", {})


@pytest.fixture
def client():
    appli = Starlette(routes=api.creer_routes(), middleware=api.creer_middlewares() + MIDDLEWARES_STREAMLIT)
    return TestClient(appli)


def lire_ndjson(reponse) -> list:
    assert reponse.text.endswith("\n")
    return [json.loads(ligne) for ligne in reponse.text.splitlines()]


class TestPages:
    def test_index(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert r.headers["x-content-type-options"] == "nosniff"
        assert "Relais" in r.text

    def test_css_revalide(self, client):
        r = client.get("/assets/css/tokens.css")
        assert r.status_code == 200
        assert r.headers["cache-control"] == "no-cache"

    def test_police_cache_long(self, client):
        r = client.get("/assets/fonts/Geist-latin.woff2")
        assert r.status_code == 200
        assert "max-age" in r.headers["cache-control"]

    def test_texte_compresse(self, client):
        r = client.get("/assets/js/demo.js", headers={"Accept-Encoding": "gzip"})
        assert r.headers.get("content-encoding") == "gzip"

    def test_api_inconnue_404_json(self, client):
        r = client.get("/api/nimporte/quoi")
        assert r.status_code == 404
        assert r.json() == {"erreur": "Ressource introuvable."}


class TestInventaires:
    def test_liste(self, client):
        donnees = client.get("/api/inventaires").json()
        assert len(donnees["inventaires"]) == 3
        assert donnees["seuil_formulaire"] == service.config.SEUIL_FORMULAIRE

    def test_detail(self, client):
        donnees = client.get("/api/inventaires/stockage_securite").json()
        assert len(donnees["lignes"]) == 20
        assert donnees["production"] == ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]

    def test_inconnu(self, client):
        assert client.get("/api/inventaires/inconnu").status_code == 404

    @pytest.mark.parametrize("nom", ["inventaire_gaming_multimedia.xlsx", "production_stockage_securite.zip"])
    def test_exemples(self, client, nom):
        assert client.get(f"/exemples/{nom}").status_code == 200

    @pytest.mark.parametrize("nom", ["inventaire_inconnu.xlsx", "..%2Fconfig.py", ".env", "production_x.zip"])
    def test_exemples_hors_liste_404(self, client, nom):
        assert client.get(f"/exemples/{nom}").status_code == 404


class TestImport:
    def test_inventaire_et_production(self, client):
        r = client.post("/api/import", files=[
            ("inventaire", ("stock.csv", b"Produit,Quantite,Seuil_Minimum\nA,1,5\n", "text/csv")),
            ("production", ("Lundi.csv", b"Produit,Quantite_Produite,Ligne_Production\nA,3,L1\n", "text/csv")),
        ])
        assert r.status_code == 200
        donnees = r.json()
        assert donnees["nom"] == "stock.csv"
        assert donnees["lignes"] == [{"produit": "A", "quantite": 1, "seuil": 5}]
        assert donnees["production"][0]["jour"] == "Lundi"

    def test_sans_fichier(self, client):
        r = client.post("/api/import", data={"x": "1"})
        assert r.status_code == 422
        assert "fichier" in r.json()["erreurs"]

    def test_fichier_invalide(self, client):
        r = client.post("/api/import", files={"inventaire": ("stock.csv", b"a,b\n1,2\n", "text/csv")})
        assert r.status_code == 422
        assert "manquante" in r.json()["erreurs"]["fichier"]

    def test_trop_volumineux(self, client):
        gros = b"x" * (api.TAILLE_MAX_IMPORT + 10)
        r = client.post("/api/import", files={"inventaire": ("stock.csv", gros, "text/csv")})
        assert r.status_code == 422


class TestPipeline:
    def test_flux_ndjson_et_telechargements(self, client):
        r = client.post("/api/pipeline", json=REQUETE, headers={"Accept-Encoding": "gzip"})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith(api.MEDIA_NDJSON)
        assert "content-encoding" not in r.headers          # le flux n'est jamais compressé
        assert r.headers["cache-control"] == "no-store"
        evenements = lire_ndjson(r)
        assert evenements[0]["type"] == "debut"
        fin = evenements[-1]
        assert fin["type"] == "fin"
        assert len(fin["fichiers"]) == 4

        for fichier in fin["fichiers"]:
            telechargement = client.get("/" + fichier["url"])
            assert telechargement.status_code == 200
            assert fichier["nom"] in telechargement.headers["content-disposition"]
            assert len(telechargement.content) == fichier["taille"]

        archive = client.get("/" + fin["archive"]["url"])
        assert archive.headers["content-type"] == "application/zip"
        with zipfile.ZipFile(io.BytesIO(archive.content)) as zf:
            assert sorted(zf.namelist()) == sorted(f["nom"] for f in fin["fichiers"])

    def test_requete_invalide(self, client):
        r = client.post("/api/pipeline", json={**REQUETE, "seuil_formulaire": 99})
        assert r.status_code == 422
        assert "seuil_formulaire" in r.json()["erreurs"]

    def test_json_illisible(self, client):
        r = client.post("/api/pipeline", content=b"{pas du json", headers={"Content-Type": "application/json"})
        assert r.status_code == 422

    def test_corps_trop_volumineux(self, client):
        r = client.post("/api/pipeline", content=b" " * (api.TAILLE_MAX_JSON + 1),
                        headers={"Content-Type": "application/json"})
        assert r.status_code == 422

    @pytest.mark.parametrize("chemin", [
        "/api/executions/123/fichiers/a.xlsx",
        "/api/executions/" + "0" * 32 + "/fichiers/a.xlsx",
        "/api/executions/" + "0" * 32 + "/archive.zip",
    ])
    def test_execution_inconnue(self, client, chemin):
        r = client.get(chemin)
        assert r.status_code == 404
        assert "erreur" in r.json()

    def test_fichier_hors_execution(self, client):
        fin = lire_ndjson(client.post("/api/pipeline", json=REQUETE))[-1]
        r = client.get(f"/api/executions/{fin['id']}/fichiers/..%2F..%2Fconfig.py")
        assert r.status_code == 404
