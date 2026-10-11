"""Scène 5 (24-28 s) : les deux modes de planification, des frises qui défilent."""

import math

from kit import (INK, INK_2, INK_3, LINE, PANEL, PANEL_2, VOLT, VOLT_D, Frame, clamp, e_out, eyebrow, font, prog,
                 title)

MODES = [
    # (titre, sous-titre, minutes de temps simulé par seconde de vidéo, horizon affiché en minutes, tâches)
    ("MODE TEST", "pour tout valider en quelques minutes", 1.6, 6.0,
     [("Surveillance du stock", "toutes les 1 min", 1, 0), ("Rapport hebdomadaire", "toutes les 2 min", 2, 2),
      ("Scraping des prix", "toutes les 3 min", 3, 3)]),
    ("MODE PRODUCTION", "pour la surveillance réelle", 300.0, 1440.0,
     [("Surveillance du stock", "toutes les 60 min", 60, 0), ("Rapport hebdomadaire", "vendredi à 8 h", 10080, 1700),
      ("Scraping des prix", "toutes les 4 h", 240, 240)]),
]


def horloge(fr, cx, cy, r, ang, a):
    fr.circle(cx, cy, r, None, a, outline=INK_2, width=2.2)
    fr.line([(cx, cy), (cx + r * 0.62 * math.sin(ang), cy - r * 0.62 * math.cos(ang))], VOLT, 2.6, a)
    fr.line([(cx, cy), (cx + r * 0.45 * math.sin(ang / 12), cy - r * 0.45 * math.cos(ang / 12))], INK, 2.6, a)


def render(u, t):
    fr = Frame()
    eyebrow(fr, 120, 200, "05", "La planification", u, 0.0)
    title(fr, 120, 272, "Il tourne en boucle, à son rythme.", u, 0.1, size=66)

    for m, (nom, sous, vitesse, horizon, taches) in enumerate(MODES):
        x0 = 120 + m * 860
        x1 = x0 + 820
        y0, y1 = 340, 910
        a = e_out(prog(u, 0.3 + m * 0.18, 0.45))
        if a <= 0:
            continue
        fr.rect(x0, y0, x1, y1, PANEL, a, r=18, outline=LINE, width=1.5)
        horloge(fr, x0 + 52, y0 + 56, 20, max(0.0, u - 0.3) * (6 if m == 0 else 14), a)
        fr.text(x0 + 88, y0 + 52, nom, font("mono", 22, 650), VOLT, a, tracking=3)
        fr.text(x0 + 88, y0 + 82, sous, font("sans", 20, 450), INK_3, a)

        # Temps simulé : il défile beaucoup plus vite en PRODUCTION
        minutes = max(0.0, u - 0.4) * vitesse
        tx0, tx1 = x0 + 40, x1 - 40
        maintenant = tx0 + (tx1 - tx0) * 0.18
        for k, (tache, freq, periode, premier) in enumerate(taches):
            ly = y0 + 170 + k * 128
            la = e_out(prog(u, 0.5 + m * 0.18 + k * 0.1, 0.4))
            fr.text(tx0, ly, tache, font("sans", 23, 600), INK, la)
            fr.text(tx1, ly, freq, font("mono", 19, 500), INK_2, la, anchor="rs")
            piste_y0, piste_y1 = ly + 18, ly + 62
            fr.rect(tx0, piste_y0, tx1, piste_y1, PANEL_2, la, r=8)
            # Repères d'exécution : ils arrivent par la droite et passent la ligne « maintenant »
            debut = minutes - horizon * 0.18
            n0 = math.ceil((debut - premier) / periode) if periode else 0
            n = n0
            while True:
                quand = premier + n * periode
                if quand > minutes + horizon * 0.82:
                    break
                x = maintenant + (quand - minutes) / horizon * (tx1 - tx0)
                if tx0 + 4 < x < tx1 - 4:
                    passe = quand <= minutes
                    recent = clamp(1 - (minutes - quand) / (horizon * 0.06)) if passe else 0
                    col = VOLT if passe else VOLT_D
                    w = 2.5 + 3 * recent
                    fr.rect(x - w / 2, piste_y0 + 8, x + w / 2, piste_y1 - 8, col, la * (0.55 + 0.45 * passe), r=1)
                    if recent > 0:
                        fr.glow(x, (piste_y0 + piste_y1) / 2, 36, VOLT, 0.35 * recent * la)
                n += 1
            fr.rect(maintenant - 1.5, piste_y0 - 6, maintenant + 1.5, piste_y1 + 6, INK, la)
        fa = e_out(prog(u, 0.8, 0.4))
        fr.text(tx0 + (maintenant - tx0) + 8, y1 - 30, "maintenant", font("mono", 17, 500), INK_3, fa)

    ba = e_out(prog(u, 1.4, 0.5))
    fr.text(120, 975, "Deux modes, un seul code : les intervalles viennent du fichier .env.",
            font("mono", 21, 500), INK_2, ba)
    return fr
