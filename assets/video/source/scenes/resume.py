"""Scène 7 (34-40 s) : les chiffres clés, puis la signature et l'adresse de la démo."""

from kit import (H, INK, INK_2, INK_3, LINE, ON_VOLT, VOLT, W, Frame, beat_pulse, clamp, e_back, e_out, eyebrow,
                 font, logo, prog, title)

CHIFFRES = [
    ("< 1 s", "par cycle complet", None),
    ("6", "automatisations enchaînées", 6),
    ("0", "intervention ensuite", None),
    ("108", "tests automatisés", 108),
]


def render(u, t):
    fr = Frame()
    eyebrow(fr, 120, 200, "07", "En résumé", u, 0.0)
    title(fr, 120, 272, "Moins de routine, plus de temps.", u, 0.1, size=66)

    # Chiffres clés
    col_w = (W - 240) / 4
    for i, (valeur, label, cible) in enumerate(CHIFFRES):
        x = 120 + i * col_w
        a = e_out(prog(u, 0.35 + i * 0.18, 0.45))
        if a <= 0:
            continue
        fr.line([(x, 360), (x, 520)], LINE, 2, a, caps=False)
        if cible:
            n = int(round(cible * e_out(prog(u, 0.35 + i * 0.18, 0.9))))
            valeur = str(n)
        fr.text(x + 32, 450 + (1 - a) * 24, valeur, font("display", 104, 640), VOLT if i == 1 else INK, a, tracking=-3)
        fr.text(x + 34, 500, label, font("sans", 24, 500), INK_2, a)

    # Signature : logo, nom, adresse de la démo
    s = prog(u, 2.2, 0.6)
    if s > 0:
        breathe = beat_pulse(t, 0.22) if u > 2.8 else 0
        fr.glow(W / 2 - 250, 720, 170, VOLT, (0.16 + 0.1 * breathe) * e_out(s))
        logo(fr, W / 2 - 250, 720, 120, clamp((u - 2.4) / 0.6), e_out(s), scale=e_back(s))
        fr.rise(W / 2 - 160, 768, "Relais", font("display", 132, 680), INK, u, 2.4, tracking=-5)
    ua = e_out(prog(u, 3.0, 0.5))
    if ua > 0:
        f = font("mono", 26, 600)
        url = "automatisation-de-processus-cedric.streamlit.app"
        w = fr.tw(url, f) + 160
        x = W / 2 - w / 2
        fr.rect(x, 836 + (1 - ua) * 16, x + w, 896 + (1 - ua) * 16, VOLT, ua, r=30)
        fr.text(x + 30, 876 + (1 - ua) * 16, "DÉMO", font("mono", 20, 700), ON_VOLT, ua, tracking=3)
        fr.text(x + 130, 876 + (1 - ua) * 16, url, f, ON_VOLT, ua)
    fr.rise(W / 2, 955, "Python · pandas · openpyxl · Selenium · schedule · Streamlit", font("mono", 21, 500),
            INK_3, u, 3.4, anchor="ms", tracking=1)
    return fr
