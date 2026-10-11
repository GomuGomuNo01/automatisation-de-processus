/* ==========================================================================
   DÉMO INTERACTIVE : inventaire (exemple ou import), quantités modifiables,
   paramètres, et prévision en direct de ce que le pipeline va faire.
   La règle de détection est la même que côté serveur (Cas 1) :
   rupture si Quantite <= Seuil_Minimum. Le serveur reste l'autorité.
   ========================================================================== */

import { getJSON, postFormulaire, ErreurApi } from './api.js';
import { esc, icon, nombre, pluriel } from './format.js';
import { toast, announce } from './ui.js';

const QUANTITE_MAX = 1_000_000;
const SEUIL_MIN = 1;
const SEUIL_MAX = 50;
const TAILLE_MAX = 2 * 1024 * 1024;
const CATEGORIE_IMPORT = 'Téléphones tactiles';
// Même règle que le serveur (webapp/service.py) : une adresse simple, sans espace ni chevrons
const RE_EMAIL = /^[^@\s<>()[\]\\,;:"']+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$/;

const form = document.getElementById('demo-form');
const el = {
  choix: form.querySelector('[data-inventory-choices]'),
  import: form.querySelector('[data-import]'),
  importMessage: form.querySelector('[data-import-message]'),
  inputInventaire: form.querySelector('input[name="inventaire"]'),
  inputProduction: form.querySelector('input[name="production"]'),
  corps: form.querySelector('[data-inventory-body]'),
  compte: form.querySelector('[data-inventory-count]'),
  filtre: form.querySelector('[data-filter-ruptures]'),
  reset: form.querySelector('[data-action="reset-inventory"]'),
  seuil: form.querySelector('input[name="seuil_formulaire"]'),
  stepperSeuil: form.querySelector('[data-stepper]'),
  rapport: form.querySelector('input[name="rapport"]'),
  scraping: form.querySelector('input[name="scraping"]'),
  categorie: form.querySelector('[data-scraping-category]'),
  lancer: form.querySelector('[data-launch]'),
  prevRuptures: form.querySelector('[data-forecast-ruptures]'),
  prevTotal: form.querySelector('[data-forecast-total]'),
  prevListe: form.querySelector('[data-forecast-list]'),
  mail: form.querySelector('[data-mail-config]'),
  destinataire: form.querySelector('input[name="email_destinataire"]'),
  expediteur: form.querySelector('input[name="email_expediteur"]'),
  mailNote: form.querySelector('[data-mail-note]'),
  mailNoteTexte: form.querySelector('[data-mail-note-text]'),
};

const state = {
  inventaires: [],
  source: 'exemple',
  cle: null,
  nom: '',
  original: [],
  lignes: [],
  production: null,     // import uniquement
  importe: null,        // dernier import réussi { nom, lignes, production }
  pret: false,
  envoi: { actif: false, par_heure: 3, par_destinataire_jour: 2 },   // envoi réel de l'email, selon le serveur
};
const cacheInventaires = new Map();
let surLancement = () => {};
let chargement = null;   // promesse du premier chargement

const estRupture = (l) => l.quantite <= l.seuil;

/* ==========================================================================
   CHOIX DE L'INVENTAIRE
   ========================================================================== */
function carteChoix({ valeur, titre, desc, stats, coche, classe = '' }) {
  return `
    <label class="inv-choice ${classe}">
      <input class="inv-choice__input" type="radio" name="inventaire_choix" value="${esc(valeur)}"${coche ? ' checked' : ''}>
      <span class="inv-choice__card">
        <span class="inv-choice__top"><span class="inv-choice__title">${esc(titre)}</span><span class="inv-choice__radio" aria-hidden="true"></span></span>
        <span class="inv-choice__desc">${esc(desc)}</span>
        <span class="inv-choice__stats">${stats}</span>
      </span>
    </label>`;
}

function statsChoix(produits, ruptures) {
  return `<span class="chip chip--neutral">${pluriel(produits, 'produit')}</span>`
    + `<span class="chip ${ruptures ? 'chip--danger' : 'chip--ok'}">${icon(ruptures ? 'alert' : 'check')}${pluriel(ruptures, 'rupture')}</span>`;
}

function rendreChoix() {
  const importe = state.importe;
  el.choix.innerHTML = state.inventaires.map((inv) => carteChoix({
    valeur: inv.cle,
    titre: inv.titre,
    desc: inv.domaine,
    stats: statsChoix(inv.produits, inv.ruptures),
    coche: state.source === 'exemple' && state.cle === inv.cle,
  })).join('') + carteChoix({
    valeur: 'import',
    titre: importe ? importe.nom : 'Votre fichier',
    desc: importe ? 'Inventaire importé' : 'Importez un .xlsx ou .csv',
    stats: importe
      ? statsChoix(importe.lignes.length, importe.lignes.filter(estRupture).length)
      : `<span class="chip chip--signal">${icon('upload')}Importer</span>`,
    coche: state.source === 'import',
    classe: 'inv-choice--import',
  });
}

async function choisirExemple(cle) {
  state.source = 'exemple';
  state.cle = cle;
  el.import.hidden = true;
  const inv = state.inventaires.find((i) => i.cle === cle);
  el.categorie.textContent = inv ? `catalogue ${inv.categorie_scraping}` : 'catalogue en ligne';
  majBlocEmail();
  if (!cacheInventaires.has(cle)) {
    rendreChargement();
    try {
      cacheInventaires.set(cle, await getJSON(`api/inventaires/${encodeURIComponent(cle)}`));
    } catch (e) {
      afficherErreur('inventaires', e.message);
      return;
    }
  }
  if (state.source !== 'exemple' || state.cle !== cle) return;  // un autre choix est arrivé entre-temps
  const contenu = cacheInventaires.get(cle);
  state.nom = contenu.fichier;
  chargerLignes(contenu.lignes);
  state.production = null;
}

function choisirImport() {
  state.source = 'import';
  el.import.hidden = false;
  el.categorie.textContent = `catalogue ${CATEGORIE_IMPORT} (par défaut)`;
  majBlocEmail();
  if (state.importe) {
    state.nom = state.importe.nom;
    state.production = state.importe.production;
    chargerLignes(state.importe.lignes);
  } else {
    state.nom = '';
    state.production = null;
    chargerLignes([]);
    el.compte.textContent = 'Importez un fichier pour voir ses produits ici.';
  }
}

/* ==========================================================================
   TABLEAU MODIFIABLE
   ========================================================================== */
function chargerLignes(lignes) {
  state.original = lignes.map((l) => ({ ...l }));
  state.lignes = lignes.map((l) => ({ ...l }));
  rendreTableau();
  mettreAJour();
}

function rendreChargement() {
  el.corps.innerHTML = Array.from({ length: 4 }, () =>
    '<tr><td colspan="4"><span class="skeleton skeleton-line" aria-hidden="true"></span></td></tr>').join('');
  el.compte.textContent = 'Chargement de l\'inventaire…';
}

function puce(rupture) {
  return rupture
    ? `<span class="chip chip--danger">${icon('alert')}<span class="chip__text">Rupture</span></span>`
    : `<span class="chip chip--ok">${icon('check')}<span class="chip__text">OK</span></span>`;
}

function rendreTableau() {
  if (!state.lignes.length) {
    el.corps.innerHTML = `<tr><td class="inv-table__empty" colspan="4">${state.source === 'import' ? 'Aucun inventaire importé pour l\'instant.' : 'Inventaire vide.'}</td></tr>`;
    return;
  }
  el.corps.innerHTML = state.lignes.map((l, i) => {
    const nom = esc(l.produit);
    return `
      <tr data-index="${i}" class="${estRupture(l) ? 'is-rupture' : ''}">
        <td class="inv-table__product">${nom}<small>seuil ${nombre(l.seuil)}</small></td>
        <td class="col-center">
          <div class="stepper">
            <button class="stepper__btn" type="button" data-delta="-1" aria-label="Retirer 1 à ${nom}"${l.quantite <= 0 ? ' disabled' : ''}>${icon('minus', 'icon--sm')}</button>
            <input class="stepper__input" type="number" min="0" max="${QUANTITE_MAX}" step="1" inputmode="numeric" value="${l.quantite}" aria-label="Quantité de ${nom}">
            <button class="stepper__btn" type="button" data-delta="1" aria-label="Ajouter 1 à ${nom}">${icon('plus', 'icon--sm')}</button>
          </div>
        </td>
        <td class="col-num inv-table__seuil">${nombre(l.seuil)}</td>
        <td data-statut>${puce(estRupture(l))}</td>
      </tr>`;
  }).join('');
  appliquerFiltre();
}

function majLigne(index) {
  const ligne = state.lignes[index];
  const tr = el.corps.querySelector(`tr[data-index="${index}"]`);
  if (!tr) return;
  const rupture = estRupture(ligne);
  const avant = tr.classList.contains('is-rupture');
  tr.classList.toggle('is-rupture', rupture);
  tr.classList.toggle('is-edited', ligne.quantite !== state.original[index]?.quantite);
  tr.querySelector('.stepper__input').value = ligne.quantite;
  tr.querySelector('[data-delta="-1"]').disabled = ligne.quantite <= 0;
  if (avant !== rupture) {
    const cellule = tr.querySelector('[data-statut]');
    cellule.innerHTML = puce(rupture);
    cellule.firstElementChild.classList.add('is-changed');
    announce(`${ligne.produit} : ${rupture ? 'en rupture' : 'stock suffisant'}.`);
  }
}

function appliquerFiltre() {
  const seulement = el.filtre.checked;
  let visibles = 0;
  el.corps.querySelectorAll('tr[data-index]').forEach((tr) => {
    const cache = seulement && !tr.classList.contains('is-rupture');
    tr.hidden = cache;
    if (!cache) visibles += 1;
  });
  el.corps.querySelector('[data-vide-filtre]')?.remove();
  if (seulement && state.lignes.length && !visibles) {
    el.corps.insertAdjacentHTML('beforeend', '<tr data-vide-filtre><td class="inv-table__empty" colspan="4">Aucune rupture : tout le stock est au-dessus des seuils.</td></tr>');
  }
}

function lireQuantite(input) {
  const texte = input.value.trim();
  if (!/^\d+$/.test(texte)) return null;
  const valeur = Number(texte);
  return valeur <= QUANTITE_MAX ? valeur : null;
}

function initTableau() {
  el.corps.addEventListener('click', (event) => {
    const bouton = event.target.closest('[data-delta]');
    if (!bouton) return;
    const index = Number(bouton.closest('tr').dataset.index);
    const ligne = state.lignes[index];
    ligne.quantite = Math.min(QUANTITE_MAX, Math.max(0, ligne.quantite + Number(bouton.dataset.delta)));
    bouton.closest('.stepper').removeAttribute('data-invalid');
    majLigne(index);
    mettreAJour();
  });
  el.corps.addEventListener('input', (event) => {
    const input = event.target.closest('.stepper__input');
    if (!input) return;
    const index = Number(input.closest('tr').dataset.index);
    const valeur = lireQuantite(input);
    const stepper = input.closest('.stepper');
    if (valeur === null) {
      stepper.dataset.invalid = 'true';
      input.setAttribute('aria-invalid', 'true');
      return;
    }
    stepper.removeAttribute('data-invalid');
    input.removeAttribute('aria-invalid');
    state.lignes[index].quantite = valeur;
    const tr = input.closest('tr');
    const rupture = estRupture(state.lignes[index]);
    if (tr.classList.contains('is-rupture') !== rupture) majLigne(index);
    else tr.classList.toggle('is-edited', valeur !== state.original[index]?.quantite);
    mettreAJour();
  });
  // Valeur invalide abandonnée : on revient à la dernière valeur correcte
  el.corps.addEventListener('focusout', (event) => {
    const input = event.target.closest('.stepper__input');
    if (!input || lireQuantite(input) !== null) return;
    const index = Number(input.closest('tr').dataset.index);
    input.closest('.stepper').removeAttribute('data-invalid');
    input.removeAttribute('aria-invalid');
    input.value = state.lignes[index].quantite;
  });
  el.filtre.addEventListener('change', appliquerFiltre);
  el.reset.addEventListener('click', () => {
    chargerLignes(state.original);
    toast('Quantités d\'origine restaurées.');
  });
}

/* ==========================================================================
   IMPORT
   ========================================================================== */
function zone(nom) { return form.querySelector(`[data-dropzone="${nom}"]`); }

function etatZone(nom, etatZoneValeur, titre) {
  const z = zone(nom);
  if (etatZoneValeur) z.dataset.state = etatZoneValeur; else delete z.dataset.state;
  if (titre) z.querySelector('[data-dropzone-title]').textContent = titre;
}

function messageImport(type, texte) {
  if (!texte) { el.importMessage.innerHTML = ''; return; }
  el.importMessage.innerHTML = type === 'error'
    ? `<p class="field__error">${icon('alert', 'icon--sm')}<span>${esc(texte)}</span></p>`
    : type === 'loading'
      ? `<p class="field__hint"><span class="spinner" aria-hidden="true"></span> ${esc(texte)}</p>`
      : `<p class="field__success">${icon('check-circle', 'icon--sm')}<span>${esc(texte)}</span></p>`;
}

async function importer() {
  const fichier = el.inputInventaire.files[0];
  const production = [...el.inputProduction.files];
  if (production.length) {
    etatZone('production', 'success', production.length === 1 ? production[0].name : `${production.length} fichiers CSV`);
  }
  if (!fichier) {
    if (production.length) messageImport('error', 'Choisissez d\'abord le fichier d\'inventaire.');
    return;
  }
  if (!/\.(xlsx|csv)$/i.test(fichier.name)) {
    etatZone('inventaire', 'error');
    el.inputInventaire.setAttribute('aria-invalid', 'true');
    messageImport('error', `« ${fichier.name} » : formats acceptés .xlsx et .csv.`);
    return;
  }
  if ([fichier, ...production].some((f) => f.size > TAILLE_MAX)) {
    etatZone('inventaire', 'error');
    messageImport('error', 'Chaque fichier doit faire moins de 2 Mo.');
    return;
  }

  const donnees = new FormData();
  donnees.append('inventaire', fichier);
  production.forEach((f) => donnees.append('production', f));
  etatZone('inventaire', 'loading', fichier.name);
  messageImport('loading', `Analyse de « ${fichier.name} »…`);
  el.lancer.disabled = true;
  try {
    const resultat = await postFormulaire('api/import', donnees);
    state.importe = { nom: resultat.nom, lignes: resultat.lignes, production: resultat.production };
    el.inputInventaire.removeAttribute('aria-invalid');
    etatZone('inventaire', 'success', resultat.nom);
    const ruptures = resultat.lignes.filter(estRupture).length;
    const prod = resultat.production ? ` · production : ${pluriel(resultat.production.length, 'jour')}` : '';
    messageImport('success', `${pluriel(resultat.lignes.length, 'produit')} importés, ${pluriel(ruptures, 'rupture')}${prod}.`);
    if (state.source === 'import') {
      state.nom = resultat.nom;
      state.production = resultat.production;
      chargerLignes(resultat.lignes);
    }
    rendreChoix();
  } catch (e) {
    etatZone('inventaire', 'error');
    el.inputInventaire.setAttribute('aria-invalid', 'true');
    const message = e instanceof ErreurApi && e.erreurs ? Object.values(e.erreurs)[0] : e.message;
    messageImport('error', message);
  } finally {
    mettreAJour();
  }
}

function initImport() {
  el.inputInventaire.addEventListener('change', importer);
  el.inputProduction.addEventListener('change', importer);
  form.querySelectorAll('.dropzone').forEach((z) => {
    let profondeur = 0;
    z.addEventListener('dragenter', () => { profondeur += 1; z.classList.add('is-dragging'); });
    z.addEventListener('dragleave', () => { profondeur -= 1; if (profondeur <= 0) { profondeur = 0; z.classList.remove('is-dragging'); } });
    z.addEventListener('drop', () => { profondeur = 0; z.classList.remove('is-dragging'); });
  });
}

/* ==========================================================================
   ALERTE EMAIL : EMAIL_DESTINATAIRE et EMAIL_EXPEDITEUR réglables ici
   L'envoi réel part du compte de la démo, seulement avec un inventaire
   d'exemple (contenu verrouillé) et dans les limites fixées par le serveur.
   ========================================================================== */
const envoiPossible = () => state.envoi.actif && state.source === 'exemple';

function lireEmail(input) {
  const valeur = input.value.trim();
  return { valeur, valide: !valeur || RE_EMAIL.test(valeur) };
}

function majBlocEmail() {
  const possible = envoiPossible();
  el.mail.dataset.disabled = String(!possible);
  [el.destinataire, el.expediteur].forEach((input) => { input.disabled = !possible; });
  if (!state.envoi.actif) {
    el.mailNote.dataset.type = 'warning';
    el.mailNoteTexte.textContent = 'L\'envoi réel n\'est pas configuré sur ce serveur : l\'email se télécharge en .eml après l\'exécution.';
  } else if (state.source === 'import') {
    el.mailNote.dataset.type = 'warning';
    el.mailNoteTexte.textContent = 'L\'envoi réel est réservé aux inventaires d\'exemple (contenu verrouillé). Avec un fichier importé, l\'email se télécharge en .eml.';
  } else {
    delete el.mailNote.dataset.type;
    el.mailNoteTexte.textContent = `Contenu verrouillé : seules les quantités de l'inventaire d'exemple sont modifiables. ${state.envoi.par_heure} envois par heure et ${state.envoi.par_destinataire_jour} par adresse et par jour au plus.`;
  }
}

function validerEmails({ silencieux = false, complet = false } = {}) {
  if (!envoiPossible()) {
    afficherErreur('destinataire', '');
    afficherErreur('expediteur', '');
    return true;
  }
  const dest = lireEmail(el.destinataire);
  const exp = lireEmail(el.expediteur);
  let ok = true;
  const signaler = (champ, input, message) => {
    input.setAttribute('aria-invalid', String(Boolean(message)));
    if (message) ok = false;
    if (!message || !silencieux) afficherErreur(champ, message);
  };
  signaler('destinataire', el.destinataire,
    !dest.valide ? 'Adresse email invalide (exemple : vous@exemple.com).'
      : complet && exp.valeur && !dest.valeur ? 'Indiquez le destinataire de l\'alerte.' : '');
  signaler('expediteur', el.expediteur, exp.valide ? '' : 'Adresse email invalide (exemple : vous@entreprise.com).');
  return ok;
}

function emailDemande() {
  const dest = lireEmail(el.destinataire);
  return envoiPossible() && dest.valeur && dest.valide ? dest.valeur : '';
}

function initEmail() {
  [el.destinataire, el.expediteur].forEach((input) => {
    // Pendant la saisie : on efface l'erreur dès que l'adresse devient valide, sans en afficher de nouvelle
    input.addEventListener('input', () => { validerEmails({ silencieux: true }); mettreAJour(); });
    input.addEventListener('blur', () => validerEmails());
  });
}

/* ==========================================================================
   PARAMÈTRES ET PRÉVISION
   ========================================================================== */
function lireSeuil() {
  const texte = el.seuil.value.trim();
  if (!/^\d+$/.test(texte)) return null;
  const valeur = Number(texte);
  return valeur >= SEUIL_MIN && valeur <= SEUIL_MAX ? valeur : null;
}

function mode() {
  return form.querySelector('input[name="mode"]:checked')?.value ?? 'TEST';
}

function itemPrevision(on, titre, pourquoi) {
  return `<span class="forecast-item__icon">${icon(on ? 'check' : 'minus')}</span>
    <span><span class="forecast-item__title">${esc(titre)}</span><span class="forecast-item__why">${esc(pourquoi)}</span></span>`;
}

function mettreAJour() {
  const total = state.lignes.length;
  const ruptures = state.lignes.filter(estRupture).length;
  const seuil = lireSeuil();
  const modifies = state.lignes.filter((l, i) => l.quantite !== state.original[i]?.quantite).length;

  // Tableau
  if (total) {
    el.compte.innerHTML = `<strong>${nombre(ruptures)}</strong> ${ruptures > 1 ? 'ruptures' : 'rupture'} sur <strong>${nombre(total)}</strong> produits`
      + (modifies ? ` · <span class="muted">${pluriel(modifies, 'quantité modifiée', 'quantités modifiées')}</span>` : '');
  }
  el.reset.disabled = !modifies;

  // Chiffre principal
  const ancien = el.prevRuptures.textContent;
  el.prevRuptures.textContent = total ? nombre(ruptures) : '—';
  if (ancien !== el.prevRuptures.textContent && ancien !== '—') {
    el.prevRuptures.classList.remove('is-changed');
    void el.prevRuptures.offsetWidth;  // relance l'animation
    el.prevRuptures.classList.add('is-changed');
  }
  el.prevTotal.textContent = total ? `sur ${pluriel(total, 'produit')}` : 'aucun inventaire';

  // Décisions du pipeline
  const productionDispo = state.source === 'exemple' || Boolean(state.production?.length);
  const inv = state.inventaires.find((i) => i.cle === state.cle);
  const categorie = state.source === 'exemple' ? inv?.categorie_scraping : CATEGORIE_IMPORT;
  const items = {
    cas1: [true, 'Rapport d\'alerte Excel', `toujours · ${pluriel(ruptures, 'ligne')}`],
    cas3: [ruptures > 0, emailDemande() && ruptures > 0 ? 'Email envoyé à votre adresse' : 'Email d\'alerte',
      ruptures === 0 ? 'aucune rupture : pas d\'email'
        : emailDemande() ? `${ruptures} rupture(s) > 0 · vers ${emailDemande()}` : `${ruptures} rupture(s) > 0 · .eml à télécharger`],
    cas6: [seuil !== null && ruptures >= seuil, 'Formulaire d\'urgence',
      seuil === null ? 'seuil à corriger' : ruptures >= seuil ? `${ruptures} ≥ seuil ${seuil}` : `${ruptures} < seuil ${seuil}`],
    cas2: [el.rapport.checked && productionDispo, 'Rapport hebdomadaire',
      !el.rapport.checked ? 'désactivé' : productionDispo ? 'production de la semaine · 2 onglets' : 'aucun fichier de production'],
    cas5: [el.scraping.checked, 'Relevé des prix en ligne', el.scraping.checked ? `catalogue ${categorie ?? ''}` : 'désactivé'],
    cas4: [true, 'Planification', mode() === 'TEST' ? 'mode TEST : surveillance chaque minute' : 'mode PRODUCTION : surveillance chaque heure'],
  };
  Object.entries(items).forEach(([cle, [on, titre, pourquoi]]) => {
    const li = el.prevListe.querySelector(`[data-forecast="${cle}"]`);
    const html = itemPrevision(on, titre, pourquoi);
    if (li.dataset.html === html) return;
    li.dataset.html = html;
    li.className = 'forecast-item';
    li.dataset.on = String(on);
    li.innerHTML = html;
  });

  el.lancer.disabled = !state.pret || !total;
}

function initParametres() {
  el.stepperSeuil.addEventListener('click', (event) => {
    const bouton = event.target.closest('[data-step]');
    if (!bouton) return;
    const actuel = lireSeuil() ?? 3;
    el.seuil.value = Math.min(SEUIL_MAX, Math.max(SEUIL_MIN, actuel + Number(bouton.dataset.step)));
    validerSeuil();
    mettreAJour();
  });
  el.seuil.addEventListener('input', () => { validerSeuil({ silencieux: true }); mettreAJour(); });
  el.seuil.addEventListener('change', () => validerSeuil());
  form.addEventListener('change', (event) => {
    if (event.target.matches('input[name="mode"], input[name="rapport"], input[name="scraping"]')) mettreAJour();
    if (event.target.matches('input[name="inventaire_choix"]')) {
      afficherErreur('inventaires', '');
      if (event.target.value === 'import') choisirImport();
      else choisirExemple(event.target.value);
    }
  });
}

function validerSeuil({ silencieux = false } = {}) {
  const valide = lireSeuil() !== null;
  el.stepperSeuil.dataset.invalid = String(!valide);
  el.seuil.setAttribute('aria-invalid', String(!valide));
  el.stepperSeuil.querySelector('[data-step="-1"]').disabled = (lireSeuil() ?? 2) <= SEUIL_MIN;
  el.stepperSeuil.querySelector('[data-step="1"]').disabled = (lireSeuil() ?? 0) >= SEUIL_MAX;
  if (valide) afficherErreur('seuil_formulaire', '');
  else if (!silencieux) afficherErreur('seuil_formulaire', `Indiquez un nombre entier de ${SEUIL_MIN} à ${SEUIL_MAX}.`);
  return valide;
}

function afficherErreur(champ, message) {
  const zoneErreur = form.querySelector(`[data-error="${champ}"]`);
  if (!zoneErreur) { if (message) toast(message, { type: 'error' }); return; }
  zoneErreur.hidden = !message;
  zoneErreur.innerHTML = message ? `${icon('alert', 'icon--sm')}<span>${esc(message)}</span>` : '';
}

/* ==========================================================================
   LANCEMENT
   ========================================================================== */
export function payload() {
  return {
    source: state.source,
    inventaire: state.source === 'exemple' ? state.cle : undefined,
    nom: state.source === 'import' ? state.nom : undefined,
    lignes: state.lignes.map(({ produit, quantite, seuil }) => ({ produit, quantite, seuil })),
    production: state.source === 'import' ? state.production : undefined,
    mode: mode(),
    seuil_formulaire: lireSeuil(),
    cas: { rapport: el.rapport.checked, scraping: el.scraping.checked },
    email: emailDemande() ? { destinataire: emailDemande(), expediteur: lireEmail(el.expediteur).valeur } : undefined,
  };
}

/** Réglages courants, après le premier chargement (boutons « Lancer le pipeline ») */
export async function payloadPret() {
  await chargement;
  if (!state.lignes.length || lireSeuil() === null || !validerEmails({ complet: true })) return null;
  return payload();
}

/** Erreurs renvoyées par le serveur (422) : affichées près des champs concernés */
export function afficherErreursServeur(erreurs) {
  Object.entries(erreurs ?? {}).forEach(([champ, message]) => {
    const cible = { lignes: 'lignes', seuil_formulaire: 'seuil_formulaire', destinataire: 'destinataire', expediteur: 'expediteur' }[champ] ?? 'inventaires';
    afficherErreur(cible, message);
  });
}

export function setLancement(enCours) {
  if (enCours) el.lancer.dataset.state = 'loading';
  else delete el.lancer.dataset.state;
}

export function initDemo({ onLaunch }) {
  surLancement = onLaunch;
  initTableau();
  initImport();
  initParametres();
  initEmail();
  validerSeuil({ silencieux: true });
  mettreAJour();

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!validerSeuil()) { el.seuil.focus(); return; }
    if (!validerEmails({ complet: true })) {
      (el.destinataire.getAttribute('aria-invalid') === 'true' ? el.destinataire : el.expediteur).focus();
      return;
    }
    if (!state.lignes.length) {
      afficherErreur('lignes', state.source === 'import' ? 'Importez d\'abord un inventaire.' : 'L\'inventaire est vide.');
      return;
    }
    afficherErreur('lignes', '');
    surLancement(payload());
  });

  chargement = (async () => {
    try {
      const reponse = await getJSON('api/inventaires');
      state.inventaires = reponse.inventaires;
      if (reponse.seuil_formulaire) el.seuil.value = reponse.seuil_formulaire;
      if (reponse.envoi_email) state.envoi = reponse.envoi_email;
      state.cle = state.inventaires[0]?.cle ?? null;
      rendreChoix();
      if (state.cle) await choisirExemple(state.cle);
      state.pret = true;
    } catch (e) {
      el.choix.innerHTML = '';
      afficherErreur('inventaires', `${e.message} Rechargez la page pour réessayer.`);
      el.compte.textContent = 'Inventaires indisponibles.';
      el.corps.innerHTML = '';
    } finally {
      validerSeuil({ silencieux: true });
      majBlocEmail();
      mettreAJour();
    }
  })();
}
