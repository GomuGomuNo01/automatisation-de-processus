"""Scène 6 (28-34 s) : la démo en ligne, un clic, six étapes, l'alerte arrive dans la boîte."""

from kit import (mark, AMBER, GRAPHITE, INK, INK_2, INK_3, LINE, ON_VOLT, PANEL, PANEL_2, VOLT, Frame, chip, clamp, e_back,
                 e_in_out, e_out, eyebrow, font, icon, lerp, prog, title)

ETAPES = ["Détection des ruptures", "Alerte email", "Formulaire d'urgence", "Rapport hebdomadaire",
          "Scraping des prix", "Planification"]
RESUMES = ["12 ruptures sur 20", "envoyé à vous@exemple.com", "Received!", "5 produits · 2 601 unités",
           "9 produits relevés", "toutes les 1 min"]
JOURNAL = [
    ("›", "Lecture : inventaire_gaming_multimedia.xlsx"),
    ("!", "PRODUITS EN ALERTE  12/20"),
    ("✓", "Email envoyé à vous@exemple.com"),
    ("✓", "Formulaire soumis · Received!"),
    ("✓", "rapport_semaine.xlsx — 2 onglets"),
    ("✓", "9 produit(s) relevés en ligne"),
    ("✓", "Pipeline terminé en 0,6 s · 4 fichiers"),
]
CLIC = 1.3
T0 = 1.55            # première étape
PAS = 0.42           # une étape par demi-temps environ


