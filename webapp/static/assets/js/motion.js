/* ==========================================================================
   SYSTÈME DE MOTION
   Un seul endroit pour décider si, quand et comment ça bouge :
   - mêmes durées et courbes que les tokens CSS (lues sur :root) ;
   - apparition au défilement (data-reveal) avec stagger hiérarchique ;
   - transitions de vue ;
   - interactions curseur réservées aux pointeurs fins (souris, trackpad) ;
   - tout s'efface devant prefers-reduced-motion.
   ========================================================================== */

const reduceQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
const finePointerQuery = window.matchMedia('(hover: hover) and (pointer: fine)');

export const motionAllowed = () => !reduceQuery.matches;
export const finePointer = () => finePointerQuery.matches;

/** Durée d'un token CSS (« 380ms ») en millisecondes */
export function token(nom) {
  const valeur = getComputedStyle(document.documentElement).getPropertyValue(nom).trim();
  const nombre = parseFloat(valeur);
  if (Number.isNaN(nombre)) return 0;
  return valeur.endsWith('ms') ? nombre : nombre * 1000;
}

export const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Résout après la durée d'animation d'un élément (sans dépendre de transitionend) */
export function afterMotion(el, nom = '--dur-component') {
  return wait(motionAllowed() ? token(nom) + 30 : 0).then(() => el);
}

/* ---------- Apparition au défilement ---------- */
let revealObserver = null;

function reveal(el) {
  el.classList.add('is-revealed');
  const index = Number(getComputedStyle(el).getPropertyValue('--reveal-index')) || 0;
  wait(token('--dur-complex') + index * token('--stagger') + 50).then(() => el.classList.add('is-settled'));
}

export function initReveal() {
  clearTimeout(window.__motionGuard);
  const root = document.documentElement;
  const elements = document.querySelectorAll('[data-reveal]');
  if (!motionAllowed() || !('IntersectionObserver' in window)) {
    root.classList.remove('has-motion');
    return;
  }
  root.classList.add('has-motion');
  revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      reveal(entry.target);
      revealObserver.unobserve(entry.target);
    });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
  elements.forEach((el) => revealObserver.observe(el));

  // Le visiteur active « réduire les animations » en cours de route : tout s'affiche
  reduceQuery.addEventListener('change', () => {
    if (!reduceQuery.matches) return;
    root.classList.remove('has-motion');
    revealObserver?.disconnect();
  });
}

/* ---------- Transition de vue ---------- */
export function transitionView(update) {
  if (document.startViewTransition && motionAllowed()) {
    const transition = document.startViewTransition(update);
    return transition.updateCallbackDone.catch(() => {});
  }
  update();
  return Promise.resolve();
}

/* ---------- Compteurs (repères chiffrés) ---------- */
export function countUp(el) {
  const cible = Number(el.dataset.count);
  if (!motionAllowed() || !cible) { el.textContent = String(cible); return; }
  const duree = token('--dur-complex') * 1.4;
  const debut = performance.now();
  const ease = (t) => 1 - Math.pow(1 - t, 4);
  const tick = (maintenant) => {
    const t = Math.min(1, (maintenant - debut) / duree);
    el.textContent = String(Math.round(ease(t) * cible));
    if (t < 1) requestAnimationFrame(tick);
  };
  el.textContent = '0';
  requestAnimationFrame(tick);
}

export function initCounters() {
  const valeurs = document.querySelectorAll('[data-count]');
  if (!('IntersectionObserver' in window)) return;
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      countUp(entry.target);
      io.unobserve(entry.target);
    });
  }, { threshold: 0.6 });
  valeurs.forEach((el) => io.observe(el));
}

/* ---------- Surligneur du titre ---------- */
export function initHighlight() {
  const cibles = document.querySelectorAll('[data-highlight]');
  // Le délai est porté par le CSS (le trait suit l'apparition du titre)
  requestAnimationFrame(() => requestAnimationFrame(() => cibles.forEach((el) => el.classList.add('is-drawn'))));
}

/* ---------- Interactions curseur (desktop uniquement) ---------- */
function onFrame(callback) {
  let attente = false;
  let dernier = null;
  return (event) => {
    dernier = event;
    if (attente) return;
    attente = true;
    requestAnimationFrame(() => { attente = false; callback(dernier); });
  };
}

/** Projecteur et légère parallaxe du tableau de bord dans le hero */
export function initSpotlight() {
  const zone = document.querySelector('[data-spotlight]');
  const board = zone?.querySelector('[data-tilt]');
  if (!zone) return;
  const actif = () => finePointer() && motionAllowed();

  zone.addEventListener('pointermove', onFrame((event) => {
    if (!actif()) return;
    const rect = zone.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    zone.style.setProperty('--spot-x', `${(x * 100).toFixed(1)}%`);
    zone.style.setProperty('--spot-y', `${(y * 100).toFixed(1)}%`);
    if (board) {
      const dx = x - 0.5;
      const dy = y - 0.5;
      board.style.setProperty('--rot-y', `${(dx * 4).toFixed(2)}deg`);
      board.style.setProperty('--rot-x', `${(-dy * 3).toFixed(2)}deg`);
      board.style.setProperty('--tilt-x', `${(dx * 8).toFixed(1)}px`);
      board.style.setProperty('--tilt-y', `${(dy * 6).toFixed(1)}px`);
    }
  }), { passive: true });

  zone.addEventListener('pointerleave', () => {
    ['--rot-x', '--rot-y', '--tilt-x', '--tilt-y'].forEach((p) => board?.style.removeProperty(p));
  });
}

/** Effet magnétique très discret (4 px maximum) sur les appels à l'action principaux */
export function initMagnetic() {
  document.querySelectorAll('[data-magnetic]').forEach((el) => {
    el.addEventListener('pointermove', onFrame((event) => {
      if (!finePointer() || !motionAllowed()) return;
      const rect = el.getBoundingClientRect();
      const dx = (event.clientX - rect.left) / rect.width - 0.5;
      const dy = (event.clientY - rect.top) / rect.height - 0.5;
      el.style.transform = `translate3d(${(dx * 8).toFixed(1)}px, ${(dy * 6).toFixed(1)}px, 0)`;
    }), { passive: true });
    el.addEventListener('pointerleave', () => { el.style.transform = ''; });
    el.addEventListener('pointerdown', () => { el.style.transform = ''; });
  });
}

export function initMotion() {
  initReveal();
  initCounters();
  initHighlight();
  initSpotlight();
  initMagnetic();
}
