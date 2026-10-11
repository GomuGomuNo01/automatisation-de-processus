/* ==========================================================================
   RÉSULTATS : tuiles chiffrées, un onglet par automatisation, fichiers
   Graphiques : marques fines, une seule série (ou statut avec icône + libellé),
   valeurs toujours lisibles sans survol (tableaux et étiquettes directes),
   infobulle en complément.
   ========================================================================== */

import { dans, duree, esc, heure, icon, jourHeure, nombre, octets, pluriel, prix } from './format.js';
import { initTabs } from './ui.js';
import { motionAllowed, finePointer } from './motion.js';

const vue = document.getElementById('vue-execution');
const el = {
  section: vue.querySelector('[data-results]'),
  stats: vue.querySelector('[data-stats]'),
  tabs: vue.querySelector('[data-results-tabs]'),
  panneaux: vue.querySelector('[data-results-panels]'),
  fichiers: vue.querySelector('[data-files]'),
  archive: vue.querySelector('[data-archive]'),
};

let planActif = null;   // plans de la dernière exécution (onglet Planification)
let ecouteursPoses = false;
let debutExecution = 0;

export function viderResultats() {
  el.section.hidden = true;
  el.stats.innerHTML = '';
  el.tabs.innerHTML = '';
  el.panneaux.innerHTML = '';
  el.fichiers.innerHTML = '';
}

/* ---------- Infobulle partagée des graphiques ---------- */
let bulle = null;
function infobulle() {
  if (!bulle) {
    bulle = document.createElement('div');
    bulle.className = 'viz-tip';
    bulle.setAttribute('aria-hidden', 'true');
    document.body.append(bulle);
  }
  return bulle;
}
function brancherInfobulles(racine) {
  const montrer = (cible) => {
    const tip = infobulle();
    tip.innerHTML = cible.dataset.tip;
    const rect = cible.getBoundingClientRect();
    tip.style.left = `${Math.min(window.innerWidth - 120, Math.max(120, rect.left + rect.width / 2))}px`;
    tip.style.top = `${rect.top}px`;
    tip.classList.add('is-visible');
  };
  const cacher = () => bulle?.classList.remove('is-visible');
  racine.addEventListener('pointerover', (event) => {
    const cible = event.target.closest('[data-tip]');
    if (cible && finePointer()) montrer(cible);
  });
  racine.addEventListener('pointerout', (event) => {
    if (event.target.closest('[data-tip]')) cacher();
  });
  racine.addEventListener('focusin', (event) => {
    const cible = event.target.closest('[data-tip]');
    if (cible) montrer(cible);
  });
  racine.addEventListener('focusout', cacher);
  window.addEventListener('scroll', cacher, { passive: true });
}

/** Les barres poussent depuis leur base à l'affichage (transform uniquement) */
function fairePousser(racine) {
  if (!motionAllowed()) return;
  const marques = racine.querySelectorAll('.bullet__bar, .bar-row__bar, .timeline__tick');
  marques.forEach((m) => m.style.setProperty('--grow', '0'));
  requestAnimationFrame(() => requestAnimationFrame(() => marques.forEach((m) => m.style.removeProperty('--grow'))));
}

/* ---------- Panneaux ---------- */
function vide(titre, texte, nomIcone = 'minus-circle') {
  return `<div class="panel__empty">${icon(nomIcone)}<strong>${esc(titre)}</strong><span class="small">${esc(texte)}</span></div>`;
}

function note(texte, { type = '', nomIcone = 'info' } = {}) {
  return `<p class="panel__note ${type ? `panel__note--${type}` : ''}">${icon(nomIcone, 'icon--sm')}<span>${texte}</span></p>`;
}

