"""Scène 2 (6-10 s) : la routine manuelle, ligne par ligne, puis rayée."""

import math

from kit import (INK, INK_2, INK_3, LINE, PANEL, PANEL_2, VOLT, Frame, corners, e_in_out, e_out, eyebrow, font,
                 icon, prog, title)

TACHES = [
    "Ouvrir chaque fichier Excel d'inventaire",
    "Repérer les produits sous leur seuil",
    "Rédiger l'email d'alerte, recopier la liste",
    "Remplir le bon de commande urgent",
    "Additionner la production, relever les prix",
]


def render(u, t):
    fr = Frame()
    eyebrow(fr, 120, 200, "02", "Le constat", u, 0.0)
    title(fr, 120, 272, "Chaque matin, la même routine.", u, 0.1, size=66)

    # Terminal : la liste des tâches faites à la main
    a = e_out(prog(u, 0.25, 0.45))
    x0, y0, x1, y1 = 120, 340, 1100, 880
    if a > 0:
        fr.rect(x0, y0, x1, y1, PANEL, a, r=18, outline=LINE, width=1.5)
        fr.rect(x0, y0, x1, y0 + 58, PANEL_2, a, r=18)
        fr.rect(x0, y0 + 40, x1, y0 + 58, PANEL_2, a)
        for k in range(3):
            fr.circle(x0 + 30 + k * 22, y0 + 29, 6, LINE, a)
        fr.text(x0 + 110, y0 + 36, "routine.txt — à faire à la main, chaque jour", font("mono", 18, 500), INK_3, a)
    fm = font("mono", 26, 500)
    for i, s in enumerate(TACHES):
        y = y0 + 128 + i * 82
        start = 0.55 + i * 0.32
        if u < start:
            continue
        p = e_out(prog(u, start, 0.3))
        box_x = x0 + 46
        fr.rect(box_x, y - 26, box_x + 30, y + 4, None, p, r=5, outline=INK_3, width=2)
        fr.typed(box_x + 52, y, s, fm, INK, u, start, cps=70, cursor=False)
        # Rayée : Relais prend la tâche en charge
        sp = e_in_out(prog(u, 2.55 + i * 0.13, 0.3))
        if sp > 0:
            w = fr.tw(s, fm)
            fr.line([(box_x + 46, y - 10), (box_x + 52 + (w + 10) * sp, y - 10)], VOLT, 3.5, 1.0, caps=False)
            fr.rect(box_x, y - 26, box_x + 30, y + 4, VOLT, sp, r=5)
            if sp > 0.6:
                icon(fr, "check", box_x + 15, y - 11, 24, (11, 15, 5), 1.0, width=3)

    # Horloge : le temps file, tous les jours
    cx, cy, r = 1490, 560, 205
    ca = e_out(prog(u, 0.45, 0.5))
    if ca > 0:
        fr.circle(cx, cy, r, PANEL, ca, outline=LINE, width=2)
        for k in range(12):
            ang = math.radians(k * 30)
            r0 = r - (26 if k % 3 == 0 else 16)
            fr.line([(cx + r0 * math.sin(ang), cy - r0 * math.cos(ang)),
                     (cx + (r - 8) * math.sin(ang), cy - (r - 8) * math.cos(ang))],
                    INK_2 if k % 3 == 0 else INK_3, 3 if k % 3 == 0 else 2, ca, caps=False)
        turn = max(0.0, u - 0.5) * 1.6
        for length, speed, width, col in ((r * 0.55, 1 / 12, 7, INK), (r * 0.8, 1.0, 4, VOLT)):
            ang = 2 * math.pi * turn * speed
            fr.line([(cx, cy), (cx + length * math.sin(ang), cy - length * math.cos(ang))], col, width, ca)
        fr.circle(cx, cy, 10, VOLT, ca)
    # Légende sous l'horloge : le constat, puis la relève
    f = font("display", 40, 600)
    sortie = e_out(prog(u, 2.85, 0.25))
    entree = e_out(prog(u, 3.05, 0.35))
    if sortie < 1:
        fr.rise(cx, 850 - 24 * sortie, "Tous les jours. À la main.", f, INK_2, u, 1.4, alpha=1 - sortie, anchor="ms")
    if entree > 0:
        fr.text(cx, 850 + (1 - entree) * 24, "Relais prend le relais.", f, VOLT, entree, anchor="ms")
    corners(fr, cx - r - 30, cy - r - 30, cx + r + 30, cy + r + 30, LINE, ca, n=16)
    return fr
