"""Boîte à outils graphique de la charte « Signal ».

Charte propre à la présentation de Relais, pensée pour ne ressembler à aucune
autre vidéo du portfolio :
- fond graphite quadrillé comme un plan, un seul signal vert-volt ;
- titres en Space Grotesk, tout ce que la machine écrit en Geist Mono ;
- motifs : le relais du logo, des fils parcourus d'impulsions, un terminal,
  une instrumentation de pupitre (minutage, chapitre, avancement) ;
- transitions : ligne de balayage, volets, grille qui commute, barre de relais.

Chaque image est dessinée en 3840×2160 (facteur SS) puis réduite de moitié :
contours et textes lissés sans traitement local. Les coordonnées passées aux
fonctions restent celles d'une image 1920×1080.
"""

import math
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from timeline import BEAT, DURATION, HEIGHT as H, SCENES, SS, WIDTH as W

# ── Palette (celle de l'interface web, thème sombre) ──────────────────────
GRAPHITE = (10, 13, 12)
PANEL = (17, 22, 20)
PANEL_2 = (22, 29, 26)
PANEL_3 = (31, 40, 36)
LINE = (44, 55, 50)
GRID = (19, 26, 23)
GRID_MAJOR = (26, 35, 31)
INK = (237, 242, 236)
INK_2 = (179, 192, 184)
INK_3 = (122, 136, 128)
VOLT = (207, 242, 74)
VOLT_D = (127, 159, 34)
ON_VOLT = (11, 15, 5)
RED = (255, 112, 99)
AMBER = (246, 193, 75)
MINT = (99, 219, 168)

# ── Polices (SIL OFL, téléchargées par build.py) ──────────────────────────
FONT_DIR = Path(os.environ.get("RELAIS_FONT_DIR", Path(__file__).with_name(".fonts")))
FONT_FILES = {
    "display": "SpaceGrotesk[wght].ttf",
    "sans": "Geist[wght].ttf",
    "mono": "GeistMono[wght].ttf",
}


@lru_cache(maxsize=None)
def font(kind, size, weight=500):
    """kind : display | sans | mono ; size en pixels de l'image 1080p."""
    f = ImageFont.truetype(str(FONT_DIR / FONT_FILES[kind]), max(1, int(round(size * SS))))
    try:
        f.set_variation_by_axes([weight])
    except (OSError, AttributeError):
        pass
    return f


# ── Temps & courbes ───────────────────────────────────────────────────────

def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def prog(u, start, dur):
    """Avancement 0→1 d'une animation qui commence à `start` et dure `dur`."""
    return clamp((u - start) / dur) if dur > 0 else float(u >= start)


def lerp(a, b, p):
    return a + (b - a) * p


def mix(c1, c2, p):
    return tuple(int(round(lerp(a, b, p))) for a, b in zip(c1, c2))


def e_out(p):
    return 1 - (1 - p) ** 3


def e_quint(p):
    return 1 - (1 - p) ** 5


def e_in(p):
    return p ** 3


def e_in_out(p):
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def e_back(p, s=1.6):
    c = s + 1
    return 1 + c * (p - 1) ** 3 + s * (p - 1) ** 2


def beat_pulse(t, decay=0.14):
    """1 sur chaque temps puis décroissance : l'image « respire » avec la musique."""
    return math.exp(-((t % BEAT) / decay))


# ── Fond quadrillé (calculé une fois par processus) ───────────────────────