def render(u, t):
    fr = Frame()
    eyebrow(fr, 120, 200, "06", "La démo en ligne", u, 0.0)
    title(fr, 120, 272, "Testez-le en ligne, en un clic.", u, 0.1, size=66)

    # Fenêtre du navigateur
    a = e_out(prog(u, 0.25, 0.5))
    x0, y0, x1, y1 = 120, 330, 1800, 985
    dy = (1 - a) * 40
    y0, y1 = y0 + dy, y1 + dy
    if a <= 0:
        return fr
    fr.rect(x0, y0, x1, y1, PANEL, a, r=20, outline=LINE, width=1.5)
    fr.rect(x0, y0, x1, y0 + 64, PANEL_2, a, r=20)
    fr.rect(x0, y0 + 44, x1, y0 + 64, PANEL_2, a)
    for k in range(3):
        fr.circle(x0 + 32 + k * 22, y0 + 32, 6, LINE, a)
    url = "automatisation-de-processus-cedric.streamlit.app"
    fu = font("mono", 19, 500)
    uw = fr.tw(url, fu) + 70
    ux = (x0 + x1) / 2 - uw / 2
    fr.rect(ux, y0 + 14, ux + uw, y0 + 50, GRAPHITE, a, r=18)
    icon(fr, "globe", ux + 24, y0 + 32, 18, INK_3, a, width=1.6)
    fr.text(ux + 44, y0 + 39, url, fu, INK_2, a)

    # En-tête de la page d'exécution + bouton
    termine = u > T0 + PAS * 6
    fr.text(x0 + 48, y0 + 130, "Pipeline terminé" if termine else ("Pipeline en cours…" if u > CLIC else "Démo interactive"),
            font("display", 40, 620), INK, a, tracking=-1)
    bx0, by0, bx1, by1 = x1 - 400, y0 + 92, x1 - 48, y0 + 148
    press = clamp(1 - abs(u - CLIC) / 0.15)
    clique = u > CLIC
    fr.rect(bx0 + 3 * press, by0 + 3 * press, bx1 - 3 * press, by1 - 3 * press,
            VOLT if not clique else PANEL_2, a, r=10, outline=None if not clique else LINE, width=1.5)
    fb = font("sans", 23, 650)
    libelle = "Lancer le pipeline  →" if not clique else ("Terminé" if termine else "En cours…")
    fr.text((bx0 + bx1) / 2 + (14 if termine else 0), by0 + 37, libelle, fb,
            ON_VOLT if not clique else (VOLT if termine else INK_2), a, anchor="ms")
    if termine:
        icon(fr, "check", (bx0 + bx1) / 2 - fr.tw(libelle, fb) / 2 - 8, by0 + 28, 22, VOLT, a, width=2.6)
    if clique and u < CLIC + 0.5:
        r = (u - CLIC) / 0.5
        fr.circle((bx0 + bx1) / 2, (by0 + by1) / 2, 30 + 160 * e_out(r), None, a * (1 - r), outline=VOLT, width=3)

    # Barre d'avancement
    done = clamp((u - T0) / (PAS * 6))
    fr.rect(x0 + 48, y0 + 180, x1 - 48, y0 + 184, LINE, a)
    fr.rect(x0 + 48, y0 + 180, x0 + 48 + (x1 - x0 - 96) * done, y0 + 184, VOLT, a)

    # Étapes
    for i, nom in enumerate(ETAPES):
        y = y0 + 248 + i * 62
        debut = T0 + i * PAS
        etat = 0 if u < debut else (1 if u < debut + PAS else 2)
        cx = x0 + 74
        if etat == 0:
            fr.circle(cx, y - 8, 15, None, a, outline=LINE, width=2)
            fr.text(cx, y, str([1, 3, 6, 2, 5, 4][i]), font("mono", 15, 600), INK_3, a, anchor="ms")
        elif etat == 1:
            ang = (u * 900) % 360
            fr.circle(cx, y - 8, 15, None, a, outline=LINE, width=2)
            fr.arc(cx, y - 8, 15, ang, ang + 110, VOLT, 3, a)
        else:
            k = e_back(prog(u, debut + PAS, 0.2))
            fr.circle(cx, y - 8, 15 * k, VOLT, a)
            icon(fr, "check", cx, y - 8, 20, ON_VOLT, a, width=2.6)
        fr.text(cx + 34, y, nom, font("sans", 23, 600 if etat else 500), INK if etat else INK_3, a)
        if etat == 2:
            fr.text(cx + 34 + fr.tw(nom, font("sans", 23, 600)) + 18, y, RESUMES[i], font("mono", 18, 500), INK_3,
                    a * e_out(prog(u, debut + PAS, 0.25)))

    # Journal
    jx0, jy0, jx1, jy1 = 920, y0 + 214, x1 - 48, y1 - 40
    fr.rect(jx0, jy0, jx1, jy1, (7, 9, 8), a, r=14, outline=LINE, width=1.5)
    fm = font("mono", 19, 500)
    for k, (g, s) in enumerate(JOURNAL):
        debut = T0 + k * PAS * 0.92
        if u < debut:
            break
        y = jy0 + 48 + k * 44
        col = {"›": INK_3, "!": AMBER, "✓": VOLT}[g]
        mark(fr, jx0 + 26, y, g, fm, col, a)
        fr.typed(jx0 + 56, y, s, fm, INK if g != "›" else INK_2, u, debut, cps=80, cursor=False)

    # Le curseur vient cliquer sur le bouton
    if u < CLIC + 0.9:
        m = e_in_out(prog(u, 0.55, 0.7))
        cx = lerp(1150, (bx0 + bx1) / 2 + 40, m)
        cy = lerp(820, (by0 + by1) / 2 + 12, m)
        ca = a * (1 - prog(u, CLIC + 0.5, 0.4))
        icon(fr, "cursor", cx + 12, cy + 12, 40 * (1 - 0.12 * press), INK, ca)

    # Notification : l'alerte arrive dans la boîte mail
    na = e_out(prog(u, 4.35, 0.45))
    if na > 0:
        nw, nh = 560, 118
        nx = x1 - 30 - nw + (1 - na) * 160
        ny = y0 + 82
        fr.rect(nx + 6, ny + 8, nx + nw + 6, ny + nh + 8, (0, 0, 0), 0.35 * na, r=16)
        fr.rect(nx, ny, nx + nw, ny + nh, INK, na, r=16)
        fr.rect(nx + 22, ny + 26, nx + 86, ny + 90, VOLT, na, r=12)
        icon(fr, "mail", nx + 54, ny + 58, 36, ON_VOLT, na, width=2.6)
        fr.text(nx + 108, ny + 50, "[ALERTE STOCK] 12 produit(s) en rupture", font("sans", 22, 650), GRAPHITE, na)
        fr.text(nx + 108, ny + 84, "Reçu dans votre boîte · rapport .xlsx joint", font("sans", 19, 450),
                (70, 80, 75), na)
    return fr
