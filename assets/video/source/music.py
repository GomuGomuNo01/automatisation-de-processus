"""Musique originale de la présentation : électro minimale, 120 BPM, ré mineur.

Tout est synthétisé ici à partir d'oscillateurs et de bruit (numpy seul) :
aucun échantillon, aucune boucle ni aucun extrait d'une œuvre existante. Le
morceau est une création propre au projet, libre de droits tiers.

Instrumentation : kick, clap, charleston, « clics de relais » (percussion
signature : de brèves impulsions comme un relais qui commute), basse roulante,
arpège pincé avec écho, nappes, cloches et effets de transition. Grille
d'accords sur quatre mesures : Rém9 – Si♭maj7(9) – Solm9 – La7sus4 → La7.

La musique suit l'image (voir timeline.py et scenes/) : le kick entre avec le
constat, une note tinte à chaque nœud du pipeline et à chaque carte allumée par
le séquenceur, la démo a son clic et sa notification, et le logo final sonne
une cloche avant l'accord de fin.
"""

import wave

import numpy as np

from timeline import BAR, BEAT, DURATION, STEP, boundaries

SR = 44100
TAIL = 1.0
N = int((DURATION + TAIL) * SR)
rng = np.random.default_rng(2026)

# Grille d'accords (notes MIDI) et fondamentales de la basse, par mesure (cycle de 4)
ACCORDS = [
    [50, 53, 57, 60, 64],          # Rém9
    [46, 50, 53, 57, 60],          # Si♭maj7(9)
    [55, 58, 62, 65, 69],          # Solm9
    [57, 62, 64, 67],              # La7sus4 (la tierce arrive au 3e temps)
]
BASSES = [38, 34, 31, 33]          # ré, si♭, sol, la


# ── Outils ────────────────────────────────────────────────────────────────

def hz(note):
    return 440.0 * 2 ** ((note - 69) / 12)


def tvec(dur):
    return np.arange(int(dur * SR)) / SR


def spectral(x, lo=None, hi=None):
    """Filtre doux appliqué dans le domaine fréquentiel (passe-haut / passe-bas)."""
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR) + 1e-9
    gain = np.ones_like(f)
    if lo:
        gain *= 1 / np.sqrt(1 + (lo / f) ** 4)
    if hi:
        gain *= 1 / np.sqrt(1 + (f / hi) ** 4)
    return np.fft.irfft(spec * gain, len(x))


def noise(dur):
    return rng.standard_normal(int(dur * SR))


def onepole(x, cutoffs):
    """Passe-bas à coupure variable (une coupure par échantillon)."""
    a = 1 - np.exp(-2 * np.pi * np.asarray(cutoffs) / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


class Piste:
    """Piste stéréo sur laquelle on pose des sons à un instant donné."""

    def __init__(self):
        self.l = np.zeros(N)
        self.r = np.zeros(N)

    def add(self, t, sig, gain=1.0, pan=0.0):
        i = int(round(t * SR))
        if i >= N or i + len(sig) <= 0:
            return
        if i < 0:                       # son commencé avant 0 : on garde la partie audible
            sig, i = sig[-i:], 0
        j = min(N, i + len(sig))
        s = sig[: j - i] * gain
        self.l[i:j] += s * np.sqrt((1 - pan) / 2)
        self.r[i:j] += s * np.sqrt((1 + pan) / 2)

    def stereo(self):
        return np.stack([self.l, self.r])


# ── Instruments ───────────────────────────────────────────────────────────

def kick():
    t = tvec(0.45)
    f = 44 + 120 * np.exp(-t / 0.04)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.17)
    click = spectral(noise(0.45), lo=2500) * np.exp(-t / 0.003) * 0.35
    return np.tanh(1.6 * (body + click))


def clap():
    t = tvec(0.35)
    env = np.zeros_like(t)
    for k, d in enumerate((0.0, 0.011, 0.022)):
        m = t >= d
        env[m] += np.exp(-(t[m] - d) / (0.007 if k < 2 else 0.11))
    return spectral(noise(0.35), lo=900, hi=4200) * env * 0.8


def hat(open_=False):
    dur = 0.32 if open_ else 0.07
    t = tvec(dur)
    return spectral(noise(dur), lo=7200) * np.exp(-t / (0.11 if open_ else 0.018))


