"""
Garde-fou commun : aucun test n'envoie de vrai email.

Le .env local peut contenir de vrais identifiants Gmail ; l'envoi SMTP est donc
remplacé, pour tous les tests, par un enregistreur (fixture `emails_envoyes`).
"""

import pytest

from webapp import service


@pytest.fixture(autouse=True)
def emails_envoyes(monkeypatch):
    envoyes = []

    def enregistrer(message, compte, mot_de_passe, destinataire):
        envoyes.append({"message": message, "compte": compte, "destinataire": destinataire})

    monkeypatch.setattr(service.cas3_email, "envoyer", enregistrer)
    monkeypatch.setattr(service, "LIMITEUR_ENVOIS", service.LimiteurEnvois())
    return envoyes
