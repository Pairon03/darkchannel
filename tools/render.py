#!/usr/bin/env python3
"""Monta um vídeo a partir do roteiro, das imagens e da narração.

Uso: python3 tools/render.py 01-coliseu

Espera:
  roteiros/<slug>.md        roteiro com blocos "## CENA N"
  imagens/<NN>/cenaNN.jpg   imagem principal da cena; cenaNNb.jpg, cenaNNc.jpg... (opcionais)
                            entram em sequência e dividem o tempo da cena
  audio/<slug>.mp3          narração completa
  assets/ambiente.mp3       (opcional) trilha de fundo em loop
Gera:
  videos/<slug>.mp4
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS = 1920, 1080, 30
FADE = 0.8  # segundos de transição entre imagens


def parse_scenes(md):
    blocks = re.split(r"^## CENA \d+\s*$", md, flags=re.M)[1:]
    scenes = []
    for b in blocks:
        lines = [l for l in b.strip().splitlines() if l.strip() and not l.startswith("IMG:")]
        scenes.append(" ".join(lines))
    return scenes


def duration(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    )
    return float(out)


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def ken_burns(i, n_frames):
    """Alterna zoom-in, zoom-out e panorâmicas para não ficar repetitivo."""
    z0, z1 = 1.0, 1.15
    mode = i % 4
    if mode == 0:  # zoom in no centro
        z = f"{z0}+({z1}-{z0})*on/{n_frames}"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif mode == 1:  # zoom out
        z = f"{z1}-({z1}-{z0})*on/{n_frames}"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif mode == 2:  # pan esquerda -> direita
        z = "1.12"
        x, y = f"(iw-iw/zoom)*on/{n_frames}", "ih/2-(ih/zoom/2)"
    else:  # pan direita -> esquerda
        z = "1.12"
        x, y = f"(iw-iw/zoom)*(1-on/{n_frames})", "ih/2-(ih/zoom/2)"
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={n_frames}:s={W}x{H}:fps={FPS}"


def main(slug):
    num = slug.split("-")[0]
    md = (ROOT / "roteiros" / f"{slug}.md").read_text()
    scenes = parse_scenes(md)
    audio = ROOT / "audio" / f"{slug}.mp3"
    total = duration(audio) + 1.5  # respiro no final
    folder = ROOT / "imagens" / num
    missing = [f"cena{i + 1:02d}.jpg" for i in range(len(scenes))
               if not (folder / f"cena{i + 1:02d}.jpg").exists()]
    if missing:
        sys.exit(f"faltando imagens: {missing}")

    # Tempo de cada cena proporcional ao tamanho do texto narrado nela,
    # dividido igualmente entre as imagens da cena.
    chars = [len(s) for s in scenes]
    per_scene = [sorted(folder.glob(f"cena{i + 1:02d}*.jpg")) for i in range(len(scenes))]
    n_shots = sum(len(p) for p in per_scene)
    # Cada transição "come" FADE segundos, então somamos isso de volta.
    span = total + FADE * (n_shots - 1)
    imgs, durs = [], []
    for paths, c in zip(per_scene, chars):
        for p in paths:
            imgs.append(p)
            durs.append(span * c / sum(chars) / len(paths))

    out = ROOT / "videos" / f"{slug}.mp4"
    out.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        clips = []
        for i, (img, d) in enumerate(zip(imgs, durs)):
            n = int(round(d * FPS))
            clip = Path(tmp) / f"c{i:02d}.mp4"
            vf = (
                # corta 4% das bordas: algumas imagens vêm com moldura ou faixa preta
                f"crop=iw*0.92:ih*0.92,scale=2880:1620:force_original_aspect_ratio=increase,crop=2880:1620,"
                f"{ken_burns(i, n)},"
                # gradação escura: menos saturação, contraste, vinheta e granulação
                "eq=contrast=1.05:saturation=0.9:gamma=1.08,"
                "vignette=PI/6,noise=alls=4:allf=t,format=yuv420p"
            )
            run(["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-vf", vf, "-frames:v", str(n),
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(clip)])
            clips.append((clip, n / FPS))
            print(f"imagem {i + 1}/{len(imgs)} ok ({n / FPS:.1f}s)", flush=True)

        # Encadeia as cenas com crossfade.
        inputs, chain, offset, last = [], [], 0.0, "0:v"
        for clip, _ in clips:
            inputs += ["-i", str(clip)]
        for i in range(1, len(clips)):
            offset += clips[i - 1][1] - FADE
            label = f"v{i}"
            chain.append(f"[{last}][{i}:v]xfade=transition=fade:duration={FADE}:offset={offset:.3f}[{label}]")
            last = label
        chain.append(f"[{last}]fade=t=in:st=0:d=1.5,fade=t=out:st={total - 2:.3f}:d=2[vout]")

        a_inputs, a_chain = audio_mix(audio, len(clips), total)
        run(["ffmpeg", "-y", *inputs, *a_inputs, "-filter_complex", ";".join(chain + [a_chain]),
             "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}",
             "-c:v", "libx264", "-preset", "faster", "-crf", "24", "-r", str(FPS),
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out)])
    print(f"pronto: {out}")


def audio_mix(audio, n_in, total):
    """Narração + trilha ambiente em loop, em estéreo e normalizada para -14 LUFS (padrão YouTube).

    n_in é o índice do primeiro input de áudio no comando do ffmpeg.
    """
    inputs = ["-i", str(audio)]
    # A narração da ElevenLabs vem baixa (~-34 LUFS): normaliza antes de mixar,
    # senão a música fica mais alta que a voz.
    nar = f"[{n_in}:a]loudnorm=I=-16:TP=-2,adelay=500|500,pan=stereo|c0=c0|c1=c0,asplit=2[nar][key]"
    master = "loudnorm=I=-14:TP=-1.5:LRA=11,aformat=sample_rates=48000:channel_layouts=stereo[aout]"
    # Trilha musical (tools/musica.py); se não existir, usa o drone ambiente antigo.
    bg = ROOT / "assets" / "musica.mp3"
    if not bg.exists():
        bg = ROOT / "assets" / "ambiente.mp3"
    if not bg.exists():
        return inputs, f"[{n_in}:a]adelay=500|500,pan=stereo|c0=c0|c1=c0,{master}"
    inputs += ["-stream_loop", "-1", "-i", str(bg)]
    return inputs, (
        f"{nar};[{n_in + 1}:a]volume=0.2,afade=t=out:st={total - 4:.3f}:d=4[bg];"
        # abaixa a música enquanto o narrador fala e devolve nas pausas
        f"[bg][key]sidechaincompress=threshold=0.03:ratio=4:attack=80:release=1000[duck];"
        f"[nar][duck]amix=inputs=2:duration=first:normalize=0,{master}"
    )


def remix(slug):
    """Refaz só o áudio de um vídeo já renderizado, copiando o vídeo sem reencodar."""
    out = ROOT / "videos" / f"{slug}.mp4"
    total = duration(out)
    a_inputs, a_chain = audio_mix(ROOT / "audio" / f"{slug}.mp3", 1, total)
    tmp = out.with_suffix(".tmp.mp4")
    run(["ffmpeg", "-y", "-i", str(out), *a_inputs, "-filter_complex", a_chain,
         "-map", "0:v", "-map", "[aout]", "-t", f"{total:.3f}", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(tmp)])
    tmp.replace(out)
    print(f"áudio refeito: {out}")


if __name__ == "__main__":
    if sys.argv[1] == "--remix":
        for s in sys.argv[2:]:
            remix(s)
    else:
        main(sys.argv[1])
