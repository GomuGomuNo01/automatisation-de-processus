"""
navigateur.py — Cas 5 et Cas 6 sans navigateur, pour la version en ligne

Les hébergeurs gratuits (Streamlit Community Cloud, Render) n'ont pas Chrome :
Selenium y est inutilisable. Ce module refait donc les deux automatisations web
avec de simples requêtes HTTP, en lisant le même HTML que Selenium :

  - Cas 5 : mêmes sélecteurs que scripts/cas5_scraping.py (.thumbnail, .title,
    .price, .description, note) sur la même page e-commerce ;
  - Cas 6 : le formulaire est lu, rempli champ par champ et soumis comme le
    ferait le navigateur (valeurs par défaut comprises), puis la page de
    confirmation est vérifiée.

En local, la ligne de commande continue d'utiliser Selenium et Chrome.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Iterator, Optional

DELAI_RESEAU = 12  # secondes
TAILLE_MAX_PAGE = 2 * 1024 * 1024
ENTETES = {
    "User-Agent": "Mozilla/5.0 (compatible; RelaisDemo/1.0; automatisation-de-processus)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

ELEMENTS_VIDES = {"area", "base", "br", "col", "embed", "hr", "img", "input",
                  "link", "meta", "source", "track", "wbr"}


class ErreurReseau(Exception):
    """La page n'a pas pu être téléchargée (réseau, délai, code HTTP)."""


# ============================================================
# MINI-DOM : arbre HTML et sélection par classe / attribut
# ============================================================

@dataclass
class Element:
    tag: str
    attrs: dict = field(default_factory=dict)
    enfants: list = field(default_factory=list)   # Element ou str
    parent: Optional["Element"] = None

    @property
    def classes(self) -> set:
        return set((self.attrs.get("class") or "").split())

    def texte(self) -> str:
        morceaux = []
        for enfant in self.enfants:
            morceaux.append(enfant if isinstance(enfant, str) else enfant.texte())
        return " ".join(" ".join(morceaux).split())

    def descendants(self) -> Iterator["Element"]:
        for enfant in self.enfants:
            if isinstance(enfant, Element):
                yield enfant
                yield from enfant.descendants()

    def tous(self, tag: Optional[str] = None, classe: Optional[str] = None,
             attribut: Optional[str] = None) -> list:
        return [e for e in self.descendants()
                if (tag is None or e.tag == tag)
                and (classe is None or classe in e.classes)
                and (attribut is None or attribut in e.attrs)]

    def premier(self, tag: Optional[str] = None, classe: Optional[str] = None,
                attribut: Optional[str] = None) -> Optional["Element"]:
        trouves = self.tous(tag, classe, attribut)
        return trouves[0] if trouves else None


class _Constructeur(HTMLParser):
    """Construit l'arbre en tolérant les balises mal fermées."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.racine = Element("#document")
        self.pile = [self.racine]

    def handle_starttag(self, tag, attrs):
        element = Element(tag, {k: (v if v is not None else "") for k, v in attrs}, parent=self.pile[-1])
        self.pile[-1].enfants.append(element)
        if tag not in ELEMENTS_VIDES:
            self.pile.append(element)

    def handle_startendtag(self, tag, attrs):
        element = Element(tag, {k: (v if v is not None else "") for k, v in attrs}, parent=self.pile[-1])
        self.pile[-1].enfants.append(element)

    def handle_endtag(self, tag):
        for i in range(len(self.pile) - 1, 0, -1):
            if self.pile[i].tag == tag:
                del self.pile[i:]
                return

    def handle_data(self, data):
        if data.strip():
            self.pile[-1].enfants.append(data)


def analyser(html: str) -> Element:
    constructeur = _Constructeur()
    constructeur.feed(html)
    constructeur.close()
    return constructeur.racine


# ============================================================
# HTTP
# ============================================================

@dataclass
class Page:
    url: str
    statut: int
    html: str
    duree_ms: int


def telecharger(url: str) -> Page:
    debut = time.perf_counter()
    requete = urllib.request.Request(url, headers=ENTETES)
    try:
        with urllib.request.urlopen(requete, timeout=DELAI_RESEAU) as reponse:
            corps = reponse.read(TAILLE_MAX_PAGE + 1)
            if len(corps) > TAILLE_MAX_PAGE:
                raise ErreurReseau("Page trop volumineuse.")
            encodage = reponse.headers.get_content_charset() or "utf-8"
            return Page(reponse.geturl(), reponse.status, corps.decode(encodage, errors="replace"),
                        round((time.perf_counter() - debut) * 1000))
    except urllib.error.HTTPError as e:
        raise ErreurReseau(f"Le site a répondu HTTP {e.code}.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErreurReseau("Site injoignable ou trop lent.") from e


# ============================================================
# CAS 5 — SCRAPING
# ============================================================

def _note(carte: Element) -> int:
    """Note sur 5 : attribut data-rating, sinon nombre d'étoiles affichées."""
    notation = carte.premier(attribut="data-rating")
    if notation is not None:
        try:
            return int(notation.attrs["data-rating"])
        except ValueError:
            pass
    ratings = carte.premier(classe="ratings")
    if ratings is None:
        return 0
    return len([e for e in ratings.descendants() if e.classes & {"ws-icon-star", "glyphicon-star"}])


def extraire_produits(html: str) -> list:
    """Les produits d'une page de la boutique de test webscraper.io."""
    produits = []
    for carte in analyser(html).tous(classe="thumbnail"):
        titre = carte.premier(classe="title")
        prix = carte.premier(classe="price")
        description = carte.premier(classe="description")
        if titre is None or prix is None or description is None:
            continue  # même règle que Selenium : NoSuchElementException → produit ignoré
        produits.append({
            "Produit":     titre.attrs.get("title") or titre.texte(),
            "Prix":        prix.texte(),
            "Description": description.texte(),
            "Note (/ 5)":  _note(carte),
        })
    return produits


