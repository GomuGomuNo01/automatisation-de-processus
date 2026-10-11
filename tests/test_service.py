"""
Tests du pipeline web (webapp/service.py) et des fonctions extraites des scripts
Lancer : pytest tests/test_service.py -v

Le réseau est remplacé par des doublures : les tests ne dépendent ni de
webscraper.io ni de selenium.dev.
"""

import email
import io
import zipfile

import pandas as pd
import pytest

from webapp import navigateur, service

LIGNES = [
    {"produit": "Hub USB", "quantite": 5, "seuil": 8},
    {"produit": "Cable HDMI", "quantite": 35, "seuil": 20},
    {"produit": "Ruban", "quantite": 0, "seuil": 10},
    {"produit": "Pile AA", "quantite": 20, "seuil": 20},   # égal au seuil : rupture
]


def requete(**surcharges) -> dict:
    base = {"source": "exemple", "inventaire": "consommables_bureau", "lignes": LIGNES,
            "mode": "TEST", "seuil_formulaire": 3, "cas": {"rapport": True, "scraping": True}}
    return {**base, **surcharges}


@pytest.fixture
def reseau(monkeypatch):
    """Formulaire et scraping simulés ; garde la trace des appels."""
    appels = {"formulaire": 0, "scraping": 0}

    def soumettre(url, donnees):
        appels["formulaire"] += 1
        return navigateur.Soumission(url, url.replace("web-form", "submitted-form"), 200, "Form submitted",
                                     "Received!", [("Texte", donnees["texte"])], 42)

    def scraper(url):
        appels["scraping"] += 1
        produits = [{"Produit": "Tablette", "Prix": "$99.99", "Description": "10 pouces", "Note (/ 5)": 4}]
        return produits, navigateur.Page(url, 200, "", 12)

    monkeypatch.setattr(navigateur, "soumettre_formulaire", soumettre)
    monkeypatch.setattr(navigateur, "scraper", scraper)
    monkeypatch.setattr(service, "_cache_scraping", {})
    return appels


def executer(donnees: dict) -> list:
    evenements = []
    service.executer_pipeline(service.valider_requete(donnees), evenements.append)
    return evenements


def etapes(evenements) -> dict:
    return {e["cle"]: e for e in evenements if e["type"] == "etape" and e["etat"] != "en_cours"}


# ============================================================
# FONCTIONS DES SCRIPTS (partagées avec la ligne de commande)
# ============================================================

class TestScripts:
    def test_rupture_si_quantite_inferieure_ou_egale_au_seuil(self):
        df = pd.DataFrame({"Produit": ["a", "b", "c"], "Quantite": [1, 5, 9], "Seuil_Minimum": [5, 5, 5]})
        alertes = service.cas1_stock.detecter_ruptures(df)
        assert list(alertes["Produit"]) == ["a", "b"]
        assert set(alertes["Statut"]) == {"RUPTURE"}

    def test_fusion_dans_l_ordre_de_la_semaine(self):
        jour = lambda q: pd.DataFrame({"Produit": ["x"], "Quantite_Produite": [q], "Ligne_Production": ["L1"]})
        detail, recap = service.cas2_fusion.fusionner([("Jeudi", jour(4)), ("lundi", jour(1)), ("Mardi", jour(2))])
        assert list(detail["Jour"]) == ["Lundi", "Mardi", "Jeudi"]
        assert recap.iloc[0]["Total_Semaine"] == 7

    def test_email_echappe_les_noms_de_produits(self):
        alertes = pd.DataFrame({"Produit": ["<script>x</script> & co"], "Quantite": [1], "Seuil_Minimum": [2]})
        html = service.cas3_email._construire_html(alertes)
        assert "<script>" not in html
        assert "&lt;script&gt;x&lt;/script&gt; &amp; co" in html


# ============================================================
# INVENTAIRES ET IMPORT
# ============================================================

class TestInventaires:
    def test_trois_exemples(self):
        cles = [i["cle"] for i in service.lister_inventaires()]
        assert cles == ["gaming_multimedia", "consommables_bureau", "stockage_securite"]

    def test_nombre_de_ruptures_des_exemples(self):
        ruptures = {i["cle"]: i["ruptures"] for i in service.lister_inventaires()}
        assert ruptures == {"gaming_multimedia": 12, "consommables_bureau": 7, "stockage_securite": 9}

    def test_inventaire_inconnu(self):
        assert service.lire_inventaire("../config") is None

    def test_archive_production(self):
        with zipfile.ZipFile(io.BytesIO(service.archive_production_exemple("gaming_multimedia"))) as zf:
            assert len(zf.namelist()) == 5