function panneauStock(d) {
  if (!d) return vide('Aucune donnée', 'La détection n\'a pas produit de résultat.');
  const echelle = Math.max(1, ...d.produits.map((p) => Math.max(p.quantite, p.seuil))) * 1.08;
  const lignes = [...d.produits].sort((a, b) =>
    (b.rupture - a.rupture) || (a.quantite / Math.max(1, a.seuil)) - (b.quantite / Math.max(1, b.seuil)));
  const rangees = lignes.map((p) => {
    const ecart = p.seuil - p.quantite;
    const tip = `<strong>${esc(p.produit)}</strong>${nombre(p.quantite)} en stock · seuil ${nombre(p.seuil)}<br><span class="mono">${p.rupture ? `manque ${nombre(Math.max(ecart, 0))} pour repasser le seuil` : `${nombre(-ecart)} au-dessus du seuil`}</span>`;
    return `
      <tr>
        <td>${esc(p.produit)}</td>
        <td><div class="bullet ${p.rupture ? 'bullet--rupture' : ''}" style="--w:${(p.quantite / echelle).toFixed(4)};--s:${(p.seuil / echelle).toFixed(4)}" data-tip="${esc(tip)}" tabindex="0" aria-label="${esc(`${p.produit} : ${p.quantite} en stock, seuil ${p.seuil}`)}"><span class="bullet__bar"></span><span class="bullet__seuil"></span></div></td>
        <td class="num">${nombre(p.quantite)}</td>
        <td class="num">${nombre(p.seuil)}</td>
        <td>${p.rupture ? `<span class="chip chip--danger">${icon('alert')}Rupture</span>` : `<span class="chip chip--ok">${icon('check')}OK</span>`}</td>
      </tr>`;
  }).join('');
  return `
    <div class="panel__intro">
      <p>${d.ruptures ? `<strong>${pluriel(d.ruptures, 'produit')}</strong> à leur seuil ou en dessous, sur ${nombre(d.total)}. Les plus critiques en premier.` : 'Aucun produit sous son seuil : stock nominal.'}</p>
      <div class="legend" aria-hidden="true">
        <span class="legend__item"><span class="legend__swatch" style="background:var(--viz-critical)"></span>En rupture</span>
        <span class="legend__item"><span class="legend__swatch" style="background:var(--viz-muted)"></span>Au-dessus du seuil</span>
        <span class="legend__item"><span class="legend__tick"></span>Seuil minimum</span>
      </div>
    </div>
    <div class="table-wrap bullet-table">
      <table class="table">
        <caption class="visually-hidden">Quantité en stock et seuil minimum de chaque produit</caption>
        <thead><tr><th scope="col">Produit</th><th scope="col">Stock et seuil</th><th scope="col" class="col-num">Qté</th><th scope="col" class="col-num">Seuil</th><th scope="col">Statut</th></tr></thead>
        <tbody>${rangees}</tbody>
      </table>
    </div>
    ${note(`Fichier généré : <span class="mono">${esc(d.fichier)}</span> (les produits en rupture, colonne Statut = RUPTURE).`)}`;
}

function statutEnvoi(d) {
  const envoi = d.envoi ?? { etat: 'non_demande' };
  if (envoi.etat === 'envoye') {
    return `<div class="receipt__response">${icon('check-circle')}
      <span><strong>Email envoyé à ${esc(d.a)}</strong><span class="mono">Gmail · SMTP SSL · ${esc(envoi.heure)} · pensez à regarder les indésirables</span></span>
    </div>`;
  }
  if (envoi.etat === 'non_demande') {
    return note('Aucune adresse indiquée : l\'email n\'a pas été envoyé. Renseignez votre adresse à l\'étape 03 de la démo pour le recevoir, ou téléchargez le .eml pour l\'ouvrir dans votre messagerie, pièce jointe comprise.');
  }
  return note(`<strong>Email non envoyé.</strong> ${esc(envoi.message)} Le .eml reste téléchargeable ci-dessous.`,
    { type: 'warning', nomIcone: 'alert' });
}

