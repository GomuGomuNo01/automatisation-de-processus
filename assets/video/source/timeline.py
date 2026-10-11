"""Découpage temporel partagé par l'animation et la musique.

La vidéo dure exactement 20 mesures à 120 BPM (40 s). Chaque changement de
scène tombe sur un premier temps de mesure : la musique se cale sur l'image
sans aucun montage manuel.
"""

BPM = 120
BEAT = 60 / BPM          # 0,5 s
STEP = BEAT / 4          # double-croche
BAR = BEAT * 4           # 2 s
BARS = 20
DURATION = BAR * BARS    # 40 s
FPS = 30
WIDTH, HEIGHT = 1920, 1080
SS = 2                   # chaque image est dessinée en 3840×2160 puis réduite (contours lissés)

# (clé, titre de chapitre, première mesure, nombre de mesures)
SCENES = [
    ("ouverture", "Relais",               0, 3),
    ("constat",   "Le constat",           3, 2),
    ("pipeline",  "Le pipeline",          5, 4),
    ("six_cas",   "Six automatisations",  9, 3),
    ("rythme",    "Le rythme",           12, 2),
    ("demo",      "La démo en ligne",    14, 3),
    ("resume",    "En résumé",           17, 3),
]


def scene_start(index):
    return SCENES[index][2] * BAR


def scene_end(index):
    _, _, first, count = SCENES[index]
    return (first + count) * BAR


def boundaries():
    """Instants des changements de scène (hors début et fin)."""
    return [scene_start(i) for i in range(1, len(SCENES))]