def scraper(url: str) -> tuple:
    """(produits, page) — lève ErreurReseau si la page est inaccessible."""
    page = telecharger(url)
    return extraire_produits(page.html), page


# ============================================================
# CAS 6 — FORMULAIRE
# ============================================================

@dataclass
class Champ:
    nom: str
    type: str
    valeur: str


def _options(select: Element) -> list:
    """(valeur, texte visible, sélectionnée) de chaque <option>."""
    resultat = []
    for option in select.tous("option"):
        texte = option.texte()
        valeur = option.attrs["value"] if "value" in option.attrs else texte
        resultat.append((valeur, texte, "selected" in option.attrs))
    return resultat


def lire_formulaire(html: str) -> tuple:
    """
    (action, méthode, champs) du premier formulaire, avec les valeurs qu'un
    navigateur enverrait sans intervention (cases cochées, option sélectionnée…).
    Les champs désactivés ne sont jamais envoyés.
    """
    formulaire = analyser(html).premier("form")
    if formulaire is None:
        raise ValueError("Aucun formulaire trouvé sur la page.")
    action = formulaire.attrs.get("action", "")
    methode = (formulaire.attrs.get("method") or "get").lower()

    champs = []
    for element in formulaire.descendants():
        nom = element.attrs.get("name")
        if not nom or "disabled" in element.attrs:
            continue
        if element.tag == "input":
            type_ = (element.attrs.get("type") or "text").lower()
            if type_ in ("submit", "button", "reset", "image"):
                continue
            if type_ in ("checkbox", "radio"):
                if "checked" in element.attrs:
                    champs.append(Champ(nom, type_, element.attrs.get("value") or "on"))
                continue
            champs.append(Champ(nom, type_, "" if type_ == "file" else element.attrs.get("value", "")))
        elif element.tag == "textarea":
            champs.append(Champ(nom, "textarea", element.texte()))
        elif element.tag == "select":
            options = _options(element)
            choisie = next((o for o in options if o[2]), options[0] if options else ("", "", False))
            champs.append(Champ(nom, "select", choisie[0]))
    return action, methode, champs


def _valeur_select(html: str, nom: str, texte_visible: str) -> str:
    """Équivalent de Select(...).select_by_visible_text(texte) : la valeur de l'option."""
    for select in analyser(html).tous("select"):
        if select.attrs.get("name") == nom:
            for valeur, texte, _ in _options(select):
                if texte == texte_visible:
                    return valeur
    raise ValueError(f"Option « {texte_visible} » introuvable dans la liste « {nom} ».")


@dataclass
class Soumission:
    url_formulaire: str
    url_resultat: str
    statut: int
    titre: str
    message: str
    saisies: list         # [(libellé, valeur affichée)]
    duree_ms: int

    @property
    def reussie(self) -> bool:
        return self.statut == 200 and "submitted" in self.titre.lower()


def soumettre_formulaire(url: str, donnees: dict) -> Soumission:
    """
    Même saisie que scripts/cas6_formulaire.py : my-text, my-password,
    my-textarea et my-select (par texte visible), puis envoi du formulaire.
    """
    debut = time.perf_counter()
    page = telecharger(url)
    action, methode, champs = lire_formulaire(page.html)

    saisie = {
        "my-text":     donnees["texte"],
        "my-password": donnees["mot_de_passe"],
        "my-textarea": donnees["zone_texte"],
        "my-select":   _valeur_select(page.html, "my-select", donnees["liste_deroulante"]),
    }
    noms = {c.nom for c in champs}
    manquants = [nom for nom in saisie if nom not in noms]
    if manquants:
        raise ValueError(f"Champ(s) introuvable(s) dans le formulaire : {', '.join(manquants)}.")
    paires = [(c.nom, saisie.get(c.nom, c.valeur)) for c in champs]

    cible = urllib.parse.urljoin(page.url, action or page.url)
    corps = urllib.parse.urlencode(paires)
    if methode == "post":
        requete = urllib.request.Request(cible, data=corps.encode("utf-8"), headers={
            **ENTETES, "Content-Type": "application/x-www-form-urlencoded"})
    else:
        requete = urllib.request.Request(f"{cible}?{corps}", headers=ENTETES)
    try:
        with urllib.request.urlopen(requete, timeout=DELAI_RESEAU) as reponse:
            html = reponse.read(TAILLE_MAX_PAGE).decode(reponse.headers.get_content_charset() or "utf-8", errors="replace")
            statut = reponse.status
            url_resultat = reponse.geturl()
    except urllib.error.HTTPError as e:
        raise ErreurReseau(f"Le site a répondu HTTP {e.code} à l'envoi.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErreurReseau("Site du formulaire injoignable ou trop lent.") from e

    resultat = analyser(html)
    titre = resultat.premier("h1")
    message = next((e for e in resultat.descendants() if e.attrs.get("id") == "message"), None)
    return Soumission(
        url_formulaire=page.url,
        # Le mot de passe voyage dans l'URL (formulaire GET) : on ne l'affiche pas
        url_resultat=url_resultat.split("?", 1)[0],
        statut=statut,
        titre=titre.texte() if titre else "",
        message=message.texte() if message else "",
        saisies=[
            ("Texte", donnees["texte"]),
            ("Mot de passe", "•" * len(donnees["mot_de_passe"])),
            ("Zone de texte", donnees["zone_texte"]),
            ("Liste déroulante", donnees["liste_deroulante"]),
        ],
        duree_ms=round((time.perf_counter() - debut) * 1000),
    )