class TestImport:
    def test_csv_point_virgule_et_entetes_accentues(self):
        contenu = "Produit;Quantité;Seuil minimum\nPapier;2;10\nToner;15;5\n".encode("utf-8")
        assert service.importer_inventaire("stock.csv", contenu) == [
            {"produit": "Papier", "quantite": 2, "seuil": 10},
            {"produit": "Toner", "quantite": 15, "seuil": 5},
        ]

    def test_xlsx(self):
        tampon = io.BytesIO()
        pd.DataFrame({"Produit": ["A"], "Quantite": [3], "Seuil_Minimum": [4]}).to_excel(tampon, index=False)
        assert service.importer_inventaire("stock.xlsx", tampon.getvalue())[0]["quantite"] == 3

    @pytest.mark.parametrize("nom, contenu, extrait", [
        ("stock.txt", b"x", "formats acceptés"),
        ("stock.csv", b"Produit,Quantite\nA,1\n", "Seuil_Minimum"),
        ("stock.csv", b"Produit,Quantite,Seuil_Minimum\nA,beaucoup,1\n", "n'est pas un nombre"),
        ("stock.csv", b"Produit,Quantite,Seuil_Minimum\nA,1.5,1\n", "entier"),
        ("stock.csv", b"Produit,Quantite,Seuil_Minimum\nA,-1,1\n", "hors limites"),
        ("stock.csv", b"Produit,Quantite,Seuil_Minimum\n", "aucun produit"),
        ("stock.xlsx", b"pas un classeur", "illisible"),
    ])
    def test_erreurs_explicites(self, nom, contenu, extrait):
        with pytest.raises(service.ErreurValidation) as e:
            service.importer_inventaire(nom, contenu)
        assert extrait in e.value.erreurs["fichier"]

    def test_trop_de_produits(self):
        lignes = "".join(f"P{i},1,1\n" for i in range(service.MAX_PRODUITS + 1))
        with pytest.raises(service.ErreurValidation):
            service.importer_inventaire("stock.csv", ("Produit,Quantite,Seuil_Minimum\n" + lignes).encode())

    def test_production_triee_par_jour(self):
        csv = b"Produit,Quantite_Produite,Ligne_Production\nA,10,L1\n"
        journees = service.importer_production([("Mardi.csv", csv), ("lundi.csv", csv)])
        assert [j["jour"] for j in journees] == ["Lundi", "Mardi"]

    def test_production_mauvais_format(self):
        with pytest.raises(service.ErreurValidation) as e:
            service.importer_production([("Lundi.xlsx", b"x")])
        assert "production" in e.value.erreurs


# ============================================================
# VALIDATION DE LA REQUÊTE
# ============================================================

class TestValidation:
    def test_requete_valide(self):
        r = service.valider_requete(requete())
        assert r.nom_inventaire == "inventaire_consommables_bureau.xlsx"
        assert r.rapport and r.scraping

    @pytest.mark.parametrize("surcharge, champ", [
        ({"source": "autre"}, "source"),
        ({"inventaire": "inconnu"}, "inventaire"),
        ({"lignes": []}, "lignes"),
        ({"lignes": [{"produit": "A", "quantite": True, "seuil": 1}]}, "lignes"),
        ({"lignes": [{"produit": "A", "quantite": -1, "seuil": 1}]}, "lignes"),
        ({"lignes": [{"produit": " ", "quantite": 1, "seuil": 1}]}, "lignes"),
        ({"mode": "NUIT"}, "mode"),
        ({"seuil_formulaire": 0}, "seuil_formulaire"),
        ({"seuil_formulaire": 51}, "seuil_formulaire"),
        ({"seuil_formulaire": "3"}, "seuil_formulaire"),
    ])
    def test_erreurs(self, surcharge, champ):
        with pytest.raises(service.ErreurValidation) as e:
            service.valider_requete(requete(**surcharge))
        assert champ in e.value.erreurs

    def test_pas_un_objet(self):
        with pytest.raises(service.ErreurValidation):
            service.valider_requete([1, 2])

    def test_nom_de_fichier_importe_nettoye(self):
        r = service.valider_requete(requete(source="import", nom="..\\..\\secret/stock.xlsx"))
        assert r.nom_inventaire == "stock.xlsx"


# ============================================================
# PLANIFICATION (Cas 4)
# ============================================================

