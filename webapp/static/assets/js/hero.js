/* ==========================================================================
   ACCUEIL : tableau de bord du hero et narration « Fonctionnement »
   ========================================================================== */

import { motionAllowed, wait } from './motion.js';
import { esc } from './format.js';

/* ---------- Tableau de bord : un cycle de surveillance, joué une fois ----------
   Chaque temps montre où en est la donnée : le nœud actif s'allume, le fil se
   remplit, la console écrit ce que le programme écrirait. Pas de boucle infinie :
   la séquence s'arrête sur son état final et peut être rejouée. */
const SEQUENCE = [
  { delai: 250, noeud: 0, niveau: 'info', texte: 'Lecture : inventaire_gaming_multimedia.xlsx' },
  { delai: 650, noeud: 1, fil: 0, niveau: 'alerte', texte: 'PRODUITS EN ALERTE  12/20' },
  { delai: 750, noeud: 2, fil: 1, niveau: 'ok', texte: 'Email prêt : [ALERTE STOCK] 12 produit(s)' },
  { delai: 750, noeud: 3, fil: 2, niveau: 'alerte', texte: 'Seuil atteint (12 ≥ 3) : formulaire…' },
  { delai: 700, niveau: 'ok', texte: 'Formulaire soumis · « Received! »' },
  { delai: 450, niveau: 'ok', texte: 'Cycle terminé · 3 fichiers générés', fin: true },
];
const GLYPHES = { info: '›', ok: '✓', alerte: '!', erreur: '×' };

export function initBoard() {
  const board = document.querySelector('[data-board]');
  if (!board) return;
  const noeuds = [...board.querySelectorAll('[data-node]')];
  const fils = [...board.querySelectorAll('[data-wire]')];
  const consoleEl = board.querySelector('[data-board-console]');
  const etat = board.querySelector('[data-board-state]');
  let jeton = 0;

  const ligne = ({ niveau, texte }) =>
    `<div class="console__line" data-level="${niveau}"><span class="console__glyph">${GLYPHES[niveau]}</span><span class="console__text">${esc(texte)}</span></div>`;

  const appliquer = (pas) => {
    if (pas.noeud !== undefined) {
      noeuds.forEach((n, i) => {
        n.classList.toggle('is-active', i === pas.noeud);
        n.classList.toggle('is-done', i < pas.noeud);
      });
    }
    if (pas.fil !== undefined) fils[pas.fil].classList.add('is-done');
    if (pas.fin) {
      noeuds.forEach((n) => { n.classList.remove('is-active'); n.classList.add('is-done'); });
      board.dataset.phase = 'done';
      etat.textContent = 'terminé';
    }
    consoleEl.insertAdjacentHTML('beforeend', ligne(pas));
  };

  const reinitialiser = () => {
    noeuds.forEach((n) => n.classList.remove('is-active', 'is-done'));
    fils.forEach((f) => f.classList.remove('is-done'));
    consoleEl.innerHTML = '';
    board.dataset.phase = 'running';
    etat.textContent = 'en cours';
  };

  const jouer = async () => {
    const mien = ++jeton;
    reinitialiser();
    if (!motionAllowed()) {
      SEQUENCE.forEach(appliquer);
      return;
    }
    for (const pas of SEQUENCE) {
      await wait(pas.delai);
      if (mien !== jeton) return;
      appliquer(pas);
    }
  };

  // Démarre quand le tableau est visible (sinon personne ne le verrait jouer)
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      if (!entries.some((e) => e.isIntersecting)) return;
      io.disconnect();
      jouer();
    }, { threshold: 0.35 });
    io.observe(board);
  } else {
    jouer();
  }

  document.addEventListener('click', (event) => {
    if (event.target.closest('[data-action="replay-board"]')) jouer();
  });
}

/* ---------- Narration : le diagramme suit l'étape lue ---------- */
const CARTE = {
  cas1: { groupes: ['in-stock', 'cas1'], fils: ['cas1'], legende: 'Cas 1 · Détection des ruptures' },
  cas3: { groupes: ['cas1', 'cas3'], fils: ['cas3'], legende: 'Cas 3 · Alerte email si rupture > 0' },
  cas6: { groupes: ['cas1', 'cas6'], fils: ['cas6'], legende: 'Cas 6 · Formulaire si ruptures ≥ seuil' },
  cas2: { groupes: ['in-prod', 'cas2'], fils: ['cas2'], legende: 'Cas 2 · Rapport hebdomadaire' },
  cas5: { groupes: ['in-web', 'cas5'], fils: ['cas5'], legende: 'Cas 5 · Scraping des prix' },
  cas4: { groupes: ['cas4', 'cas1', 'cas2', 'cas5'], fils: [], legende: 'Cas 4 · Le planificateur relance tout' },
};

export function initStory() {
  const story = document.querySelector('[data-story]');
  if (!story) return;
  const etapes = [...story.querySelectorAll('.story-step')];
  const diagramme = story.querySelector('[data-diagram]');
  const legende = story.querySelector('[data-story-caption]');

  const allumer = (cle) => {
    const carte = CARTE[cle];
    if (!carte || !diagramme) return;
    diagramme.dataset.active = cle;
    diagramme.querySelectorAll('[data-dg]').forEach((g) => g.classList.toggle('is-lit', carte.groupes.includes(g.dataset.dg)));
    diagramme.querySelectorAll('[data-dw]').forEach((w) => w.classList.toggle('is-lit', carte.fils.includes(w.dataset.dw)));
    legende.textContent = carte.legende;
  };

  if (!('IntersectionObserver' in window)) return;
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      etapes.forEach((e) => e.classList.toggle('is-active', e === entry.target));
      allumer(entry.target.dataset.step);
    });
  }, { rootMargin: '-45% 0px -45% 0px' });
  etapes.forEach((e) => io.observe(e));
  allumer('cas1');
  etapes[0]?.classList.add('is-active');
}
