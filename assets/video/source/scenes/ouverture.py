"""Scène 1 (0-6 s) : le quadrillage s'allume, le relais se dessine, la promesse s'affiche."""

from kit import (GRAPHITE, H, INK, INK_3, ON_VOLT, VOLT, W, Frame, beat_pulse, e_back, e_in_out, e_out, font,
                 lerp, logo, prog, pulse, title, wire)


def render(u, t):
    fr = Frame()

    # Le plan s'allume : le graphite pur laisse apparaître le quadrillage
    cover = 1 - e_out(prog(u, 0.0, 1.3))
    if cover > 0:
        fr.rect(0, 0, W, H, GRAPHITE, cover)
    p = prog(u, 0.1, 1.2)
    if 0 < p < 1:
        y = lerp(-20, H + 20, e_in_out(p))
        fr.glow(W / 2, y, 420, VOLT, 0.10 * (1 - p))
        fr.line([(0, y), (W, y)], VOLT, 2, 0.55 * (1 - p), caps=False)

    # Le logo apparaît, son tracé se dessine, puis il monte laisser place au nom
    m = e_in_out(prog(u, 1.7, 0.8))
    size = lerp(230, 150, m)
    cy = lerp(H / 2 - 10, 300, m)
    appear = prog(u, 0.35, 0.7)
    if appear > 0:
        breathe = beat_pulse(t, 0.2) if u > 3.0 else 0
        fr.glow(W / 2, cy, size * 1.25, VOLT, (0.16 + 0.12 * breathe) * e_out(appear))
        logo(fr, W / 2, cy, size, e_in_out(prog(u, 0.85, 0.75)), e_out(appear), scale=e_back(appear))

    # Nom et sous-titre
    title(fr, W / 2, 545, "Relais", u, 2.0, size=168, anchor="ms")
    fr.rise(W / 2, 610, "AUTOMATISATION DE PROCESSUS · PYTHON", font("mono", 24, 500), INK_3, u, 2.4,
            anchor="ms", tracking=7)

    # La promesse : la seconde ligne se surligne au trait volt
    f = font("display", 66, 600)
    fr.rise(W / 2, 760, "Vos tâches répétitives", f, INK, u, 3.1, 0.55, 30, anchor="ms", tracking=-2)
    line2 = "tournent toutes seules."
    w2 = fr.tw(line2, f, -2)
    hp = e_out(prog(u, 3.55, 0.6))
    if hp > 0:
        x0 = W / 2 - w2 / 2 - 14
        fr.rect(x0, 790, x0 + (w2 + 28) * hp, 862, VOLT, 1.0, r=6)
    color = ON_VOLT if hp > 0.55 else INK
    fr.rise(W / 2, 848, line2, f, color, u, 3.45, 0.55, 30, anchor="ms", tracking=-2)

    # Un fil parcouru d'impulsions, comme un signal qui circule en continu
    a = e_out(prog(u, 4.2, 0.6))
    if a > 0:
        pts = [(360, 960), (1560, 960)]
        wire(fr, pts, 0, a)
        for k in range(3):
            pulse(fr, pts, ((u - 4.2) * 0.45 + k / 3) % 1, a, r=5)
    return fr
