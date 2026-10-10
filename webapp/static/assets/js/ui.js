/* ==========================================================================
   COMPOSANTS D'INTERFACE : thème, en-tête, menu mobile, navigation active,
   onglets, infobulles, fenêtres, notifications, copie
   ========================================================================== */

import { afterMotion, motionAllowed } from './motion.js';
import { icon } from './format.js';

/* ---------- Logo (gabarit unique) ---------- */
export function initLogos() {
  const gabarit = document.getElementById('tpl-logo');
  document.querySelectorAll('[data-logo]').forEach((slot) => slot.append(gabarit.content.cloneNode(true)));
}

/* ---------- Thème clair / sombre ---------- */
const CLE_THEME = 'relais-theme';

function appliquerTheme(theme) {
  const root = document.documentElement;
  root.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]').content = theme === 'dark' ? '#0a0d0c' : '#f4f3ee';
  document.querySelectorAll('[data-action="toggle-theme"]').forEach((bouton) => {
    bouton.setAttribute('aria-label', theme === 'dark' ? 'Activer le thème clair' : 'Activer le thème sombre');
  });
}

export function initTheme() {
  appliquerTheme(document.documentElement.dataset.theme || 'light');
  document.addEventListener('click', (event) => {
    if (!event.target.closest('[data-action="toggle-theme"]')) return;
    const suivant = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    appliquerTheme(suivant);
    try { localStorage.setItem(CLE_THEME, suivant); } catch { /* stockage indisponible */ }
  });
  // Sans choix enregistré, la page suit le système
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (event) => {
    let choix = null;
    try { choix = localStorage.getItem(CLE_THEME); } catch { /* stockage indisponible */ }
    if (!choix) appliquerTheme(event.matches ? 'dark' : 'light');
  });
}

/* ---------- En-tête : compact et flouté après défilement ---------- */
export function initHeader() {
  const header = document.getElementById('site-header');
  let attente = false;
  const maj = () => {
    attente = false;
    header.dataset.scrolled = String(window.scrollY > 8);
  };
  window.addEventListener('scroll', () => {
    if (attente) return;
    attente = true;
    requestAnimationFrame(maj);
  }, { passive: true });
  maj();
}

/* ---------- Menu mobile ---------- */
export function initMobileMenu() {
  const bouton = document.querySelector('.menu-toggle');
  const menu = document.getElementById('mobile-menu');
  const header = document.getElementById('site-header');
  if (!bouton || !menu) return;

  const ouvrir = () => {
    menu.hidden = false;
    menu.classList.remove('is-closing');
    menu.classList.add('is-open');
    header.classList.add('is-menu-open');
    bouton.setAttribute('aria-expanded', 'true');
    bouton.setAttribute('aria-label', 'Fermer le menu');
    menu.querySelector('a, button')?.focus({ preventScroll: true });
  };
  const fermer = ({ rendreFocus = true } = {}) => {
    if (menu.hidden) return;
    bouton.setAttribute('aria-expanded', 'false');
    bouton.setAttribute('aria-label', 'Ouvrir le menu');
    menu.classList.remove('is-open');
    menu.classList.add('is-closing');
    header.classList.remove('is-menu-open');
    afterMotion(menu).then(() => {
      if (bouton.getAttribute('aria-expanded') === 'false') {
        menu.hidden = true;
        menu.classList.remove('is-closing');
      }
    });
    if (rendreFocus) bouton.focus({ preventScroll: true });
  };

  bouton.addEventListener('click', () => (menu.hidden ? ouvrir() : fermer()));
  menu.addEventListener('click', (event) => {
    if (event.target.closest('a, button')) fermer({ rendreFocus: false });
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !menu.hidden) fermer();
  });
  document.addEventListener('click', (event) => {
    if (!menu.hidden && !header.contains(event.target)) fermer({ rendreFocus: false });
  });
  window.matchMedia('(min-width: 64em)').addEventListener('change', (event) => {
    if (event.matches) fermer({ rendreFocus: false });
  });
}

/* ---------- Navigation : section en cours ---------- */
export function initScrollSpy() {
  const liens = [...document.querySelectorAll('[data-spy]')];
  const sections = liens.map((lien) => document.getElementById(lien.dataset.spy)).filter(Boolean);
  if (!('IntersectionObserver' in window)) return;
  const visibles = new Map();
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => visibles.set(entry.target.id, entry.isIntersecting));
    const active = sections.find((s) => visibles.get(s.id));
    liens.forEach((lien) => {
      if (active && lien.dataset.spy === active.id) lien.setAttribute('aria-current', 'true');
      else lien.removeAttribute('aria-current');
    });
  }, { rootMargin: '-40% 0px -55% 0px' });
  sections.forEach((s) => io.observe(s));
}