class TestPlanification:
    def test_test(self):
        plan = service.planifier("TEST")
        taches = {t["cle"]: t for t in plan["taches"]}
        assert taches["surveillance"]["prochaines"][:3] == [0, 60, 120]   # premier cycle immédiat
        assert taches["rapport"]["prochaines"][0] == 120
        assert taches["scraping"]["prochaines"][0] == 180
        assert plan["horizon_s"] == 600

    def test_production(self):
        plan = service.planifier("PROD")
        taches = {t["cle"]: t for t in plan["taches"]}
        assert taches["surveillance"]["prochaines"][1] == 3600
        assert taches["scraping"]["prochaines"][0] == 4 * 3600
        assert len(taches["rapport"]["prochaines"]) == 1                  # un vendredi par semaine
        assert "vendredi à 08:00" in taches["rapport"]["frequence"]


# ============================================================
# PIPELINE COMPLET
# ============================================================

class TestPipeline:
    def test_enchainement_complet(self, reseau):
        evenements = executer(requete())
        assert evenements[0]["type"] == "debut"
        assert evenements[-1]["type"] == "fin"
        resultats = etapes(evenements)
        assert [c for c in resultats] == ["cas1", "cas3", "cas6", "cas2", "cas5", "cas4"]
        assert all(e["etat"] == "termine" for e in resultats.values())
        assert resultats["cas1"]["valeur"] == 3
        assert reseau == {"formulaire": 1, "scraping": 1}

    def test_fichiers_identiques_a_la_ligne_de_commande(self, reseau):
        fin = executer(requete())[-1]
        noms = [f["nom"] for f in fin["fichiers"]]
        assert [n.split("_2")[0] for n in noms] == ["rapport_alerte", "alerte_stock", "rapport_semaine", "scraping_produits"]
        execution = service.CACHE_EXECUTIONS.obtenir(fin["id"])
        alerte = pd.read_excel(io.BytesIO(execution.fichiers[noms[0]].contenu))
        assert list(alerte.columns) == ["Produit", "Quantite", "Seuil_Minimum", "Statut"]
        assert list(alerte["Produit"]) == ["Hub USB", "Ruban", "Pile AA"]
        semaine = pd.read_excel(io.BytesIO(execution.fichiers[noms[2]].contenu), sheet_name=None)
        assert list(semaine) == ["Detail journalier", "Recapitulatif semaine"]

    def test_email_eml_avec_piece_jointe(self, reseau):
        fin = executer(requete())[-1]
        execution = service.CACHE_EXECUTIONS.obtenir(fin["id"])
        eml = next(f for f in execution.fichiers.values() if f.nom.endswith(".eml"))
        message = email.message_from_bytes(eml.contenu)
        assert message["Subject"].startswith("[ALERTE STOCK] 3 produit(s) en rupture")
        assert message["To"] == service.DESTINATAIRE_DEMO
        pieces = [p.get_filename() for p in message.walk() if p.get_filename()]
        assert pieces and pieces[0].startswith("rapport_alerte_")

    def test_sans_rupture_ni_email_ni_formulaire(self, reseau):
        lignes = [{"produit": "A", "quantite": 50, "seuil": 1}]
        resultats = etapes(executer(requete(lignes=lignes)))
        assert resultats["cas3"]["etat"] == "ignore"
        assert resultats["cas6"]["etat"] == "ignore"
        assert reseau["formulaire"] == 0

    def test_formulaire_seulement_au_dela_du_seuil(self, reseau):
        resultats = etapes(executer(requete(seuil_formulaire=4)))
        assert resultats["cas6"]["etat"] == "ignore"
        assert "3 < 4" in resultats["cas6"]["resume"]
        assert reseau["formulaire"] == 0

    def test_etapes_desactivees(self, reseau):
        resultats = etapes(executer(requete(cas={"rapport": False, "scraping": False})))
        assert resultats["cas2"]["etat"] == "ignore"
        assert resultats["cas5"]["etat"] == "ignore"
        assert reseau["scraping"] == 0

    def test_import_sans_production(self, reseau):
        resultats = etapes(executer(requete(source="import", nom="stock.csv")))
        assert resultats["cas2"]["etat"] == "ignore"
        assert "production" in resultats["cas2"]["resume"]

    def test_import_avec_production(self, reseau):
        production = [{"jour": "Lundi", "lignes": [{"produit": "A", "quantite": 7, "ligne": "L1"}]}]
        evenements = executer(requete(source="import", nom="stock.csv", production=production))
        donnees = next(e["donnees"] for e in evenements if e["type"] == "resultat" and e["cle"] == "cas2")
        assert donnees["produits"] == [{"produit": "A", "total": 7, "par_jour": [7]}]

    def test_formulaire_injoignable_n_arrete_pas_le_pipeline(self, reseau, monkeypatch):
        def panne(*_):
            raise navigateur.ErreurReseau("Site du formulaire injoignable ou trop lent.")
        monkeypatch.setattr(navigateur, "soumettre_formulaire", panne)
        evenements = executer(requete())
        resultats = etapes(evenements)
        assert resultats["cas6"]["etat"] == "erreur"
        assert resultats["cas5"]["etat"] == "termine"
        assert evenements[-1]["type"] == "fin"

    def test_scraping_copie_de_secours(self, reseau, monkeypatch):
        def panne(_):
            raise navigateur.ErreurReseau("Site injoignable ou trop lent.")
        monkeypatch.setattr(navigateur, "scraper", panne)
        evenements = executer(requete())
        donnees = next(e["donnees"] for e in evenements if e["type"] == "resultat" and e["cle"] == "cas5")
        assert donnees["source"] == "secours"
        assert donnees["produits"]
        assert etapes(evenements)["cas5"]["secours"] is True

    def test_scraping_mis_en_cache(self, reseau):
        executer(requete())
        executer(requete())
        assert reseau["scraping"] == 1

    def test_erreur_inattendue_signalee(self, reseau, monkeypatch):
        monkeypatch.setattr(service.cas1_stock, "detecter_ruptures", lambda df: 1 / 0)
        evenements = executer(requete())
        assert evenements[-1] == {"type": "erreur", "message": service.MESSAGE_ERREUR_INATTENDUE}


