# Mettre l'application en ligne

Ce guide explique comment publier l'interface web pour que n'importe qui puisse tester le pipeline depuis un simple lien, sans Codespaces ni installation. Même démarche que pour [sales-report-automation](https://github.com/GomuGomuNo01/sales-report-automation) : Streamlit Community Cloud pour la démo gratuite, Docker pour les autres hébergeurs.

## En bref

| Hébergeur | Coût | Carte bancaire | Premier visiteur après une période calme | Verdict |
|---|---|---|---|---|
| **Streamlit Community Cloud** | 0 € | non | page « app endormie » à cliquer après 12 h, puis environ 1 minute | **Recommandé pour la démo** |
| **Render** (offre gratuite) | 0 € | non | environ 1 minute, ou rien avec le maintien en éveil | Alternative sans carte |
| **Google Cloud Run** | environ 0 € (quotas gratuits) | oui | quelques secondes | Le plus fluide |

## Ce dont l'application a besoin (partout)

- **Python 3.11 ou plus récent** (pandas 3). Sur Streamlit Cloud, choisir **3.12** dans *Advanced settings*.
- **Aucun secret** : sans fichier `.env`, `config.py` lit `.env.example`. L'interface web n'envoie jamais d'email (il se télécharge en `.eml`) ; rien à configurer.
- **Accès Internet sortant** vers `webscraper.io` (Cas 5) et `selenium.dev` (Cas 6). Si le site de scraping est injoignable, une copie récente du catalogue (`webapp/donnees/scraping_secours.json`) prend le relais et l'interface le signale.
- **Pas de Chrome** : en ligne, Cas 5 et 6 passent par des requêtes HTTP (`webapp/navigateur.py`) qui lisent les mêmes pages que Selenium.
- **Une seule instance** : les fichiers générés restent en mémoire une heure. Avec plusieurs instances, un lien de téléchargement pourrait arriver sur une autre instance.
- **Vérification de santé** : `/_stcore/health`.

---

## Option 1 : Streamlit Community Cloud (démo gratuite)

1. [share.streamlit.io](https://share.streamlit.io) > **Create app** > **Deploy a public app from GitHub**.
2. Dépôt `GomuGomuNo01/automatisation-de-processus`, branche `main`, fichier **`app.py`**.
3. Sous-domaine : par exemple `automatisation-de-processus-cedric` (les sous-domaines sont attribués au premier qui les prend).
4. **Advanced settings** > Python **3.12** > **Deploy**. L'installation prend 2 à 5 minutes la première fois ; chaque push sur `main` redéploie ensuite en quelques secondes.
5. Mettre l'adresse obtenue dans le README si elle diffère de `https://automatisation-de-processus-cedric.streamlit.app` :

   ```bash
   sed -i 's#https://automatisation-de-processus-cedric.streamlit.app#https://VOTRE-ADRESSE#g' README.md
   ```

**Après un push qui modifie une route du serveur** (`webapp/api.py` ou `app.py`) : redémarrer l'application (**Manage app** > **⋮** > **Reboot app**). Streamlit Cloud remplace les fichiers sans relancer le serveur : HTML, CSS et JS sont à jour tout de suite, mais les routes de l'API ne sont créées qu'au démarrage.

À savoir :
- l'application tourne dans une iframe, sous `/~/+/` : le frontend n'utilise que des adresses relatives et envoie à la page hôte le message `GUEST_READY` (dans [`main.js`](../webapp/static/assets/js/main.js)), sans lequel l'iframe reste masquée ;
- après 12 heures sans visite, Streamlit affiche une page « This app has gone to sleep ».

**Maintien en éveil** : le workflow [`reveil-streamlit.yml`](../.github/workflows/reveil-streamlit.yml) ouvre la démo dans un vrai navigateur toutes les 6 heures, clique sur le bouton de réveil si besoin et lance le pipeline. Il est **inactif tant que la variable `STREAMLIT_URL` n'existe pas** :
GitHub > dépôt > **Settings > Secrets and variables > Actions > Variables > New repository variable** > `STREAMLIT_URL` = l'adresse de la démo. Pour l'essayer : **Actions > Réveiller la démo Streamlit > Run workflow**.

---

## Option 2 : Render (gratuit, sans carte bancaire)

Le fichier [`render.yaml`](../render.yaml) décrit tout le déploiement (Docker, offre gratuite, région Francfort, vérification de santé, redéploiement à chaque push).

1. Créer un compte sur [render.com](https://render.com) avec son compte GitHub.
2. **New > Blueprint**, choisir le dépôt, puis **Apply**.
3. Adresse : `https://automatisation-de-processus.onrender.com` (Render ajoute un suffixe si le nom est pris).

Limites : mise en veille après 15 minutes sans visite (environ une minute de réveil), 0,1 CPU, 512 Mo. Le workflow [`garder-eveille.yml`](../.github/workflows/garder-eveille.yml) interroge la démo toutes les 10 minutes une fois la variable de dépôt `DEMO_URL` définie.

---

## Option 3 : Google Cloud Run

Dans **Cloud Shell** (bouton `>_` de la console Google Cloud), après avoir activé la facturation et créé une alerte budgétaire :

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
git clone https://github.com/GomuGomuNo01/automatisation-de-processus.git
cd automatisation-de-processus

gcloud run deploy automatisation-de-processus \
  --source . \
  --region europe-west9 \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 1 \
  --memory 1Gi \
  --cpu-boost
```

`--max-instances 1` à cause des fichiers gardés en mémoire ; `--min-instances 0` pour un coût nul sans visiteur (quelques secondes de démarrage au premier).

---

## Tester en local

```bash
pip install -r requirements.txt
streamlit run app.py                 # → http://localhost:8501
```

Avec Docker :

```bash
docker build -t relais .
docker run --rm -p 8501:8501 relais
```

Après la mise en ligne : ouvrir l'adresse, cliquer sur **Lancer le pipeline**, vérifier que les six étapes s'affichent une par une puis télécharger l'archive `.zip`.