function panneauEmail(d, etape) {
  if (!d) return vide('Pas d\'alerte', etape?.resume || 'Aucune rupture : aucun email à envoyer.', 'mail');
  return `
    ${statutEnvoi(d)}
    <div class="mail">
      <dl class="mail__head">
        <div class="mail__row"><dt>De</dt><dd>${esc(d.de)}</dd></div>
        <div class="mail__row"><dt>À</dt><dd>${esc(d.a)}</dd></div>
        ${d.repondre_a ? `<div class="mail__row"><dt>Rép. à</dt><dd>${esc(d.repondre_a)}</dd></div>` : ''}
        <div class="mail__row"><dt>Objet</dt><dd class="mail__subject">${esc(d.objet)}</dd></div>
        <div class="mail__row"><dt>Pièce j.</dt><dd><span class="mail__attachment">${icon('sheet', 'icon--sm')}${esc(d.piece_jointe)}</span></dd></div>
      </dl>
      <iframe class="mail__frame" title="Aperçu du contenu de l'email d'alerte" sandbox="" referrerpolicy="no-referrer" loading="lazy" data-srcdoc></iframe>
    </div>
    <p><a class="btn btn--secondary" href="${esc(lienFichier(d.fichier))}" download>${icon('download', 'icon--sm')}Télécharger l'email (.eml)</a></p>`;
}

function panneauFormulaire(d, etape) {
  if (!d) return vide('Formulaire non déclenché', etape?.resume || '', 'form');
  if (!d.declenche) {
    return vide('Formulaire non déclenché', `${pluriel(d.ruptures, 'rupture')}, sous le seuil de ${d.seuil}. Il se déclenche à partir de ${d.seuil} ruptures.`, 'form');
  }
  if (d.erreur || !d.reussie) {
    return `
      <div class="receipt__response receipt__response--error">${icon('x-circle')}
        <span><strong>Soumission non confirmée</strong><span class="small">${esc(d.erreur || 'Le site n\'a pas renvoyé la page de confirmation attendue.')}</span></span>
      </div>
      ${note(`Formulaire visé : <span class="mono">${esc(d.url_formulaire)}</span>. Relancez dans un instant : le site de test peut être momentanément indisponible.`, { type: 'warning', nomIcone: 'alert' })}`;
  }
  const champs = d.saisies.map(([libelle, valeur], i) =>
    `<div class="receipt__field" style="--i:${i}"><dt>${esc(libelle)}</dt><dd>${esc(valeur)}</dd></div>`).join('');
  return `
    <div class="panel__intro"><p>Déclenché car <strong>${nombre(d.ruptures)} ruptures ≥ seuil ${nombre(d.seuil)}</strong>. Les champs ont été remplis un par un, puis le formulaire a été soumis.</p></div>
    <div class="receipt">
      <dl class="receipt__fields">${champs}</dl>
      <div class="receipt__response">${icon('check-circle')}
        <span><strong>${esc(d.titre)} · « ${esc(d.message)} »</strong><span class="mono">HTTP ${d.statut} · ${esc(d.url_resultat)} · ${duree(d.duree_ms)}</span></span>
      </div>
    </div>
    ${note(`Formulaire de test public : <span class="mono">${esc(d.url_formulaire)}</span>. En local, Selenium remplit la même page dans Chrome.`)}`;
}

function panneauProduction(d, etape) {
  if (!d) return vide('Rapport hebdomadaire non généré', etape?.resume || '', 'bars');
  const max = Math.max(1, ...d.produits.map((p) => p.total));
  const pas = Math.pow(10, Math.floor(Math.log10(max)));
  const borne = Math.ceil(max / pas) * pas;
  const graduations = [0, borne / 2, borne].map((v) => `<span>${nombre(v)}</span>`).join('');
  const barres = d.produits.map((p) => {
    const tip = `<strong>${esc(p.produit)}</strong>${nombre(p.total)} unités sur la semaine<br><span class="mono">${d.jours.map((j, i) => `${j.slice(0, 3)}. ${nombre(p.par_jour[i])}`).join(' · ')}</span>`;
    return `
      <div class="bar-row" tabindex="0" data-tip="${esc(tip)}" aria-label="${esc(`${p.produit} : ${p.total} unités`)}">
        <span class="bar-row__label">${esc(p.produit)}</span>
        <span class="bar-row__track"><span class="bar-row__bar" style="--w:${(p.total / borne).toFixed(4)}"></span><span class="bar-row__value">${nombre(p.total)}</span></span>
      </div>`;
  }).join('');
  const tete = d.jours.map((j) => `<th scope="col" class="col-num">${esc(j)}</th>`).join('');
  const corps = d.produits.map((p) => `<tr><th scope="row">${esc(p.produit)}</th>${p.par_jour.map((v) => `<td class="num">${nombre(v)}</td>`).join('')}<td class="num"><strong>${nombre(p.total)}</strong></td></tr>`).join('');
  return `
    <div class="panel__intro"><p>Production totale de la semaine par produit (${pluriel(d.jours.length, 'jour')}, ${pluriel(d.lignes, 'ligne')} fusionnées).</p></div>
    <div class="bars" role="list" aria-label="Production de la semaine par produit">${barres.replaceAll('class="bar-row"', 'class="bar-row" role="listitem"')}</div>
    <div class="chart-axis" aria-hidden="true"><span></span><span class="chart-axis__ticks">${graduations}</span></div>
    <details class="details">
      <summary>${icon('arrow-right', 'icon--sm')}Détail jour par jour (onglet 1 du rapport)</summary>
      <div class="table-wrap"><table class="table"><thead><tr><th scope="col">Produit</th>${tete}<th scope="col" class="col-num">Semaine</th></tr></thead><tbody>${corps}</tbody></table></div>
    </details>
    ${note(`Fichier généré : <span class="mono">${esc(d.fichier)}</span> · onglets « Detail journalier » et « Recapitulatif semaine ».`)}`;
}

