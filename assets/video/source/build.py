"""Construit la présentation vidéo de Relais.

    python build.py              # musique + vidéo + affiche → assets/video/
    python build.py --preview 15 # planche contact (1 image toutes les 15 images)
    python build.py --still 12.5 # une seule image PNG à l'instant donné
    python build.py --music      # musique seule (assets/video/musique.mp3)

Prérequis : Python 3.10+, Pillow, numpy, et ffmpeg (celui du système, sinon
celui du paquet imageio-ffmpeg : pip install imageio-ffmpeg). Les polices
(Space Grotesk, Geist, Geist Mono — licence SIL OFL) sont téléchargées depuis
google/fonts au premier lancement dans assets/video/source/.fonts/ (ignoré par git).
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
FONT_DIR = HERE / ".fonts"
os.environ.setdefault("RELAIS_FONT_DIR", str(FONT_DIR))
sys.path.insert(0, str(HERE))

FONTS = {
    "SpaceGrotesk[wght].ttf": "ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf",
    "Geist[wght].ttf": "ofl/geist/Geist%5Bwght%5D.ttf",
    "GeistMono[wght].ttf": "ofl/geistmono/GeistMono%5Bwght%5D.ttf",
}
VIDEO = OUT / "Relais_presentation.mp4"
POSTER = OUT / "presentation-poster.jpg"
MUSIQUE = OUT / "musique.mp3"
POSTER_T = 5.4


def ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg introuvable : installez-le, ou pip install imageio-ffmpeg")


def fetch_fonts():
    FONT_DIR.mkdir(exist_ok=True)
    for name, path in FONTS.items():
        dest = FONT_DIR / name
        if not dest.exists():
            print(f"Téléchargement de {name}…")
            urllib.request.urlretrieve(f"https://raw.githubusercontent.com/google/fonts/main/{path}", dest)


def _render(i):
    from animation import frame
    from timeline import FPS
    return frame(i / FPS).tobytes()


def write_music(wav):
    from music import compose, write_wav
    print("Synthèse de la musique…")
    write_wav(wav, compose())


def export_mp3(wav):
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", str(wav), "-t", "40", "-c:a", "libmp3lame", "-b:a", "192k",
                    "-metadata", "title=Relais — musique de la présentation",
                    "-metadata", "comment=Musique originale synthétisée pour le projet (numpy), libre de droits",
                    str(MUSIQUE)], check=True)
    print(f"Musique : {MUSIQUE}")


def render_video(workers):
    from timeline import DURATION, FPS, HEIGHT, WIDTH

    total = int(round(DURATION * FPS))
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "musique.wav"
        write_music(wav)
        export_mp3(wav)
        cmd = [
            ffmpeg(), "-v", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
            "-i", str(wav),
            "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-tune", "animation",
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart",
            "-c:a", "aac", "-b:a", "192k", "-shortest",
            "-metadata", "title=Relais — présentation",
            "-metadata", "comment=Animation Python (Pillow) et musique originale synthétisée pour le projet",
            str(VIDEO),
        ]
        enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        with Pool(workers) as pool:
            for n, data in enumerate(pool.imap(_render, range(total), chunksize=4)):
                enc.stdin.write(data)
                if n % 150 == 0:
                    print(f"  image {n}/{total}")
        enc.stdin.close()
        if enc.wait():
            sys.exit("ffmpeg a échoué")
    print(f"Vidéo : {VIDEO}")


def render_poster():
    from animation import frame
    frame(POSTER_T).save(POSTER, quality=88, optimize=True, progressive=True)
    print(f"Affiche : {POSTER}")


def preview(every, dest, start=0.0, end=None):
    from PIL import Image
    from animation import frame
    from timeline import DURATION, FPS

    end = DURATION if end is None else end
    times = [i / FPS for i in range(int(start * FPS), int(end * FPS), every)]
    with Pool(os.cpu_count() or 2) as pool:
        frames = pool.map(_still_thumb, times)
    cols = 6
    sheet = Image.new("RGB", (cols * 384, ((len(frames) + cols - 1) // cols) * 216), (0, 0, 0))
    for k, th in enumerate(frames):
        sheet.paste(th, ((k % cols) * 384, (k // cols) * 216))
    sheet.save(dest)
    print(f"Planche : {dest}")


def _still_thumb(t):
    from animation import frame
    return frame(t).resize((384, 216))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", type=int, metavar="N")
    ap.add_argument("--still", type=float, metavar="T")
    ap.add_argument("--music", action="store_true")
    ap.add_argument("--from", dest="start", type=float, default=0.0)
    ap.add_argument("--to", dest="end", type=float)
    ap.add_argument("--out", default="apercu.png")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    args = ap.parse_args()
    fetch_fonts()
    if args.still is not None:
        from animation import frame
        frame(args.still).save(args.out)
        print(args.out)
    elif args.preview:
        preview(args.preview, args.out, args.start, args.end)
    elif args.music:
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "musique.wav"
            write_music(wav)
            export_mp3(wav)
    else:
        render_video(args.workers)
        render_poster()
