/* ==========================================================================
   POINT D'ENTRÉE : initialisation et navigation entre les deux vues
   « accueil » (page de présentation + démo) et « execution » (pipeline en
   cours puis résultats). La navigation passe par l'historique du navigateur
   (bouton Retour compris) et par une transition de vue courte, qui ne bloque
   jamais l'interaction.
   ========================================================================== */

import { initMotion, transitionView, afterMotion, motionAllowed } from './motion.js';
import { initLogos, initTheme, initHeader, initMobileMenu, initScrollSpy, initTooltips, initDialogs, initCopy, toast } from './ui.js';
import { initBoard, initStory } from './hero.js';
import { initDemo, payloadPret, afficherErreursServeur, setLancement } from './demo.js';
import { initRun, startRun, hasRun } from './run.js';

const vues = {
  accueil: document.getElementById('vue-accueil'),
  execution: document.getElementById('vue-execution'),
};
const header = document.getElementById('site-header');
let vueCourante = 'accueil';
let vueVisee = null;      // vue en cours d'affichage (transition)
let defilementAccueil = 0;

function focusSansDefiler(el) {
  if (!el) return;
  if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1');
  el.focus({ preventScroll: true });
}

function defilerVers(id, { instantane = false } = {}) {
  const cible = document.getElementById(id);
  if (!cible) return;
  cible.scrollIntoView({ behavior: instantane || !motionAllowed() ? 'instant' : 'smooth', block: 'start' });
}

/** Affiche une vue ; `section` fait défiler l'accueil jusqu'à une section. */
function go(vue, { push = true, section = null } = {}) {
  const depuis = vueVisee ?? vueCourante;
  if (vue === depuis) {
    if (section) defilerVers(section);
    return Promise.resolve();
  }
  vueVisee = vue;
  if (depuis === 'accueil') defilementAccueil = window.scrollY;

  const maj = () => {
    Object.entries(vues).forEach(([nom, el]) => { el.hidden = nom !== vue; });
    vueCourante = vue;
    if (vueVisee === vue) vueVisee = null;
    header.dataset.solid = String(vue !== 'accueil');
    if (vue === 'execution') window.scrollTo({ top: 0, behavior: 'instant' });
    else if (section) defilerVers(section, { instantane: true });
    else window.scrollTo({ top: defilementAccueil, behavior: 'instant' });
  };

  const avecVT = Boolean(document.startViewTransition) && motionAllowed();
  const fin = transitionView(maj).then(() => {
    if (!avecVT && motionAllowed()) {
      vues[vue].classList.add('is-entering');
      afterMotion(vues[vue], '--dur-transition').then(() => vues[vue].classList.remove('is-entering'));
    }
    if (vue === 'execution') focusSansDefiler(document.getElementById('run-titre'));
    else if (section) focusSansDefiler(document.getElementById(`${section}-titre`) ?? document.getElementById(section));
  });

  if (push) {
    const url = vue === 'execution' ? '#execution' : (section ? `#${section}` : window.location.pathname);
    history.pushState({ vue, section }, '', url);
  }
  return fin;
}

/* ---------- Lancement ---------- */
async function lancer(payload) {
  if (!payload) {
    toast('Les réglages de la démo sont incomplets : vérifiez l\'inventaire et le seuil.', { type: 'error' });
    go('accueil', { section: 'demo' });
    return;
  }
  setLancement(true);
  go('execution');
  startRun(payload);
}

function initNavigation() {
  document.addEventListener('click', async (event) => {
    const action = event.target.closest('[data-action]');
    if (action?.dataset.action === 'run-default') {
      event.preventDefault();
      lancer(await payloadPret());
      return;
    }

    const nav = event.target.closest('[data-nav]');
    if (nav) {
      event.preventDefault();
      const cible = nav.dataset.nav;
      if (cible === 'accueil') {
        if (vueCourante === 'accueil') {
          window.scrollTo({ top: 0, behavior: motionAllowed() ? 'smooth' : 'instant' });
          history.pushState({ vue: 'accueil' }, '', window.location.pathname);
        } else {
          defilementAccueil = 0;
          go('accueil');
        }
      } else if (cible === 'demo') {
        go('accueil', { section: 'demo' });
      }
      return;
    }

    // Ancres de l'accueil cliquées depuis la vue exécution
    const ancre = event.target.closest('a[href^="#"]');
    if (ancre && vueCourante !== 'accueil') {
      const id = ancre.getAttribute('href').slice(1);
      if (id && id !== 'execution' && id !== 'contenu') {
        event.preventDefault();
        go('accueil', { section: id });
      }
    }
  });

  window.addEventListener('popstate', (event) => {
    const depuisHash = window.location.hash.slice(1);
    let vue = event.state?.vue ?? (depuisHash === 'execution' ? 'execution' : 'accueil');
    if (vue === 'execution' && !hasRun()) vue = 'accueil';
    go(vue, { push: false, section: event.state?.section ?? null });
  });

  // Un lien direct vers #execution sans exécution en mémoire revient à l'accueil
  if (window.location.hash === '#execution') history.replaceState({ vue: 'accueil' }, '', window.location.pathname);
  else history.replaceState({ vue: 'accueil' }, '', window.location.href);
}

/* ---------- Démarrage ---------- */
// Streamlit Community Cloud affiche l'appli dans une iframe (/~/+/), masquée tant
// qu'elle n'a pas signalé être prête : on envoie le message qu'attend la page hôte.
if (window.parent !== window) {
  window.parent.postMessage({ stCommVersion: 1, type: 'GUEST_READY' }, '*');
}

initLogos();
initTheme();
initMotion();
initHeader();
initMobileMenu();
initScrollSpy();
initTooltips();
initDialogs();
initCopy();
initBoard();
initStory();
initDemo({ onLaunch: lancer });
initRun({
  onInvalid: (erreurs) => {
    setLancement(false);
    afficherErreursServeur(erreurs);
    toast('Le serveur a refusé ces réglages : corrigez le champ signalé.', { type: 'error' });
    go('accueil', { section: 'demo' });
  },
  onSettled: () => setLancement(false),
});
initNavigation();