def relais():
    """Clic de relais : impulsion carrée très brève + souffle métallique."""
    t = tvec(0.03)
    carre = np.sign(np.sin(2 * np.pi * 2350 * t)) * np.exp(-t / 0.0028)
    souffle = spectral(noise(0.03), lo=5000) * np.exp(-t / 0.004) * 0.6
    return carre * 0.5 + souffle


def basse(note, dur, brillance=1.0):
    t = tvec(dur)
    f = hz(note)
    sig = 0.7 * np.sin(2 * np.pi * f * t)                          # sous-basse
    for k in range(1, 12):
        if f * k > 4000:
            break
        sig += (0.55 / k) * np.sin(2 * np.pi * f * k * t) * np.exp(-t * (6 + k * 5 / brillance))
    env = np.minimum(1, t / 0.004) * np.exp(-t / (dur * 0.55))
    return np.tanh(1.3 * sig) * env


def pince(note, vel=1.0):
    """Arpège pincé : harmoniques impaires qui s'éteignent vite (filtre qui se ferme)."""
    t = tvec(0.42)
    f = hz(note)
    sig = np.zeros_like(t)
    for k in (1, 3, 5, 7, 9):
        sig += (1 / k) * np.sin(2 * np.pi * f * k * t) * np.exp(-t * (4 + k * 3.2))
    return sig * np.minimum(1, t / 0.002) * np.exp(-t / 0.2) * vel


def nappe(notes, dur, brillance=0.5):
    t = tvec(dur)
    sig = np.zeros_like(t)
    for n in notes:
        for detune in (-0.07, 0.07):
            f = hz(n + detune)
            for k in range(1, 9):
                if f * k > 6000:
                    break
                sig += (1 / k) * np.exp(-k * (1.1 - brillance)) * np.sin(2 * np.pi * f * k * t + rng.uniform(0, 6.28))
    att, rel = 0.35, 0.6
    env = np.minimum(1, t / att) * np.minimum(1, (dur - t) / rel)
    return sig * np.clip(env, 0, 1) / (len(notes) * 2.2)


def cloche(note, dur=1.6):
    t = tvec(dur)
    f = hz(note)
    sig = np.zeros_like(t)
    for ratio, amp, dec in ((1, 1, 0.9), (2.76, 0.45, 0.35), (5.4, 0.25, 0.15), (8.93, 0.12, 0.08)):
        sig += amp * np.sin(2 * np.pi * f * ratio * t) * np.exp(-t / dec)
    return sig * np.minimum(1, t / 0.002)


def souffle(dur=0.9, montee=True):
    """Souffle de transition : bruit dont le filtre s'ouvre (ou se referme)."""
    t = tvec(dur)
    p = t / dur
    coupure = 400 + 7000 * (p if montee else 1 - p) ** 2
    env = np.sin(np.pi * p) ** 2
    return onepole(noise(dur), coupure) * env * 1.6


def montee(dur):
    """Montée avant un temps fort : bruit qui s'ouvre + sinus qui grimpe."""
    t = tvec(dur)
    p = t / dur
    bruit = onepole(noise(dur), 300 + 9000 * p ** 3) * p ** 2
    sweep = np.sin(2 * np.pi * np.cumsum(220 + 900 * p ** 2) / SR) * p ** 3 * 0.25
    return bruit * 1.4 + sweep


def impact():
    t = tvec(1.2)
    sub = np.sin(2 * np.pi * np.cumsum(30 + 45 * np.exp(-t / 0.12)) / SR) * np.exp(-t / 0.45)
    bruit = spectral(noise(1.2), hi=1800) * np.exp(-t / 0.08) * 0.5
    return np.tanh(1.4 * (sub + bruit))


def clic_souris():
    t = tvec(0.04)
    return spectral(noise(0.04), lo=1500, hi=6000) * np.exp(-t / 0.005) + np.sin(2 * np.pi * 1800 * t) * np.exp(-t / 0.004)


# ── Composition ───────────────────────────────────────────────────────────

def accord(bar, temps=0):
    notes = ACCORDS[bar % 4]
    if bar % 4 == 3 and temps >= 2:          # La7sus4 → La7 : la quarte résout sur la tierce
        notes = [57, 61, 64, 67]
    return notes


