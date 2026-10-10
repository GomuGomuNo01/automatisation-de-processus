"""
Tests des automatisations web sans navigateur (webapp/navigateur.py)
Lancer : pytest tests/test_navigateur.py -v

Aucun accès réseau : le HTML reproduit la structure des deux sites de test.
"""

import pytest

from webapp import navigateur

PAGE_PRODUITS = """
<div class="row">
  <div class="col-md-4">
    <div class="card thumbnail">
      <div class="caption">
        <h4 class="price float-end"><span itemprop="price">$69.99</span></h4>
        <h4><a href="/p/10" class="title" title="Lenovo IdeaTab">Lenovo IdeaTab</a></h4>
        <p class="description card-text">7&quot; screen, Android</p>
      </div>
      <div class="ratings">
        <p class="review-count">7 reviews</p>
        <p data-rating="3"><span class="ws-icon ws-icon-star"></span><span class="ws-icon ws-icon-star"></span><span class="ws-icon ws-icon-star"></span></p>
      </div>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card thumbnail">
      <h4 class="price">$24.99</h4>
      <h4><a class="title" title="Nokia 123">Nokia 123</a></h4>
      <p class="description">7 day battery</p>
      <div class="ratings"><p><span class="glyphicon glyphicon-star"></span><span class="glyphicon glyphicon-star"></span></p></div>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card thumbnail"><h4 class="price">$1.00</h4><p class="description">Sans titre : ignoré</p></div>
  </div>
</div>
"""

PAGE_FORMULAIRE = """
<form method="get" action="submitted-form.html">
  <input type="text" name="my-text">
  <input type="password" name="my-password">
  <textarea name="my-textarea"></textarea>
  <input type="text" name="my-disabled" value="x" disabled>
  <input type="text" name="my-readonly" value="Readonly input" readonly>
  <select name="my-select">
    <option selected>Open this select menu</option>
    <option value="1">One</option>
    <option value="2">Two</option>
  </select>
  <input name="my-datalist" list="opts"><datalist id="opts"><option value="Paris"></datalist>
  <input type="checkbox" name="my-check" checked>
  <input type="checkbox" name="my-check">
  <input type="radio" name="my-radio" checked>
  <input type="file" name="my-file">
  <input type="range" name="my-range" value="5">
  <button type="submit">Submit</button>
</form>
"""


class TestScraping:
    def test_produits_extraits_comme_selenium(self):
        produits = navigateur.extraire_produits(PAGE_PRODUITS)
        assert produits == [
            {"Produit": "Lenovo IdeaTab", "Prix": "$69.99", "Description": '7" screen, Android', "Note (/ 5)": 3},
            {"Produit": "Nokia 123", "Prix": "$24.99", "Description": "7 day battery", "Note (/ 5)": 2},
        ]

    def test_produit_incomplet_ignore(self):
        assert all(p["Description"] != "Sans titre : ignoré" for p in navigateur.extraire_produits(PAGE_PRODUITS))

    def test_page_sans_produit(self):
        assert navigateur.extraire_produits("<html><body><p>Rien</p></body></html>") == []

    def test_html_mal_ferme_tolere(self):
        html = '<div class="thumbnail"><span class="price">$5<h4><a class="title" title="A">A</a><p class="description">d'
        assert navigateur.extraire_produits(html)[0]["Produit"] == "A"


class TestFormulaire:
    def test_valeurs_envoyees_par_defaut(self):
        action, methode, champs = navigateur.lire_formulaire(PAGE_FORMULAIRE)
        valeurs = [(c.nom, c.valeur) for c in champs]
        assert action == "submitted-form.html"
        assert methode == "get"
        assert ("my-readonly", "Readonly input") in valeurs          # lecture seule : envoyé
        assert all(nom != "my-disabled" for nom, _ in valeurs)       # désactivé : jamais envoyé
        assert ("my-select", "Open this select menu") in valeurs     # option sélectionnée, sans value
        assert valeurs.count(("my-check", "on")) == 1                # seule la case cochée
        assert ("my-radio", "on") in valeurs
        assert ("my-file", "") in valeurs
        assert ("my-range", "5") in valeurs

    def test_select_par_texte_visible(self):
        assert navigateur._valeur_select(PAGE_FORMULAIRE, "my-select", "Two") == "2"

    def test_option_absente(self):
        with pytest.raises(ValueError):
            navigateur._valeur_select(PAGE_FORMULAIRE, "my-select", "Four")

    def test_page_sans_formulaire(self):
        with pytest.raises(ValueError):
            navigateur.lire_formulaire("<p>Pas de formulaire</p>")

    def test_soumission_reussie_si_page_de_confirmation(self):
        s = navigateur.Soumission("u", "r", 200, "Form submitted", "Received!", [], 10)
        assert s.reussie
        assert not navigateur.Soumission("u", "r", 200, "Web form", "", [], 10).reussie