function etoiles(n) {
  return `<span class="stars" role="img" aria-label="${n} sur 5">${Array.from({ length: 5 }, (_, i) =>
    `<svg class="icon ${i < n ? 'is-on' : ''}" aria-hidden="true"><use href="#i-star"/></svg>`).join('')}</span>`;
}

function panneauPrix(d, etape) {
  if (!d) return vide('Relevé non effectué', etape?.resume || '', 'globe');
  const valeurs = d.produits.map((p) => p.prix_num).filter((v) => typeof v === 'number');
  const moyenne = valeurs.length ? valeurs.reduce((a, b) => a + b, 0) / valeurs.length : 0;
  const tuiles = valeurs.length ? `
    <dl class="price-stats">
      <div class="stat"><dt class="stat__label">Prix le plus bas</dt><dd class="stat__value">${prix(Math.min(...valeurs))} $</dd></div>
      <div class="stat"><dt class="stat__label">Prix moyen</dt><dd class="stat__value">${prix(moyenne)} $</dd></div>
      <div class="stat"><dt class="stat__label">Prix le plus haut</dt><dd class="stat__value">${prix(Math.max(...valeurs))} $</dd></div>
    </dl>` : '';
  const source = {
    direct: note(`Page lue en direct : <span class="mono">${esc(d.url)}</span>`, { nomIcone: 'globe' }),
    cache: note(`Page lue il y a moins de 10 minutes, résultat réutilisé pour ménager le site : <span class="mono">${esc(d.url)}</span>`, { nomIcone: 'clock' }),
    secours: note(`Le site ne répondait pas : <strong>copie de secours du ${esc(d.date)}</strong> du même catalogue.`, { type: 'warning', nomIcone: 'alert' }),
  }[d.source] ?? '';
  const lignes = d.produits.map((p) => `
    <tr>
      <td>${esc(p.produit)}</td>
      <td class="num">${esc(p.prix)}</td>
      <td>${etoiles(p.note)}</td>
      <td class="scrape-table__desc">${esc(p.description)}</td>
    </tr>`).join('');
  return `
    ${tuiles}
    <div class="table-wrap scrape-table">
      <table class="table">
        <caption class="visually-hidden">Produits relevés sur le catalogue en ligne</caption>
        <thead><tr><th scope="col">Produit</th><th scope="col" class="col-num">Prix</th><th scope="col">Note</th><th scope="col" class="scrape-table__desc-col">Description</th></tr></thead>
        <tbody>${lignes}</tbody>
      </table>
    </div>
    ${source}
    ${note(`Fichier généré : <span class="mono">${esc(d.fichier)}</span>`)}`;
}

