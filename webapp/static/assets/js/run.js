/* ==========================================================================
   EXÉCUTION : flux NDJSON du serveur → étapes, journal, puis résultats

   Le serveur exécute le pipeline en une seconde environ. Les événements
   sont rejoués avec un très léger rythme (quelques dizaines de ms) pour
   que l'enchaînement Cas 1 → 3 → 6 → 2 → 5 → 4 se lise ; « Afficher tout
   de suite » vide la file, et le mouvement réduit supprime tout délai.
   ========================================================================== */

import { fluxNDJSON, ErreurApi } from './api.js';
import { motionAllowed, wait } from './motion.js';
import { duree, esc, icon } from './format.js';
import { announce } from './ui.js';
import { rendreResultats, viderResultats } from './results.js';

const RYTHME = { debut: 160, log: 45, en_cours: 90, fin_etape: 240 };
const GLYPHES = { info: '›', ok: '✓', alerte: '!', erreur: '×' };
const LIBELLES_ETAT = { done: 'terminée', skipped: 'ignorée', error: 'en erreur' };
const ETATS = { en_cours: 'running', termine: 'done', ignore: 'skipped', erreur: 'error' };

const vue = document.getElementById('vue-execution');
const el = {
  titre: vue.querySelector('[data-run-title]'),
  meta: vue.querySelector('[data-run-meta]'),
  statut: vue.querySelector('[data-run-status]'),
  statutTexte: vue.querySelector('[data-run-status-text]'),
  passer: vue.querySelector('[data-action="skip-animation"]'),
  progression: vue.querySelector('[data-run-progress]'),
  etapes: vue.querySelector('[data-run-steps]'),
  journal: vue.querySelector('[data-run-log]'),
  journalTitre: vue.querySelector('[data-run-console-title]'),
  erreur: vue.querySelector('[data-run-error]'),
  erreurMessage: vue.querySelector('[data-run-error-message]'),
  resultats: vue.querySelector('[data-results]'),
  relancer: vue.querySelector('[data-action="rerun"]'),
};

let execution = null;   // { payload, controleur, file, vidage, instantane, etat }
let rappels = { onInvalid: () => {}, onSettled: () => {} };

/* ---------- Rendu des étapes ---------- */
function iconeEtape(etat, cas) {
  if (etat === 'running') return '<span class="spinner" aria-hidden="true"></span>';
  if (etat === 'done') return icon('check');
  if (etat === 'skipped') return icon('minus');
  if (etat === 'error') return icon('x');
  return String(cas);
}

function rendreEtapes(etapes) {
  el.etapes.innerHTML = etapes.map((e) => `
    <li class="step" data-state="pending" data-step="${esc(e.cle)}">
      <span class="step__icon">${iconeEtape('pending', e.cas)}</span>
      <span class="step__body">
        <span class="step__title">${esc(e.titre)}<span class="step__cas">Cas ${e.cas}</span></span>
        <span class="step__resume" data-resume></span>
      </span>
      <span class="step__time" data-time></span>
    </li>`).join('');
}

function majEtape(evt) {
  const li = el.etapes.querySelector(`[data-step="${evt.cle}"]`);
  if (!li) return;
  const etat = ETATS[evt.etat] ?? 'pending';
  li.dataset.state = etat;
  const cas = execution.etat.etapes.find((e) => e.cle === evt.cle)?.cas ?? '';
  li.querySelector('.step__icon').innerHTML = iconeEtape(etat, cas);
  if (evt.resume !== undefined) li.querySelector('[data-resume]').textContent = evt.resume;
  if (evt.duree_ms !== undefined) li.querySelector('[data-time]').textContent = duree(evt.duree_ms);
  if (etat !== 'running') {
    execution.etat.terminees += 1;
    majProgression();
    const titre = execution.etat.etapes.find((e) => e.cle === evt.cle)?.titre ?? evt.cle;
    announce(`${titre} ${LIBELLES_ETAT[etat]}${evt.resume ? ` : ${evt.resume}` : ''}.`);
  }
}

function majProgression() {
  const total = execution.etat.etapes.length || 6;
  const fait = Math.min(execution.etat.terminees, total);
  el.progression.setAttribute('aria-valuenow', String(fait));
  el.progression.setAttribute('aria-valuemax', String(total));
  el.progression.querySelector('.progress__bar').style.setProperty('--progress', String(fait / total));
}

/* ---------- Journal ---------- */
function ajouterLigne({ niveau = 'info', heure = '', texte }) {
  const procheDuBas = el.journal.scrollHeight - el.journal.scrollTop - el.journal.clientHeight < 40;
  el.journal.insertAdjacentHTML('beforeend',
    `<div class="console__line" data-level="${esc(niveau)}"><span class="console__time">${esc(heure)}</span><span class="console__glyph" aria-hidden="true">${GLYPHES[niveau] ?? '›'}</span><span class="console__text">${esc(texte)}</span></div>`);
  if (procheDuBas) el.journal.scrollTop = el.journal.scrollHeight;
}

/* ---------- Statut global ---------- */
function statut(etat, texte) {
  el.statut.dataset.state = etat;
  el.statutTexte.textContent = texte;
  el.passer.hidden = etat !== 'running';
  el.progression.dataset.state = etat === 'error' ? 'error' : '';
}