@lru_cache(maxsize=1)
def background():
    img = Image.new("RGB", (W * SS, H * SS), GRAPHITE)
    d = ImageDraw.Draw(img)
    cell = 48 * SS
    for k, x in enumerate(range(0, W * SS + 1, cell)):
        d.line([(x, 0), (x, H * SS)], fill=GRID_MAJOR if k % 4 == 0 else GRID, width=SS)
    for k, y in enumerate(range(0, H * SS + 1, cell)):
        d.line([(0, y), (W * SS, y)], fill=GRID_MAJOR if k % 4 == 0 else GRID, width=SS)
    # Vignette : le quadrillage s'efface vers les bords
    yy, xx = np.mgrid[0:H * SS, 0:W * SS].astype(np.float32)
    dist = np.sqrt(((xx - W * SS / 2) / (W * SS * 0.62)) ** 2 + ((yy - H * SS / 2) / (H * SS * 0.62)) ** 2)
    k = np.clip(1.0 - 0.55 * dist ** 2, 0.38, 1.0)[..., None]
    base = np.array(GRAPHITE, np.float32)
    arr = np.asarray(img, np.float32)
    arr = base + (arr - base) * k
    return Image.fromarray(arr.astype(np.uint8))


@lru_cache(maxsize=64)
def _glow_mask(r):
    n = int(2 * r * SS)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    d = np.sqrt((xx - n / 2) ** 2 + (yy - n / 2) ** 2) / (r * SS)
    a = np.clip(np.exp(-(d ** 2) * 3.2) - 0.04, 0, 1) / 0.96
    return Image.fromarray((a * 255).astype(np.uint8), "L")


# ── Géométrie des tracés ──────────────────────────────────────────────────

def _lengths(pts):
    segs = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    return segs, sum(segs)


def point_at(pts, p):
    """Point situé à la fraction p (0→1) de la longueur d'une ligne brisée."""
    segs, total = _lengths(pts)
    target = clamp(p) * total
    for (a, b), s in zip(zip(pts, pts[1:]), segs):
        if target <= s or s == segs[-1] and b == pts[-1]:
            q = target / s if s else 0
            return (lerp(a[0], b[0], clamp(q)), lerp(a[1], b[1], clamp(q)))
        target -= s
    return pts[-1]


def partial(pts, p):
    """Début de la ligne brisée jusqu'à la fraction p (tracé qui se dessine)."""
    if p <= 0:
        return [pts[0], pts[0]]
    segs, total = _lengths(pts)
    target = clamp(p) * total
    out = [pts[0]]
    for (a, b), s in zip(zip(pts, pts[1:]), segs):
        if target >= s:
            out.append(b)
            target -= s
        else:
            q = target / s if s else 0
            out.append((lerp(a[0], b[0], q), lerp(a[1], b[1], q)))
            break
    return out


# ── Image en cours de dessin ──────────────────────────────────────────────