function rendreFrise(plan) {
  const horizon = plan.horizon_s;
  const libelleHorizon = horizon >= 86400 ? `+${Math.round(horizon / 86400)} j` : `+${Math.round(horizon / 60)} min`;
  const milieu = horizon >= 86400 ? `+${Math.round(horizon / 172800 * 10) / 10} j` : `+${Math.round(horizon / 120)} min`;
  return plan.taches.map((t) => {
    const dense = t.prochaines.length > 40;
    const ticks = t.prochaines.map((s, i) =>
      `<span class="timeline__tick ${s === 0 ? 'timeline__tick--now' : ''} ${dense ? 'timeline__tick--dense' : ''}" style="--x:${(s / horizon).toFixed(5)};--i:${Math.min(i, 40)}"></span>`).join('');
    const prochaine = t.prochaines.find((s) => s > 0) ?? t.prochaines[0];
    const date = new Date(debutExecution + prochaine * 1000);
    const quand = prochaine >= 86400 ? jourHeure(date) : heure(date);
    return `
      <div class="timeline__lane">
        <div class="timeline__lane-head">
          <span class="timeline__lane-title">${esc(t.titre)} <span class="tag">${esc(t.cas)}</span></span>
          <span class="timeline__lane-freq">${esc(t.frequence)}</span>
        </div>
        <div class="timeline__track" role="img" aria-label="${esc(`${t.titre} : ${pluriel(t.prochaines.length, 'exécution')} sur la période, prochaine ${dans(prochaine)}`)}">${ticks}</div>
        <p class="timeline__next">Prochaine exécution : <strong>${esc(quand)}</strong> (${dans(prochaine)})${t.cle === 'surveillance' ? ' · premier cycle lancé immédiatement' : ''}</p>
      </div>`;
  }).join('') + `<div class="timeline__axis" aria-hidden="true"><span>maintenant</span><span>${milieu}</span><span>${libelleHorizon}</span></div>`;
}

function panneauPlanification(d) {
  if (!d) return vide('Planification indisponible', '');
  planActif = d.plans;
  const choix = ['TEST', 'PROD'].map((m) => `
    <label class="segmented__option">
      <input class="segmented__input" type="radio" name="plan_mode" value="${m}"${m === d.mode ? ' checked' : ''}>
      <span class="segmented__label"><span class="segmented__title">${m === 'TEST' ? 'TEST' : 'PRODUCTION'}</span><span class="segmented__desc">${m === 'TEST' ? '10 prochaines minutes' : '7 prochains jours'}</span></span>
    </label>`).join('');
  return `
    <div class="panel__intro"><p>Ce que le planificateur exécuterait à partir de maintenant, calculé avec la bibliothèque <span class="mono">schedule</span> et les intervalles du fichier .env. Comparez les deux modes&nbsp;:</p></div>
    <div class="segmented timeline-toggle" role="radiogroup" aria-label="Mode affiché">${choix}</div>
    <div class="timeline" data-timeline>${rendreFrise(d.plans[d.mode])}</div>`;
}

/* ---------- Tuiles chiffrées ---------- */
function rendreStats(etat) {
  const stock = etat.resultats.cas1;
  const tuiles = [
    ['Produits analysés', stock ? nombre(stock.total) : '—', etat.debut?.inventaire ?? ''],
    ['En rupture', stock ? nombre(stock.ruptures) : '—', stock ? `${Math.round((stock.ruptures / Math.max(1, stock.total)) * 100)} % de l'inventaire` : '', stock?.ruptures ? 'stat__value--danger' : ''],
    ['Fichiers générés', nombre(etat.fin.fichiers.length), 'Excel et email, prêts à télécharger'],
    ['Durée côté serveur', duree(etat.fin.duree_ms), 'pour les six automatisations'],
  ];
  el.stats.innerHTML = tuiles.map(([label, valeur, meta, classe = ''], i) => `
    <div class="stat" style="--i:${i}">
      <dt class="stat__label">${esc(label)}</dt>
      <dd class="stat__value ${classe}">${esc(valeur)}</dd>
      <dd class="stat__meta">${esc(meta)}</dd>
    </div>`).join('');
}

/* ---------- Fichiers ---------- */
let execId = '';
function lienFichier(nom) {
  return `api/executions/${execId}/fichiers/${encodeURIComponent(nom)}`;
}

