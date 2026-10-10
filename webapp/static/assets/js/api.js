/* ==========================================================================
   API : adresses relatives (l'appli peut être servie sous un préfixe,
   comme /~/+/ sur Streamlit Community Cloud)
   ========================================================================== */

export class ErreurApi extends Error {
  constructor(message, { statut = 0, erreurs = null } = {}) {
    super(message);
    this.statut = statut;
    this.erreurs = erreurs;
  }
}

const MESSAGE_RESEAU = 'Connexion au serveur impossible. Vérifiez votre réseau puis réessayez.';

async function lireErreur(reponse) {
  let donnees = null;
  try { donnees = await reponse.json(); } catch { /* réponse non JSON */ }
  const erreurs = donnees?.erreurs ?? null;
  const message = donnees?.erreur ?? (erreurs ? Object.values(erreurs)[0] : `Erreur du serveur (${reponse.status}).`);
  return new ErreurApi(message, { statut: reponse.status, erreurs });
}

async function envoyer(url, options) {
  let reponse;
  try {
    reponse = await fetch(url, options);
  } catch (e) {
    if (e.name === 'AbortError') throw e;
    throw new ErreurApi(MESSAGE_RESEAU);
  }
  if (!reponse.ok) throw await lireErreur(reponse);
  return reponse;
}

export async function getJSON(url, { signal } = {}) {
  const reponse = await envoyer(url, { headers: { Accept: 'application/json' }, signal });
  return reponse.json();
}

export async function postFormulaire(url, formData, { signal } = {}) {
  const reponse = await envoyer(url, { method: 'POST', body: formData, signal });
  return reponse.json();
}

/**
 * Envoie `corps` en JSON et appelle `surEvenement` pour chaque ligne NDJSON,
 * dès qu'elle arrive (le pipeline rend compte de sa progression en direct).
 */
export async function fluxNDJSON(url, corps, surEvenement, { signal } = {}) {
  const reponse = await envoyer(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/x-ndjson' },
    body: JSON.stringify(corps),
    signal,
  });
  const lecteur = reponse.body.getReader();
  const decodeur = new TextDecoder();
  let tampon = '';
  const vider = (fin) => {
    let i;
    while ((i = tampon.indexOf('\n')) >= 0) {
      const ligne = tampon.slice(0, i).trim();
      tampon = tampon.slice(i + 1);
      if (ligne) surEvenement(JSON.parse(ligne));
    }
    if (fin && tampon.trim()) { surEvenement(JSON.parse(tampon)); tampon = ''; }
  };
  try {
    for (;;) {
      const { value, done } = await lecteur.read();
      if (done) break;
      tampon += decodeur.decode(value, { stream: true });
      vider(false);
    }
  } catch (e) {
    if (e.name === 'AbortError') throw e;
    throw new ErreurApi('La connexion a été interrompue pendant l\'exécution.');
  }
  tampon += decodeur.decode();
  vider(true);
}