class TestCache:
    def test_expiration(self):
        cache = service.CacheExecutions(duree=-1)
        cache.ajouter(service.Execution("a" * 32, "x.zip"))
        assert cache.obtenir("a" * 32) is None

    def test_taille_maximale(self):
        cache = service.CacheExecutions(maximum=2)
        for i in range(3):
            cache.ajouter(service.Execution(str(i) * 32, "x.zip"))
        assert cache.obtenir("0" * 32) is None
        assert cache.obtenir("2" * 32) is not None


# ============================================================
# ENVOI RÉEL DE L'EMAIL (EMAIL_DESTINATAIRE / EMAIL_EXPEDITEUR saisis sur la page)
# ============================================================

def lignes_exemple(cle="consommables_bureau"):
    return [dict(l) for l in service.lire_inventaire(cle)["lignes"]]


def requete_email(**email):
    return requete(lignes=lignes_exemple(), email=email)


@pytest.fixture
def envoi_actif(monkeypatch):
    monkeypatch.setattr(service, "envoi_email_actif", lambda: True)
    monkeypatch.setattr(service.config, "EMAIL_EXPEDITEUR", "demo.relais@gmail.com")
    monkeypatch.setattr(service.config, "MOT_DE_PASSE_APP", "abcd efgh ijkl mnop")


def resultat_email(evenements) -> dict:
    return next(e["donnees"] for e in evenements if e["type"] == "resultat" and e["cle"] == "cas3")


class TestEmailValidation:
    @pytest.mark.parametrize("adresse, valide", [
        ("vous@exemple.com", True), ("prenom.nom+demo@gmail.com", True),
        ("x@y", False), ("a b@c.com", False), ("<a@b.com>", False),
        ("a@b.com\r\nBcc: z@z.com", False), ("a@b.com\n", False), ("a" * 250 + "@b.com", False),
    ])
    def test_format(self, adresse, valide):
        assert service.email_valide(adresse) is valide

    def test_requete_valide(self):
        r = service.valider_requete(requete_email(destinataire=" vous@exemple.com ", expediteur="moi@exemple.com"))
        assert (r.destinataire, r.expediteur) == ("vous@exemple.com", "moi@exemple.com")

    @pytest.mark.parametrize("email, champ", [
        ({"destinataire": "pas-une-adresse"}, "destinataire"),
        ({"destinataire": "vous@exemple.com", "expediteur": "moi@"}, "expediteur"),
        ({"expediteur": "moi@exemple.com"}, "destinataire"),
    ])
    def test_adresses_invalides(self, email, champ):
        with pytest.raises(service.ErreurValidation) as e:
            service.valider_requete(requete_email(**email))
        assert champ in e.value.erreurs

    def test_reserve_aux_inventaires_d_exemple(self):
        with pytest.raises(service.ErreurValidation) as e:
            service.valider_requete(requete(source="import", nom="x.csv", email={"destinataire": "vous@exemple.com"}))
        assert "réservé" in e.value.erreurs["destinataire"]

    def test_contenu_verrouille(self):
        lignes = lignes_exemple()
        lignes[0]["produit"] = "Achetez maintenant sur http://spam.example"
        with pytest.raises(service.ErreurValidation) as e:
            service.valider_requete(requete(lignes=lignes, email={"destinataire": "vous@exemple.com"}))
        assert "quantités" in e.value.erreurs["destinataire"]

    def test_quantites_modifiables(self):
        lignes = lignes_exemple()
        lignes[0]["quantite"] = 0
        assert service.valider_requete(requete(lignes=lignes, email={"destinataire": "vous@exemple.com"})).destinataire