function afficherErreur(message) {
  statut('error', 'Échec');
  el.titre.textContent = 'Pipeline interrompu';
  el.erreurMessage.textContent = message;
  el.erreur.hidden = false;
  announce(`Échec du pipeline : ${message}`);
  rappels.onSettled();
}

/* ---------- File d'événements rythmée ---------- */
function delai(evt) {
  if (execution.instantane || !motionAllowed()) return 0;
  if (evt.type === 'debut') return RYTHME.debut;
  if (evt.type === 'log') return RYTHME.log;
  if (evt.type === 'etape') return evt.etat === 'en_cours' ? RYTHME.en_cours : RYTHME.fin_etape;
  return 0;
}

function traiter(evt) {
  const etat = execution.etat;
  switch (evt.type) {
    case 'debut':
      etat.debut = evt;
      etat.etapes = evt.etapes;
      rendreEtapes(evt.etapes);
      el.meta.innerHTML = [
        `<li class="tag">${esc(evt.inventaire)}</li>`,
        `<li class="tag">mode ${evt.mode === 'TEST' ? 'TEST' : 'PRODUCTION'}</li>`,
        `<li class="tag">lancé à ${esc(evt.heure)}</li>`,
      ].join('');
      el.journalTitre.textContent = `journal · ${evt.inventaire}`;
      break;
    case 'log':
      ajouterLigne(evt);
      break;
    case 'etape':
      majEtape(evt);
      break;
    case 'resultat':
      etat.resultats[evt.cle] = evt.donnees;
      break;
    case 'fin':
      etat.fin = evt;
      statut('done', 'Terminé');
      el.titre.textContent = 'Pipeline terminé';
      rendreResultats(etat);
      announce(`Pipeline terminé en ${duree(evt.duree_ms)}. ${evt.fichiers.length} fichiers prêts au téléchargement.`);
      rappels.onSettled();
      break;
    case 'erreur':
      etat.echec = true;
      afficherErreur(evt.message);
      break;
    default:
      break;
  }
}

async function vider(mien) {
  if (mien.vidage) return;
  mien.vidage = true;
  while (execution === mien && mien.file.length) {
    const evt = mien.file.shift();
    traiter(evt);
    const d = delai(evt);
    if (d) await wait(d);
  }
  if (execution === mien) mien.vidage = false;
}

/* ---------- API du module ---------- */
export function hasRun() { return execution !== null; }

export function cancelRun() {
  execution?.controleur.abort();
}

export async function startRun(payload) {
  cancelRun();
  const mien = {
    payload,
    controleur: new AbortController(),
    file: [],
    vidage: false,
    instantane: false,
    etat: { etapes: [], terminees: 0, resultats: {}, fin: null, debut: null, echec: false },
  };
  execution = mien;

  // Remise à zéro de la vue
  statut('running', 'En cours');
  el.titre.textContent = 'Pipeline en cours…';
  el.meta.innerHTML = '';
  el.erreur.hidden = true;
  el.journal.innerHTML = '';
  el.journalTitre.textContent = 'journal';
  rendreEtapes([
    { cle: 'cas1', cas: 1, titre: 'Détection des ruptures' }, { cle: 'cas3', cas: 3, titre: 'Alerte email' },
    { cle: 'cas6', cas: 6, titre: 'Formulaire d\'urgence' }, { cle: 'cas2', cas: 2, titre: 'Rapport hebdomadaire' },
    { cle: 'cas5', cas: 5, titre: 'Scraping des prix' }, { cle: 'cas4', cas: 4, titre: 'Planification' },
  ]);
  majProgression();
  viderResultats();

  try {
    await fluxNDJSON('api/pipeline', payload, (evt) => {
      if (execution !== mien) return;
      mien.file.push(evt);
      vider(mien);
    }, { signal: mien.controleur.signal });
    if (execution === mien && !mien.file.some((e) => e.type === 'fin' || e.type === 'erreur') && !mien.etat.fin && !mien.etat.echec) {
      // Flux terminé sans événement final : attendre la file puis signaler l'échec
      await waitUntilDrained(mien);
      if (!mien.etat.fin && !mien.etat.echec) afficherErreur('Le serveur a interrompu le pipeline avant la fin.');
    }
  } catch (e) {
    if (e.name === 'AbortError' || execution !== mien) return;
    if (e instanceof ErreurApi && e.erreurs) {   // erreurs de validation, champ par champ
      rappels.onInvalid(e.erreurs);
      return;
    }
    afficherErreur(e.message);
  }
}

async function waitUntilDrained(mien) {
  while (mien.vidage || mien.file.length) await wait(30);
}

function relancer() {
  if (!execution) return;
  el.relancer.dataset.state = 'loading';
  const payload = execution.payload;
  window.scrollTo({ top: 0, behavior: motionAllowed() ? 'smooth' : 'instant' });
  startRun(payload).finally(() => { delete el.relancer.dataset.state; });
}

export function initRun({ onInvalid, onSettled }) {
  rappels = { onInvalid, onSettled };
  el.relancer.addEventListener('click', relancer);
  el.passer.addEventListener('click', () => {
    if (!execution) return;
    execution.instantane = true;
    vider(execution);
  });
  vue.addEventListener('click', (event) => {
    if (event.target.closest('[data-action="retry"]') && execution) {
      startRun(execution.payload);
    }
  });
}
