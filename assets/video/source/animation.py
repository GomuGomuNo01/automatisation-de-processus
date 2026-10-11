"""Assemblage image par image : scène courante, transitions calées sur les mesures, pupitre.

Chaque scène est un module de `scenes/` exposant :
    render(u, t) -> kit.Frame (dessinée en 3840×2160)
où u est le temps local de la scène (0 à son début) et t le temps global.
Une scène accepte un u légèrement négatif (transition d'entrée) ou supérieur
à sa durée (transition de sortie).
"""

import importlib

from kit import chrome_layer, composite_transition, e_out, prog
from timeline import DURATION, SCENES, boundaries, scene_end, scene_start

MODULES = [importlib.import_module(f"scenes.{key}") for key, *_ in SCENES]

# Transition vers la scène suivante (index = scène sortante)
TRANSITIONS = [
    "scan",      # ouverture → constat : la ligne de balayage descend sur le plan
    "volets",    # constat → pipeline : huit volets tombent, la routine est remplacée
    "grille",    # pipeline → six cas : la grille commute case par case
    "scan",      # six cas → planification
    "relais",    # planification → démo : la barre du relais traverse l'écran
    "grille",    # démo → résumé
]
PRE, POST = 0.36, 0.36   # la transition chevauche chaque changement de scène


def scene_index(t):
    for i in range(len(SCENES)):
        if t < scene_end(i):
            return i
    return len(SCENES) - 1


def render_scene(i, t):
    return MODULES[i].render(t - scene_start(i), t).finish()


def frame(t):
    t = min(max(t, 0.0), DURATION - 1e-6)
    image = None
    index = scene_index(t)
    for k, b in enumerate(boundaries()):
        if b - PRE <= t < b + POST:
            p = prog(t, b - PRE, PRE + POST)
            image = composite_transition(render_scene(k, t), render_scene(k + 1, t), TRANSITIONS[k], p, t)
            break
    if image is None:
        image = render_scene(index, t)
    # Le pupitre (logo, chapitre, minutage, avancement) apparaît après l'ouverture
    alpha = e_out(prog(t, 1.9, 0.8))
    if alpha > 0:
        layer = chrome_layer(t, index, t - scene_start(index), alpha)
        image.paste(layer, (0, 0), layer)
    return image
