"""Scène 4 (18-24 s) : les six automatisations, puis le séquenceur qui les enchaîne."""

from kit import (INK, INK_2, INK_3, LINE, ON_VOLT, PANEL, PANEL_2, VOLT, Frame, chip, e_out, eyebrow, font, icon,
                 mix, prog, title)

CAS = [
    ("1", "scan", "Détection des ruptures", ("Lit l'inventaire Excel et repère", "chaque produit sous son seuil."),
     "pandas · openpyxl"),
    ("2", "bars", "Rapport hebdomadaire", ("Additionne cinq jours de production", "dans un classeur à deux onglets."),
     "pandas"),
    ("3", "mail", "Alerte email", ("Prévient dès la première rupture,", "rapport Excel en pièce jointe."),
     "Gmail · SMTP SSL"),
    ("4", "clock", "Planification", ("Relance chaque tâche à son rythme,", "en TEST comme en PRODUCTION."),
     "schedule"),
    ("5", "globe", "Scraping des prix", ("Relève nom, prix et note", "d'un catalogue en ligne."), "Selenium"),
    ("6", "form", "Formulaire d'urgence", ("Rempli et soumis tout seul", "au-delà du seuil critique."), "Selenium"),
]
ORDRE = [0, 2, 5, 1, 4, 3]       # ordre d'exécution dans le pipeline : 1 → 3 → 6 → 2 → 5 → 4
W_CARTE, H_CARTE, GAP = 520, 250, 40
X0, Y0 = 140, 340


def render(u, t):
    fr = Frame()
    eyebrow(fr, 120, 200, "04", "Les six cas", u, 0.0)
    title(fr, 120, 272, "Six automatisations, un seul pipeline.", u, 0.1, size=66)

    # Séquenceur : une carte s'allume par temps, dans l'ordre du pipeline
    pas = int((u - 2.6) / 0.5) if u >= 2.6 else -1
    for i, (num, ic, nom, desc, tag) in enumerate(CAS):
        col, row = i % 3, i // 3
        x = X0 + col * (W_CARTE + GAP)
        y = Y0 + row * (H_CARTE + GAP)
        a = e_out(prog(u, 0.45 + i * 0.22, 0.45))
        if a <= 0:
            continue
        dy = (1 - a) * 30
        rang = ORDRE.index(i)
        actif = rang == pas
        vu = 0 <= rang < pas or (pas >= len(ORDRE))
        lum = e_out(prog(u, 2.6 + rang * 0.5, 0.18)) if actif else 0.0
        if actif:
            fr.glow(x + W_CARTE / 2, y + dy + H_CARTE / 2, 300, VOLT, 0.16 * lum)
        fr.rect(x, y + dy, x + W_CARTE, y + dy + H_CARTE, mix(PANEL, PANEL_2, lum), a, r=18,
                outline=VOLT if (actif or vu) else LINE, width=2.5 if actif else 1.5,
                oalpha=a if (actif or vu) else a)
        # Numéro
        fr.rect(x + 28, y + dy + 28, x + 28 + 74, y + dy + 64, VOLT if (actif or vu) else PANEL_2, a, r=6)
        fr.text(x + 65, y + dy + 54, f"CAS {num}", font("mono", 18, 650), ON_VOLT if (actif or vu) else INK_3, a,
                anchor="ms")
        icon(fr, ic, x + W_CARTE - 58, y + dy + 48, 40, VOLT if actif else INK_2, a, width=2.2)
        fr.text(x + 28, y + dy + 116, nom, font("display", 34, 620), INK, a, tracking=-0.6)
        for k, l in enumerate(desc):
            fr.text(x + 28, y + dy + 156 + k * 30, l, font("sans", 21, 450), INK_2, a)
        chip(fr, x + 28, y + dy + H_CARTE - 26, tag, INK_3, PANEL_2 if not actif else (40, 50, 30), a, size=15)
    # Légende du séquenceur
    la = e_out(prog(u, 2.5, 0.4))
    if la > 0:
        f = font("mono", 19, 500)
        fr.text(140, 930, "ORDRE D'EXÉCUTION", f, INK_3, la, tracking=3)
        x = 140 + fr.tw("ORDRE D'EXÉCUTION", f, 3) + 24
        for k, idx in enumerate(ORDRE):
            on = k <= pas
            fr.text(x, 930, CAS[idx][0], font("mono", 22, 650), VOLT if on else INK_3, la)
            x += 22
            if k < len(ORDRE) - 1:
                fr.text(x + 6, 930, "→", f, INK_3, la)
                x += 36
    return fr