/* ---------- Onglets (motif ARIA, clavier compris) ---------- */
export function initTabs(tablist, { onChange } = {}) {
  const tabs = () => [...tablist.querySelectorAll('[role="tab"]')];
  const activer = (tab, { focus = false } = {}) => {
    tabs().forEach((t) => {
      const choisi = t === tab;
      t.setAttribute('aria-selected', String(choisi));
      t.tabIndex = choisi ? 0 : -1;
      const panneau = document.getElementById(t.getAttribute('aria-controls'));
      if (panneau) {
        if (choisi && panneau.hidden) {
          panneau.hidden = false;
          if (motionAllowed()) {
            panneau.classList.add('is-entering');
            afterMotion(panneau).then(() => panneau.classList.remove('is-entering'));
          }
        } else if (!choisi) {
          panneau.hidden = true;
        }
      }
    });
    if (focus) tab.focus();
    onChange?.(tab);
  };
  tablist.addEventListener('click', (event) => {
    const tab = event.target.closest('[role="tab"]');
    if (tab) activer(tab);
  });
  tablist.addEventListener('keydown', (event) => {
    const liste = tabs();
    const i = liste.indexOf(document.activeElement);
    if (i < 0) return;
    const cibles = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: liste.length - 1 };
    if (!(event.key in cibles)) return;
    event.preventDefault();
    activer(liste[(cibles[event.key] + liste.length) % liste.length], { focus: true });
  });
  return { activer };
}

/* ---------- Infobulles (survol, focus, Échap) ---------- */
export function initTooltips(root = document) {
  root.querySelectorAll('.tooltip-wrap').forEach((wrap) => {
    if (wrap.dataset.ready) return;
    wrap.dataset.ready = 'true';
    const ouvrir = () => wrap.classList.add('is-open');
    const fermer = () => wrap.classList.remove('is-open');
    wrap.addEventListener('mouseenter', ouvrir);
    wrap.addEventListener('mouseleave', fermer);
    wrap.addEventListener('focusin', ouvrir);
    wrap.addEventListener('focusout', fermer);
    wrap.addEventListener('keydown', (event) => { if (event.key === 'Escape') fermer(); });
  });
}

/* ---------- Fenêtres modales ---------- */
function fermerDialog(dialog) {
  if (!dialog.open || dialog.classList.contains('is-closing')) return;
  if (!motionAllowed()) { dialog.close(); return; }
  dialog.classList.add('is-closing');
  afterMotion(dialog).then(() => {
    dialog.classList.remove('is-closing');
    dialog.close();
  });
}

export function initDialogs() {
  document.addEventListener('click', (event) => {
    const ouvreur = event.target.closest('[data-open-dialog]');
    if (ouvreur) {
      document.getElementById(ouvreur.dataset.openDialog)?.showModal();
      return;
    }
    const fermeur = event.target.closest('[data-close-dialog]');
    if (fermeur) fermerDialog(fermeur.closest('dialog'));
  });
  document.querySelectorAll('dialog').forEach((dialog) => {
    // Clic sur le fond : ferme
    dialog.addEventListener('click', (event) => { if (event.target === dialog) fermerDialog(dialog); });
    dialog.addEventListener('cancel', (event) => { event.preventDefault(); fermerDialog(dialog); });
  });
}

/* ---------- Notifications ---------- */
export function toast(message, { type = 'info', duree = 4200 } = {}) {
  const zone = document.querySelector('[data-toasts]');
  const el = document.createElement('div');
  el.className = `toast${type === 'error' ? ' toast--error' : ''}`;
  el.innerHTML = `${icon(type === 'error' ? 'alert' : 'check-circle')}<span></span>`;
  el.querySelector('span').textContent = message;
  zone.append(el);
  setTimeout(() => {
    el.classList.add('is-leaving');
    afterMotion(el).then(() => el.remove());
  }, duree);
}

/* ---------- Annonces pour lecteurs d'écran ---------- */
export function announce(message) {
  const zone = document.querySelector('[data-announcer]');
  zone.textContent = '';
  // Laisse au lecteur d'écran le temps de voir le changement
  setTimeout(() => { zone.textContent = message; }, 60);
}

/* ---------- Copier une commande ---------- */
export function initCopy() {
  document.addEventListener('click', async (event) => {
    const bouton = event.target.closest('[data-action="copy"]');
    if (!bouton) return;
    try {
      await navigator.clipboard.writeText(bouton.dataset.copy);
      bouton.dataset.state = 'success';
      toast('Commande copiée dans le presse-papiers.');
      setTimeout(() => { delete bouton.dataset.state; }, 1800);
    } catch {
      toast('Copie impossible : sélectionnez la commande à la main.', { type: 'error' });
    }
  });
}