class TestEmailEnvoi:
    def test_envoi_reel(self, reseau, envoi_actif, emails_envoyes):
        evenements = executer(requete_email(destinataire="vous@exemple.com", expediteur="moi@exemple.com"))
        donnees = resultat_email(evenements)
        assert donnees["envoi"]["etat"] == "envoye"
        assert etapes(evenements)["cas3"]["resume"] == "Email envoyé à vous@exemple.com"
        envoi = emails_envoyes[0]
        assert envoi["destinataire"] == "vous@exemple.com" and envoi["compte"] == "demo.relais@gmail.com"
        message = envoi["message"]
        assert message["To"] == "vous@exemple.com"
        assert message["Reply-To"] == "moi@exemple.com"
        assert "demo.relais@gmail.com" in message["From"]          # Gmail envoie depuis le compte de la démo
        assert [p.get_filename() for p in message.walk() if p.get_filename()][0].startswith("rapport_alerte_")

    def test_sans_destinataire_rien_n_est_envoye(self, reseau, envoi_actif, emails_envoyes):
        donnees = resultat_email(executer(requete()))
        assert donnees["envoi"]["etat"] == "non_demande"
        assert emails_envoyes == []

    def test_serveur_non_configure(self, reseau, monkeypatch, emails_envoyes):
        monkeypatch.setattr(service, "envoi_email_actif", lambda: False)
        donnees = resultat_email(executer(requete_email(destinataire="vous@exemple.com")))
        assert donnees["envoi"]["etat"] == "indisponible"
        assert emails_envoyes == []

    def test_compte_du_modele_non_configure(self, monkeypatch):
        monkeypatch.setattr(service.config, "EMAIL_EXPEDITEUR", "votre.adresse@gmail.com")
        monkeypatch.setattr(service.config, "MOT_DE_PASSE_APP", "xxxx xxxx xxxx xxxx")
        assert service.envoi_email_actif() is False

    def test_limite_par_visiteur(self, reseau, envoi_actif, monkeypatch, emails_envoyes):
        monkeypatch.setattr(service, "LIMITEUR_ENVOIS", service.LimiteurEnvois(par_visiteur=1))
        executer(requete_email(destinataire="a@exemple.com"))
        evenements = executer(requete_email(destinataire="b@exemple.com"))
        assert resultat_email(evenements)["envoi"]["etat"] == "refuse"
        assert "par heure" in resultat_email(evenements)["envoi"]["message"]
        assert len(emails_envoyes) == 1
        assert evenements[-1]["type"] == "fin"                    # le pipeline va quand même au bout

    def test_limite_par_destinataire_insensible_a_la_casse(self, reseau, envoi_actif, monkeypatch, emails_envoyes):
        monkeypatch.setattr(service, "LIMITEUR_ENVOIS", service.LimiteurEnvois(par_destinataire=1))
        executer(requete_email(destinataire="vous@exemple.com"))
        evenements = executer(requete_email(destinataire="VOUS@exemple.com"))
        assert resultat_email(evenements)["envoi"]["etat"] == "refuse"

    def test_echec_smtp(self, reseau, envoi_actif, monkeypatch):
        def panne(*_):
            raise OSError("connexion refusée")
        monkeypatch.setattr(service.cas3_email, "envoyer", panne)
        evenements = executer(requete_email(destinataire="vous@exemple.com"))
        assert resultat_email(evenements)["envoi"]["etat"] == "echec"
        assert etapes(evenements)["cas3"]["etat"] == "erreur"
        assert etapes(evenements)["cas6"]["etat"] == "termine"
        assert evenements[-1]["type"] == "fin"
