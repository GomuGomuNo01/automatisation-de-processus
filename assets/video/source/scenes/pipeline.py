"""Scène 3 (10-18 s) : le signal parcourt le pipeline, les ruptures se détectent, les décisions tombent."""

from kit import (mark, AMBER, INK, INK_2, INK_3, LINE, ON_VOLT, PANEL, PANEL_2, RED, VOLT, Frame, chip, clamp, e_out,
                 eyebrow, font, lerp, node, prog, pulse, title, wire)

NOEUDS = [
    (330, "sheet", "Inventaire", "20 produits"),
    (760, "scan", "Détection", "12 ruptures"),
    (1190, "mail", "Alerte email", "envoyé + .xlsx"),
    (1620, "form", "Formulaire", "Received!"),
]
Y_NOEUDS = 420
# (activation, fin) de chaque nœud, en secondes de scène
ACTIVATION = [(1.0, 1.9), (1.9, 4.4), (5.0, 5.6), (6.2, 99)]
FILS = [(1.25, 1.9), (4.45, 5.0), (5.65, 6.2)]          # passage de l'impulsion

PRODUITS = [  # inventaire gaming : (nom, quantité, seuil)
    ("Manette Xbox Series X", 4, 10),
    ("Casque Gaming HyperX", 0, 8),
    ("Clavier Gaming RGB", 12, 15),
    ("Tapis Gaming XL", 18, 12),
    ("Écran Gaming 144 Hz", 25, 10),
    ("Webcam 4K Elgato", 1, 5),
]


def etat(u, i):
    a, b = ACTIVATION[i]
    if u < a:
        return 0.0
    if u < b:
        return min(1.0, (u - a) / 0.3)
    return 1.5


def render(u, t):
    fr = Frame()
    eyebrow(fr, 120, 200, "03", "Le pipeline", u, 0.0)
    title(fr, 120, 272, "Un pipeline qui décide seul.", u, 0.1, size=66)

    # Fils et impulsions entre les nœuds
    for i in range(3):
        a = e_out(prog(u, 0.45 + i * 0.12, 0.4))
        x0 = NOEUDS[i][0] + 70
        x1 = NOEUDS[i + 1][0] - 70
        pts = [(x0, Y_NOEUDS), (x1, Y_NOEUDS)]
        s, e = FILS[i]
        wire(fr, pts, prog(u, s, e - s), a)
        pulse(fr, pts, prog(u, s, e - s), a)
    for i, (x, ic, label, meta) in enumerate(NOEUDS):
        a = e_out(prog(u, 0.3 + i * 0.12, 0.4))
        st = etat(u, i)
        node(fr, x, Y_NOEUDS, 116, ic, label, st, a, meta, meta_alpha=1.0 if st > 0 else 0.0)

    # Panneau inventaire : quantité face au seuil, les ruptures virent au rouge
    pa = e_out(prog(u, 2.0, 0.45))
    px0, py0, px1, py1 = 120, 590, 1000, 975
    if pa > 0:
        fr.rect(px0, py0, px1, py1, PANEL, pa, r=16, outline=LINE, width=1.5)
        fr.text(px0 + 30, py0 + 44, "inventaire_gaming_multimedia.xlsx", font("mono", 19, 500), INK_3, pa)
        rouge = prog(u, 3.3, 0.4)
        compte = int(round(12 * clamp((u - 3.3) / 0.8)))
        fr.text(px1 - 30, py0 + 46, f"{compte:>2} ruptures / 20", font("mono", 22, 600),
                RED if compte else INK_3, pa * (0.3 + 0.7 * rouge), anchor="rs")
    fn = font("sans", 22, 500)
    echelle = 300 / 26
    bx = 520
    for i, (nom, q, s) in enumerate(PRODUITS):
        y = py0 + 100 + i * 44
        ra = e_out(prog(u, 2.2 + i * 0.08, 0.35))
        if ra <= 0:
            continue
        rupture = q <= s
        fr.text(px0 + 30, y + 8, nom, fn, INK_2, ra)
        grow = e_out(prog(u, 2.4 + i * 0.08, 0.7))
        col = INK_3 if not rupture else tuple(int(lerp(c1, c2, prog(u, 3.3 + i * 0.05, 0.3)))
                                              for c1, c2 in zip(INK_3, RED))
        w = max(3, q * echelle * grow)
        fr.rect(bx, y - 9, bx + w, y + 9, col, ra, r=4)
        sx = bx + s * echelle
        fr.rect(sx - 1.5, y - 15, sx + 1.5, y + 15, INK, ra)
        if rupture and u > 3.4 + i * 0.05:
            chip(fr, px1 - 30, y, "RUPTURE", RED, (60, 22, 20), e_out(prog(u, 3.4 + i * 0.05, 0.25)), size=15,
                 anchor="r")
        elif not rupture and u > 3.4:
            chip(fr, px1 - 30, y, "OK", INK_3, PANEL_2, e_out(prog(u, 3.4, 0.25)), size=15, anchor="r")

    # Journal des décisions
    la = e_out(prog(u, 2.0, 0.45))
    jx0, jy0, jx1, jy1 = 1060, 590, 1800, 975
    if la > 0:
        fr.rect(jx0, jy0, jx1, jy1, (7, 9, 8), la, r=16, outline=LINE, width=1.5)
        fr.text(jx0 + 30, jy0 + 44, "journal du cycle", font("mono", 19, 500), INK_3, la)
    fm = font("mono", 23, 500)
    lignes = [
        (2.4, "›", INK_3, "Lecture de l'inventaire…"),
        (3.5, "!", AMBER, "PRODUITS EN ALERTE  12/20"),
        (4.3, "✓", VOLT, "12 > 0       → email d'alerte"),
        (5.4, "✓", VOLT, "12 ≥ seuil 3 → formulaire d'urgence"),
        (6.4, "✓", VOLT, "Form submitted · « Received! »"),
    ]
    for k, (start, glyphe, col, s) in enumerate(lignes):
        if u < start:
            continue
        y = jy0 + 104 + k * 52
        mark(fr, jx0 + 30, y, glyphe, fm, col, e_out(prog(u, start, 0.2)))
        fr.typed(jx0 + 66, y, s, fm, INK if glyphe != "›" else INK_2, u, start, cps=55, cursor=k == len(lignes) - 1)

    # La règle, rappelée en bas du journal
    ra = e_out(prog(u, 6.9, 0.45))
    if ra > 0:
        f = font("mono", 20, 600)
        s = "règle : RUPTURE si Quantité ≤ Seuil"
        w = fr.tw(s, f) + 36
        fr.rect(jx0 + 30, jy1 - 70, jx0 + 30 + w, jy1 - 26, VOLT, ra, r=8)
        fr.text(jx0 + 48, jy1 - 41, s, f, ON_VOLT, ra)
    return fr
