# Générateur de la présentation vidéo

La vidéo `../Relais_presentation.mp4` (40 s, 1920×1080, 30 i/s) et sa musique
`../musique.mp3` sont entièrement produites par ce dossier : aucune séquence
filmée, aucune banque d'images, aucun échantillon sonore.

```bash
cd assets/video/source
python build.py                  # musique + vidéo + affiche → assets/video/
python build.py --still 15.5     # une image à l'instant donné (apercu.png)
python build.py --preview 15     # planche contact de toute la vidéo
python build.py --music          # musique seule → assets/video/musique.mp3
```

Prérequis : Python 3.10+, `pip install pillow numpy`, et ffmpeg (celui du
système, sinon `pip install imageio-ffmpeg`, qui en fournit un). Au premier
lancement, les polices Space Grotesk, Geist et Geist Mono (licence SIL Open Font
License) sont téléchargées depuis le dépôt `google/fonts` dans `.fonts/`
(ignoré par git). Rendu complet : environ 40 secondes sur 12 cœurs.

| Fichier | Rôle |
|---|---|
| `timeline.py` | 20 mesures à 120 BPM : chaque scène commence sur un premier temps |
| `music.py` | Musique originale synthétisée (numpy) : électro minimale en ré mineur |
| `kit.py` | Charte « Signal » : palette, typographies, formes, icônes, pupitre, transitions |
| `scenes/*.py` | Les sept scènes, une fonction `render(u, t)` chacune |
| `animation.py` | Choisit la scène, compose les transitions sur les mesures, ajoute le pupitre |
| `build.py` | Rendu parallèle, encodage H.264 + AAC, affiche, export MP3 |

## Charte « Signal »

Propre à cette vidéo : le pupitre d'une salle de contrôle. Fond graphite
quadrillé comme un plan, un seul signal vert-volt (`#CFF24A`, la couleur de
l'interface web), titres en Space Grotesk et tout ce que la machine écrit en
Geist Mono. Motifs : le relais du logo (un tracé qui passe d'un niveau à
l'autre), des fils parcourus d'impulsions, un terminal, des barres « quantité
face au seuil ». Une instrumentation encadre chaque image : chapitre, minutage,
avancement par scène, coins de visée. Transitions : ligne de balayage, volets,
grille qui commute case par case, barre de relais qui traverse l'écran.

| Scène | Mesures | Contenu |
|---|---|---|
| Relais | 0-3 | Le plan s'allume, le relais se dessine, la promesse se surligne |
| Le constat | 3-5 | La routine manuelle tapée ligne à ligne, puis rayée ; l'horloge tourne |
| Le pipeline | 5-9 | L'impulsion traverse les nœuds, les ruptures virent au rouge, les décisions tombent |
| Six automatisations | 9-12 | Les six cas, puis le séquenceur qui les allume dans l'ordre du pipeline |
| Le rythme | 12-14 | Les frises des modes TEST et PRODUCTION défilent |
| La démo en ligne | 14-17 | Un clic, six étapes validées, l'alerte arrive dans la boîte mail |
| En résumé | 17-20 | Les chiffres clés, la signature et l'adresse de la démo |

## Musique

Électro minimale à 120 BPM, en ré mineur, grille Rém9 – Si♭maj7(9) – Solm9 –
La7sus4 → La7. Chaque son est calculé à partir d'oscillateurs et de bruit
filtré : kick à hauteur descendante, clap en trois impulsions, charleston,
« clics de relais » (percussion signature, comme un relais qui commute), basse
roulante, arpège pincé avec écho ping-pong, nappes désaccordées, cloches et
effets de transition, réverbération par convolution.

Elle suit l'image : intro sans batterie, le kick entre avec le constat, une
note tinte à chaque nœud du pipeline et à chaque carte allumée par le
séquenceur, la pause laisse tourner le tic-tac des relais, la démo a son clic et
sa notification, et la cloche du logo final précède l'accord de fin. Création
originale, sans droits tiers.