def compose():
    batterie, basse_p, nappes, arpege, cloches, effets = (Piste() for _ in range(6))
    k_sig, c_sig, h_sig, o_sig, r_sig = kick(), clap(), hat(), hat(True), relais()
    kicks = []

    def section(bar):
        if bar < 3:
            return "intro"
        if bar < 5:
            return "constat"
        if bar < 12:
            return "plein"
        if bar < 14:
            return "pause"
        if bar < 19:
            return "final"
        return "fin"

    for bar in range(20):
        t0 = bar * BAR
        sec = section(bar)
        # Nappes : présentes de bout en bout, plus ouvertes quand le groove est plein
        bril = {"intro": 0.35, "constat": 0.45, "plein": 0.6, "pause": 0.4, "final": 0.65, "fin": 0.5}[sec]
        for pan in (-0.6, 0.6):          # deux voix aux phases différentes : une nappe large
            nappes.add(t0 - 0.15, nappe(accord(bar), BAR + 0.5, bril), 0.8, pan=pan)

        for temps in range(4):
            tb = t0 + temps * BEAT
            # Kick : entre avec le constat, se tait pendant la première mesure de la pause et à la fin
            if sec in ("constat", "plein", "final") or (sec == "pause" and bar == 13):
                batterie.add(tb, k_sig, 0.78)
                kicks.append(tb)
            if sec in ("plein", "final") and temps in (1, 3):
                batterie.add(tb, c_sig, 0.5, pan=0.05)
            if sec in ("constat", "plein", "pause", "final"):
                batterie.add(tb + BEAT / 2, h_sig, 0.42, pan=0.25)
            if sec == "final" and temps % 2 == 1:
                batterie.add(tb + BEAT / 2, o_sig, 0.26, pan=-0.2)

            # Basse : à la noire pendant le constat, roulante (contretemps) ensuite
            racine = BASSES[bar % 4]
            if sec == "constat":
                basse_p.add(tb, basse(racine, 0.42, 0.7), 0.42)
            elif sec in ("plein", "final") or (sec == "pause" and bar == 13):
                for d, oct_ in ((STEP * 2, 0), (STEP * 3, 12 if temps == 3 else 0)):
                    basse_p.add(tb + d, basse(racine + oct_, 0.2, 1.0), 0.38)

        # Clics de relais : le tic-tac régulier du pipeline
        for s in range(16):
            ts = t0 + s * STEP
            if sec == "intro" and bar >= 1 and s % 4 == 0:
                batterie.add(ts, r_sig, 0.10, pan=-0.4 if s % 8 else 0.4)
            elif sec in ("constat", "pause"):
                batterie.add(ts, r_sig, 0.2 if s % 4 == 0 else 0.1, pan=-0.45 if s % 2 else 0.45)
            elif sec in ("plein", "final") and s % 2 == 1:
                batterie.add(ts, r_sig, 0.09, pan=-0.5 if s % 4 == 1 else 0.5)

        # Arpège : entre au milieu du pipeline (mesure 7), filtré pendant la pause
        if 7 <= bar < 19:
            notes = accord(bar)
            motif = [0, 2, 1, 3, 2, 4, 3, 1, 0, 3, 2, 4, 1, 3, 2, 0]
            for s, idx in enumerate(motif):
                n = notes[idx % len(notes)] + 12
                vel = 0.55 if sec == "pause" else (1.0 if s % 4 == 0 else 0.75)
                arpege.add(t0 + s * STEP, pince(n, vel), 0.3, pan=-0.45 if s % 2 else 0.45)

    # ── Accents calés sur l'image ──
    cloches.add(1.6, cloche(74, 2.4), 0.30)                     # le relais du logo se ferme
    cloches.add(2.0, cloche(81, 1.6), 0.12, pan=0.3)            # le nom apparaît
    for t, note in ((11.0, 74), (11.9, 77), (15.0, 81), (16.2, 86)):   # nœuds du pipeline
        cloches.add(t, cloche(note, 1.0), 0.20, pan=0.2)
    for k in range(6):                                          # séquenceur des six cas
        cloches.add(18 + 2.6 + k * 0.5, cloche([74, 77, 81, 79, 84, 86][k], 0.8), 0.15, pan=-0.3 + k * 0.12)
    effets.add(28 + 1.3, clic_souris(), 0.6)                    # clic sur « Lancer le pipeline »
    for k in range(6):                                          # étapes qui se valident
        cloches.add(28 + 1.55 + (k + 1) * 0.42, cloche(86 + [0, 3, 7, 10, 12, 15][k], 0.4), 0.08, pan=0.4)
    cloches.add(28 + 4.35, cloche(81, 1.2), 0.22, pan=0.35)      # notification : l'alerte est arrivée
    cloches.add(28 + 4.55, cloche(86, 1.4), 0.18, pan=0.35)
    cloches.add(34 + 2.25, cloche(74, 3.4), 0.32)               # logo final
    cloches.add(34 + 2.25, cloche(62, 3.4), 0.18)

    # Transitions : souffle à chaque changement de scène, montée et impact sur les temps forts
    for b in boundaries():
        effets.add(b - 0.55, souffle(1.0, montee=True), 0.12, pan=0.0)
    for debut, fin in ((4.0, 6.0), (26.0, 28.0)):
        effets.add(debut, montee(fin - debut), 0.16)
    for t in (6.0, 28.0, 36.25):
        effets.add(t, impact(), 0.5)

    # Accord final : il tient jusqu'à la fin, puis s'éteint
    for pan in (-0.6, 0.6):
        nappes.add(38.0, nappe([50, 57, 62, 64, 69], 3.0, 0.55), 1.0, pan=pan)
    basse_p.add(38.0, basse(38, 2.0, 0.6), 0.5)

    # Compression latérale : nappes, basse et arpège s'effacent sous chaque kick
    temps = np.arange(N) / SR
    duck = np.ones(N)
    for tk in kicks:
        i = int(tk * SR)
        j = min(N, i + int(0.3 * SR))
        duck[i:j] = np.minimum(duck[i:j], 1 - 0.6 * np.exp(-(temps[i:j] - tk) / 0.09))
    for p in (nappes, basse_p, arpege):
        p.l *= duck
        p.r *= duck

    # Écho de l'arpège (3 doubles-croches, ping-pong)
    retard = int(3 * STEP * SR)
    for k, g in enumerate((0.42, 0.22, 0.1), start=1):
        d = retard * k
        src_l, src_r = (arpege.r, arpege.l) if k % 2 else (arpege.l, arpege.r)
        arpege.l[d:] += src_l[:-d] * g
        arpege.r[d:] += src_r[:-d] * g

    sec_mix = (batterie.stereo() * 1.0 + basse_p.stereo() * 1.0 + nappes.stereo() * 1.0
               + arpege.stereo() * 1.0 + cloches.stereo() * 1.0 + effets.stereo() * 1.0)

    # Réverbération (convolution par une réponse de salle synthétique)
    envoi = nappes.stereo() * 0.5 + arpege.stereo() * 0.6 + cloches.stereo() * 0.8 + batterie.stereo() * 0.06
    ir_t = tvec(2.4)
    taille = 1 << int(np.ceil(np.log2(N + len(ir_t))))
    wet = np.zeros_like(sec_mix)
    for c in range(2):
        ir = rng.standard_normal(len(ir_t)) * np.exp(-ir_t / 0.55)
        ir = spectral(ir, lo=200, hi=7000)
        ir /= np.sqrt(np.sum(ir ** 2))
        wet[c] = np.fft.irfft(np.fft.rfft(envoi[c], taille) * np.fft.rfft(ir, taille), taille)[:N]
    mix = sec_mix + wet * 0.35

    # Fondu d'entrée et de sortie, limiteur doux, normalisation
    fade_in = np.minimum(1, temps / 0.05)
    fade_out = np.clip((DURATION - temps) / 1.6, 0, 1) ** 1.5
    mix = mix * fade_in * fade_out
    mix = np.tanh(1.15 * mix / (np.max(np.abs(mix)) + 1e-9)) / np.tanh(1.15)
    return mix * 10 ** (-1.0 / 20)


def write_wav(path, mix):
    data = (np.clip(mix.T, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
