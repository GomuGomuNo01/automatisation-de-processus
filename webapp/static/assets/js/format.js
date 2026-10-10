/* ==========================================================================
   FORMATAGE (fr-FR) et petits utilitaires de rendu
   ========================================================================== */

const entier = new Intl.NumberFormat('fr-FR');
const decimal = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 });
const euros = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const heureFmt = new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' });
const jourFmt = new Intl.DateTimeFormat('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' });

export const nombre = (n) => entier.format(n);
export const prix = (n) => euros.format(n);

export function pluriel(n, singulier, plurielForme = `${singulier}s`) {
  return `${nombre(n)} ${n > 1 ? plurielForme : singulier}`;
}

export function octets(n) {
  if (n < 1024) return `${nombre(n)} o`;
  if (n < 1024 * 1024) return `${decimal.format(n / 1024)} Ko`;
  return `${decimal.format(n / (1024 * 1024))} Mo`;
}

export function duree(ms) {
  if (ms < 1000) return `${nombre(Math.max(0, Math.round(ms)))} ms`;
  return `${decimal.format(ms / 1000)} s`;
}

/** « dans 3 min », « dans 2 h 15 », « dans 5 j » */
export function dans(secondes) {
  if (secondes <= 0) return 'immédiatement';
  if (secondes < 3600) return `dans ${Math.max(1, Math.round(secondes / 60))} min`;
  if (secondes < 86400) {
    const h = Math.floor(secondes / 3600);
    const m = Math.round((secondes % 3600) / 60);
    return m ? `dans ${h} h ${String(m).padStart(2, '0')}` : `dans ${h} h`;
  }
  return `dans ${Math.round(secondes / 86400)} j`;
}

export const heure = (date) => heureFmt.format(date);
export const jourHeure = (date) => `${jourFmt.format(date)} · ${heureFmt.format(date)}`;

/** Échappe une valeur avant insertion dans du HTML (noms de produits importés, etc.) */
export function esc(valeur) {
  return String(valeur ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

export function icon(nom, classe = '') {
  return `<svg class="icon ${classe}" aria-hidden="true"><use href="#i-${nom}"/></svg>`;
}