class Frame:
    """Image 3840×2160 ; toutes les méthodes prennent des coordonnées 1080p."""

    def __init__(self, base=None):
        self.im = (base if base is not None else background()).copy()
        self.d = ImageDraw.Draw(self.im, "RGBA")

    @staticmethod
    def c(color, alpha=1.0):
        return (*color[:3], int(round(255 * clamp(alpha))))

    # Formes
    def rect(self, x0, y0, x1, y1, color, alpha=1.0, r=0, outline=None, width=1.0, oalpha=None):
        if alpha <= 0 and (outline is None or (oalpha if oalpha is not None else alpha) <= 0):
            return
        box = [x0 * SS, y0 * SS, x1 * SS, y1 * SS]
        fill = self.c(color, alpha) if color is not None and alpha > 0 else None
        out = self.c(outline, alpha if oalpha is None else oalpha) if outline is not None else None
        w = max(1, int(round(width * SS)))
        if r:
            self.d.rounded_rectangle(box, int(r * SS), fill=fill, outline=out, width=w)
        else:
            self.d.rectangle(box, fill=fill, outline=out, width=w)

    def circle(self, cx, cy, r, color, alpha=1.0, outline=None, width=1.0):
        if r <= 0 or alpha <= 0:
            return
        box = [(cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS]
        self.d.ellipse(box, fill=self.c(color, alpha) if color else None,
                       outline=self.c(outline, alpha) if outline else None, width=max(1, int(width * SS)))

    def line(self, pts, color, width=2.0, alpha=1.0, caps=True):
        if alpha <= 0 or len(pts) < 2:
            return
        w = width * SS
        sp = [(x * SS, y * SS) for x, y in pts]
        self.d.line(sp, fill=self.c(color, alpha), width=max(1, int(round(w))), joint="curve")
        if caps and w > 2:
            for x, y in (sp[0], sp[-1]):
                self.d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=self.c(color, alpha))

    def arc(self, cx, cy, r, a0, a1, color, width=2.0, alpha=1.0):
        box = [(cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS]
        self.d.arc(box, a0, a1, fill=self.c(color, alpha), width=max(1, int(width * SS)))

    def glow(self, cx, cy, r, color, alpha=1.0):
        if alpha <= 0.01:
            return
        mask = _glow_mask(int(r))
        if alpha < 0.99:
            mask = mask.point(lambda v, a=alpha: int(v * a))
        solid = Image.new("RGB", mask.size, color[:3])
        self.im.paste(solid, (int((cx - r) * SS), int((cy - r) * SS)), mask)

    # Texte
    @staticmethod
    def tw(s, f, tracking=0.0):
        return (f.getlength(s) + tracking * SS * max(0, len(s) - 1)) / SS

    def text(self, x, y, s, f, color, alpha=1.0, anchor="ls", tracking=0.0):
        if alpha <= 0 or not s:
            return
        fill = self.c(color, alpha)
        if not tracking:
            self.d.text((x * SS, y * SS), s, font=f, fill=fill, anchor=anchor)
            return
        width = self.tw(s, f, tracking)
        if anchor[0] == "m":
            x -= width / 2
        elif anchor[0] == "r":
            x -= width
        cx = x * SS
        for ch in s:
            self.d.text((cx, y * SS), ch, font=f, fill=fill, anchor="l" + anchor[1])
            cx += f.getlength(ch) + tracking * SS

    def rise(self, x, y, s, f, color, u, start, dur=0.5, dist=26, anchor="ls", tracking=0.0, alpha=1.0):
        """Texte qui apparaît en montant (fondu + translation)."""
        p = e_out(prog(u, start, dur))
        if p > 0:
            self.text(x, y + (1 - p) * dist, s, f, color, alpha * p, anchor, tracking)

    def typed(self, x, y, s, f, color, u, start, cps=48, alpha=1.0, anchor="ls", cursor=True):
        """Texte tapé caractère par caractère, avec un curseur qui clignote."""
        n = int(max(0.0, u - start) * cps)
        if n <= 0:
            return
        shown = s[:n]
        self.text(x, y, shown, f, color, alpha, anchor)
        if cursor and n < len(s) + 6:
            cx = x + self.tw(shown, f) + 4
            if (u * 2.5) % 1 < 0.6 or n < len(s):
                self.rect(cx, y - f.size / SS * 0.78, cx + f.size / SS * 0.5, y + 4, VOLT, alpha)

    def finish(self):
        return self.im.reduce(SS)


# ── Éléments de la charte ─────────────────────────────────────────────────

def logo(fr, cx, cy, size, p=1.0, alpha=1.0, scale=1.0, dark=False):
    """Le relais de Relais : carré volt, tracé qui monte d'un niveau à l'autre."""
    s = size * scale
    if s <= 1 or alpha <= 0:
        return
    k = s / 30
    x0, y0 = cx - s / 2, cy - s / 2
    fr.rect(x0, y0, x0 + s, y0 + s, INK if dark else VOLT, alpha, r=8 * k)
    pts = [(x0 + 6.5 * k, y0 + 20 * k), (x0 + 12 * k, y0 + 20 * k), (x0 + 18 * k, y0 + 10 * k), (x0 + 23.5 * k, y0 + 10 * k)]
    ink = GRAPHITE if dark else ON_VOLT
    fr.line(partial(pts, p), ink, 2.6 * k, alpha)
    if p > 0:
        fr.circle(*pts[0], 2.3 * k, ink, alpha)
    if p >= 0.98:
        fr.circle(*pts[-1], 2.3 * k * e_back(prog(p, 0.98, 0.02)), ink, alpha)


def mark(fr, x, y, g, f, color, alpha=1.0):
    """Repère d'une ligne de journal : › ! en texte, ✓ dessiné (absent des polices)."""
    if g == "✓":
        s = f.size / SS
        icon(fr, "check", x + s * 0.32, y - s * 0.34, s * 0.95, color, alpha, width=max(2.0, s * 0.11))
    else:
        fr.text(x, y, g, f, color, alpha)


def corners(fr, x0, y0, x1, y1, color=INK_3, alpha=1.0, n=18, width=1.6):
    for (x, y, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        fr.line([(x + dx * n, y), (x, y), (x, y + dy * n)], color, width, alpha, caps=False)


def eyebrow(fr, x, y, index, label, u, start, alpha=1.0):
    """« 02 — LE CONSTAT » en monospace, avec un trait qui se dessine."""
    p = e_out(prog(u, start, 0.5))
    if p <= 0:
        return
    f = font("mono", 19, 500)
    fr.text(x, y, index, f, VOLT, alpha * p, tracking=3)
    w = fr.tw(index, f, 3) + 14
    fr.text(x + w, y, label.upper(), f, INK_3, alpha * p, tracking=3)
    w2 = w + fr.tw(label.upper(), f, 3) + 16
    fr.line([(x + w2, y - 7), (x + w2 + 46 * p, y - 7)], LINE, 1.5, alpha * p, caps=False)


def title(fr, x, y, s, u, start, size=78, color=INK, alpha=1.0, anchor="ls"):
    fr.rise(x, y, s, font("display", size, 640), color, u, start, 0.6, 34, anchor, tracking=-size * 0.03, alpha=alpha)


def chip(fr, x, y, s, fg, bg, alpha=1.0, size=17, anchor="l"):
    """Puce d'état en monospace ; (x, y) = bord gauche (ou droit) et centre vertical."""
    f = font("mono", size, 560)
    w = fr.tw(s, f) + 22
    if anchor == "r":
        x -= w
    fr.rect(x, y - size * 0.9, x + w, y + size * 0.9, bg, alpha, r=5)
    fr.text(x + 11, y + 1, s, f, fg, alpha, anchor="lm")
    return w


def wire(fr, pts, p=1.0, alpha=1.0, color=LINE, lit=VOLT, width=2.5):
    """Fil de connexion ; la partie déjà parcourue par le signal s'allume."""
    fr.line(pts, color, width, alpha, caps=False)
    if p > 0:
        fr.line(partial(pts, p), lit, width + 0.5, alpha, caps=False)


def pulse(fr, pts, p, alpha=1.0, r=7):
    """Impulsion lumineuse qui court le long d'un fil."""
    if 0 < p < 1:
        x, y = point_at(pts, p)
        fr.glow(x, y, r * 5, VOLT, 0.45 * alpha)
        fr.circle(x, y, r, VOLT, alpha)


def icon(fr, name, cx, cy, s, color, alpha=1.0, width=2.4):
    """Icônes au trait (dans une boîte de 24 unités, centrée sur cx, cy)."""
    k = s / 24
    X = lambda v: cx + (v - 12) * k  # noqa: E731
    Y = lambda v: cy + (v - 12) * k  # noqa: E731
    L = lambda *pts: fr.line([(X(a), Y(b)) for a, b in pts], color, width, alpha)  # noqa: E731
    if name == "sheet":
        L((14, 3), (7, 3), (5, 5), (5, 19), (7, 21), (17, 21), (19, 19), (19, 8), (14, 3))
        L((14, 3), (14, 8), (19, 8))
        L((8.5, 13), (15.5, 13))
        L((8.5, 16.5), (15.5, 16.5))
        L((12, 11), (12, 18.5))
    elif name == "scan":
        L((4, 8), (4, 4), (8, 4))
        L((16, 4), (20, 4), (20, 8))
        L((20, 16), (20, 20), (16, 20))
        L((8, 20), (4, 20), (4, 16))
        L((7, 12), (17, 12))
    elif name == "mail":
        fr.rect(X(3), Y(5), X(21), Y(19), None, alpha, r=2 * k, outline=color, width=width)
        L((3.5, 6.5), (12, 12.5), (20.5, 6.5))
    elif name == "form":
        fr.rect(X(5), Y(4), X(19), Y(21), None, alpha, r=2 * k, outline=color, width=width)
        L((9, 4), (9, 3), (15, 3), (15, 4))
        L((8.5, 10), (15.5, 10))
        L((8.5, 13.5), (15.5, 13.5))
        L((8.5, 17), (12.5, 17))
    elif name == "bars":
        L((4, 20), (20, 20))
        L((7, 16), (7, 11))
        L((12, 16), (12, 6))
        L((17, 16), (17, 8))
    elif name == "globe":
        fr.circle(X(12), Y(12), 9 * k, None, alpha, outline=color, width=width)
        L((3, 12), (21, 12))
        fr.d.ellipse([X(8.2) * SS, Y(3) * SS, X(15.8) * SS, Y(21) * SS], outline=fr.c(color, alpha), width=int(width * SS))
    elif name == "clock":
        fr.circle(X(12), Y(12), 9 * k, None, alpha, outline=color, width=width)
        L((12, 7), (12, 12), (15, 14))
    elif name == "check":
        L((5, 12.5), (9.5, 17), (19, 7.5))
    elif name == "alert":
        L((12, 4), (21, 20), (3, 20), (12, 4))
        L((12, 10), (12, 14))
        fr.circle(X(12), Y(17), 1.1 * k, color, alpha)
    elif name == "cursor":
        pts = [(X(a), Y(b)) for a, b in ((5, 3), (19, 10), (13, 12), (11, 18), (5, 3))]
        fr.d.polygon([(x * SS, y * SS) for x, y in pts], fill=fr.c(color, alpha), outline=fr.c(GRAPHITE, alpha))


def node(fr, cx, cy, size, name, label, state=0.0, alpha=1.0, meta=None, meta_alpha=1.0):
    """Nœud du pipeline. state : 0 attente, 0→1 activation, >1 terminé."""
    if alpha <= 0:
        return
    act = clamp(state)
    done = state > 1.0
    half = size / 2
    if act > 0 and not done:
        fr.glow(cx, cy, size * 1.25, VOLT, 0.35 * act * alpha)
    bg = mix(PANEL_2, VOLT, act) if not done else PANEL_3
    fg = mix(INK_3, ON_VOLT, act) if not done else VOLT
    sc = 1 + 0.07 * math.sin(math.pi * act) if not done else 1
    h2 = half * sc
    fr.rect(cx - h2, cy - h2, cx + h2, cy + h2, bg, alpha, r=size * 0.22,
            outline=LINE if act < 0.5 and not done else None, width=1.5)
    icon(fr, name, cx, cy, size * 0.48, fg, alpha, width=size * 0.045)
    fr.text(cx, cy + half + 38, label, font("sans", 24, 600), INK if (act > 0 or done) else INK_2, alpha, anchor="ms")
    if meta:
        fr.text(cx, cy + half + 70, meta, font("mono", 18, 500), INK_3, alpha * meta_alpha, anchor="ms")


# ── Instrumentation du pupitre (au-dessus des scènes et des transitions) ──

def chrome_layer(t, index, u, alpha=1.0):
    """Calque RGBA 1080p : logo, chapitre, minutage, avancement, coins."""
    layer = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    fr = Frame.__new__(Frame)
    fr.im = layer
    fr.d = ImageDraw.Draw(layer, "RGBA")
    a = alpha
    logo(fr, 78, 66, 30, 1.0, a)
    fr.text(106, 74, "RELAIS", font("mono", 17, 600), INK, a, tracking=4)
    fr.text(106 + fr.tw("RELAIS", font("mono", 17, 600), 4) + 14, 74, "/ AUTOMATISATION DE PROCESSUS",
            font("mono", 17, 450), INK_3, a, tracking=3)
    key, name, *_ = SCENES[index]
    fr.text(W - 64, 74, f"{index + 1:02d}/{len(SCENES):02d} · {name.upper()}", font("mono", 17, 500), INK_2, a,
            anchor="rs", tracking=3)
    secs = t
    fr.circle(70, H - 70, 5, VOLT, a * (0.45 + 0.55 * beat_pulse(t, 0.22)))
    fr.text(86, H - 63, f"T+{int(secs // 60):02d}:{secs % 60:05.2f}  ·  PIPELINE ACTIF", font("mono", 17, 500),
            INK_3, a, tracking=2)
    # Avancement : un segment par scène
    seg, gap = 46, 8
    x = W - 64 - len(SCENES) * seg - (len(SCENES) - 1) * gap
    from timeline import scene_end, scene_start
    for i in range(len(SCENES)):
        fr.rect(x, H - 72, x + seg, H - 67, LINE, a)
        if i < index:
            fr.rect(x, H - 72, x + seg, H - 67, INK_3, a)
        elif i == index:
            p = clamp((t - scene_start(i)) / (scene_end(i) - scene_start(i)))
            fr.rect(x, H - 72, x + seg * p, H - 67, VOLT, a)
        x += seg + gap
    corners(fr, 32, 32, W - 32, H - 32, LINE, a, n=22, width=2)
    return layer.reduce(SS)


# ── Transitions (sur des images 1080p) ────────────────────────────────────

def composite_transition(a, b, kind, p, t):
    """a : scène sortante, b : scène entrante, p : avancement 0→1."""
    A = np.asarray(a, np.float32)
    B = np.asarray(b, np.float32)
    volt = np.array(VOLT, np.float32)
    if kind == "scan":
        y = int(round(e_in_out(p) * H))
        out = A.copy()
        out[:y] = B[:y]
        band = np.exp(-((np.arange(H) - y) / 9.0) ** 2)[:, None, None]
        out = out + (volt - out) * (band * 0.85 * math.sin(math.pi * p))
    elif kind == "volets":
        n = 8
        out = A.copy()
        cw = W / n
        for j in range(n):
            pj = e_in_out(clamp((p - j * 0.05) / (1 - (n - 1) * 0.05)))
            y = int(round(pj * H))
            x0, x1 = int(j * cw), int((j + 1) * cw)
            out[:y, x0:x1] = B[:y, x0:x1]
            if 0 < pj < 1:
                out[max(0, y - 3):y, x0:x1] = volt
    elif kind == "grille":
        nx, ny = 16, 9
        cw, ch = W / nx, H / ny
        out = A.copy()
        for i in range(nx):
            for j in range(ny):
                thr = (i + j) / (nx + ny - 2) * 0.72
                q = clamp((p - thr) / 0.28)
                x0, x1, y0, y1 = int(i * cw), int((i + 1) * cw), int(j * ch), int((j + 1) * ch)
                if q >= 0.5:
                    out[y0:y1, x0:x1] = B[y0:y1, x0:x1]
                if 0 < q < 1:
                    flash = math.sin(math.pi * q) * 0.75
                    out[y0:y1, x0:x1] = out[y0:y1, x0:x1] + (volt - out[y0:y1, x0:x1]) * flash
    elif kind == "relais":
        bar = 220
        x = int(round(lerp(-bar, W, e_in_out(p))))
        out = A.copy()
        cut = max(0, min(W, x + bar // 2))
        out[:, :cut] = B[:, :cut]
        x0, x1 = max(0, x), max(0, min(W, x + bar))
        if x1 > x0:
            out[:, x0:x1] = volt
            stripes = (np.arange(H) // 18) % 2 == 0
            xs0, xs1 = x0, min(x1, x0 + 10)
            out[stripes, xs0:xs1] = np.array(ON_VOLT, np.float32)
    else:
        out = A + (B - A) * p
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