function rendreFichiers(fin) {
  el.fichiers.innerHTML = fin.fichiers.map((f, i) => `
    <li>
      <a class="file" href="${esc(f.url)}" download style="--i:${i}">
        <span class="file__icon">${icon(f.nom.endsWith('.eml') ? 'mail' : 'sheet')}</span>
        <span class="file__text"><span class="file__label">${esc(f.libelle)}</span><span class="file__name">${octets(f.taille)} · ${esc(f.nom)}</span></span>
        <span class="file__dl">${icon('download')}</span>
        <span class="visually-hidden">Télécharger</span>
      </a>
    </li>`).join('');
  el.archive.href = fin.archive.url;
  el.archive.setAttribute('download', fin.archive.nom);
}

/* ---------- Assemblage ---------- */
const ONGLETS = [
  { cle: 'cas1', titre: 'Stock', rendre: panneauStock, compte: (d) => d?.ruptures },
  { cle: 'cas3', titre: 'Email', rendre: panneauEmail },
  { cle: 'cas6', titre: 'Formulaire', rendre: panneauFormulaire },
  { cle: 'cas2', titre: 'Production', rendre: panneauProduction },
  { cle: 'cas5', titre: 'Prix', rendre: panneauPrix, compte: (d) => d?.produits.length },
  { cle: 'cas4', titre: 'Planification', rendre: panneauPlanification },
];

export function rendreResultats(etat) {
  execId = etat.fin.id;
  debutExecution = Date.now();
  rendreStats(etat);
  rendreFichiers(etat.fin);

  const etapes = Object.fromEntries((etat.etapes ?? []).map((e) => [e.cle, e]));
  const resumes = {};
  etat.etapes.forEach((e) => {
    const li = vue.querySelector(`[data-step="${e.cle}"] [data-resume]`);
    resumes[e.cle] = { resume: li?.textContent ?? '' };
  });

  el.tabs.innerHTML = ONGLETS.map((o, i) => {
    const compte = o.compte?.(etat.resultats[o.cle]);
    return `<button class="tab" type="button" role="tab" id="tab-${o.cle}" aria-controls="panel-${o.cle}" aria-selected="${i === 0}" tabindex="${i === 0 ? 0 : -1}">
      ${esc(o.titre)}${compte !== undefined && compte !== null ? `<span class="tab__count">${nombre(compte)}</span>` : ''}
      <span class="visually-hidden"> (cas ${etapes[o.cle] ? etapes[o.cle].cas : ''})</span>
    </button>`;
  }).join('');
  el.panneaux.innerHTML = ONGLETS.map((o, i) => `
    <div class="tab-panel panel" role="tabpanel" id="panel-${o.cle}" aria-labelledby="tab-${o.cle}" tabindex="0"${i === 0 ? '' : ' hidden'}>
      ${o.rendre(etat.resultats[o.cle], resumes[o.cle])}
    </div>`).join('');

  // Aperçu de l'email : srcdoc dans une iframe sans script ni accès à la page
  const cadre = el.panneaux.querySelector('[data-srcdoc]');
  if (cadre && etat.resultats.cas3) cadre.srcdoc = etat.resultats.cas3.html;

  // Nouvelle liste d'onglets à chaque rendu : pas d'écouteurs en double après une relance
  const tablist = el.tabs.cloneNode(true);
  el.tabs.replaceWith(tablist);
  el.tabs = tablist;
  initTabs(el.tabs, {
    onChange: (tab) => {
      const panneau = document.getElementById(tab.getAttribute('aria-controls'));
      fairePousser(panneau);
    },
  });
  if (!ecouteursPoses) {
    ecouteursPoses = true;
    brancherInfobulles(el.panneaux);
    el.panneaux.addEventListener('change', (event) => {
      if (!event.target.matches('input[name="plan_mode"]') || !planActif) return;
      const frise = el.panneaux.querySelector('[data-timeline]');
      frise.innerHTML = rendreFrise(planActif[event.target.value]);
      fairePousser(frise);
    });
  }

  el.section.hidden = false;
  fairePousser(el.panneaux.querySelector('.tab-panel:not([hidden])'));
}
