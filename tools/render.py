#!/usr/bin/env python3
"""Monta um vídeo a partir do roteiro, das imagens e da narração.

Uso: python3 tools/render.py 11-constantinopla

Espera:
  roteiros/<slug>.md        roteiro com blocos "## CENA N"; opcionais por cena:
                              TXT: texto na tela (data, lugar, número) no início da cena
                              IMG: prompts (1º = cenaNN, 2º = cenaNNb, 3º = cenaNNc)
  imagens/<NN>/cenaNN.jpg   imagem principal da cena; cenaNNb.jpg, cenaNNc.jpg... (opcionais)
                            entram em sequência e dividem o tempo da cena
  audio/<slug>.mp3          narração completa
  assets/musica.mp3         trilha de fundo em loop
  assets/fx/*.mp4           camadas de movimento (tools/fx.py)
  assets/sfx/*.wav          efeitos sonoros (tools/sfx.py)
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
FONT_DIR = ROOT / "assets" / "fonts"
MUSIC_VOL = 0.224  # 0,2 aprovado no lote 1, +1 dB
NAR_DELAY = 0.5

# Camada de movimento por palavra-chave do prompt da imagem.
FIRE = re.compile(r"fire|burning|flame|ember|spark|molten|explosion|lava|blaze|inferno", re.I)
FLICKER = re.compile(r"fire|burning|flame|torch|candle|lamp|molten|blaze|campfire", re.I)
FOG = re.compile(r"fog|mist|smoke|storm|rain|haze|snow|blizzard|steam|ash", re.I)
FX_OPACITY = {"brasas": 0.85, "poeira": 0.5, "neblina": 0.32}


def parse_scenes(md):
    """Devolve, por cena, (texto narrado, texto na tela ou None, lista de prompts IMG)."""
    blocks = re.split(r"^## CENA \d+\s*$", md, flags=re.M)[1:]
    scenes = []
    for b in blocks:
        lines = [l for l in b.strip().splitlines() if l.strip()]
        text = " ".join(l for l in lines if not l.startswith(("IMG:", "TXT:")))
        txt = next((l[4:].strip() for l in lines if l.startswith("TXT:")), None)
        imgs = [l[4:].strip() for l in lines if l.startswith("IMG:")]
        scenes.append((text, txt, imgs))
    return scenes


def duration(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    )
    return float(out)


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def ken_burns(i, n_frames):
    """Alterna zoom-in, zoom-out e panorâmicas, com um leve balanço de câmera na mão."""
    z0, z1 = 1.04, 1.18
    mode = i % 4
    if mode == 0:  # zoom in no centro
        z = f"{z0}+({z1}-{z0})*on/{n_frames}"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif mode == 1:  # zoom out
        z = f"{z1}-({z1}-{z0})*on/{n_frames}"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif mode == 2:  # pan esquerda -> direita
        z = "1.14"
        x, y = f"(iw-iw/zoom)*on/{n_frames}", "ih/2-(ih/zoom/2)"
    else:  # pan direita -> esquerda
        z = "1.14"
        x, y = f"(iw-iw/zoom)*(1-on/{n_frames})", "ih/2-(ih/zoom/2)"
    # balanço lento e irregular (duas senoides), em pixels da imagem de 2880 px
    x += f"+7*sin(on/37+{i})+4*sin(on/13)"
    y += f"+6*sin(on/29+{i * 2})+3*sin(on/17)"
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={n_frames}:s={W}x{H}:fps={FPS}"


def pick_fx(prompt):
    if FIRE.search(prompt):
        return "brasas"
    if FOG.search(prompt):
        return "neblina"
    return "poeira"


def make_clip(img, prompt, i, n, out):
    fx = pick_fx(prompt)
    flicker = (",eq=eval=frame:brightness='0.035*sin(2*PI*t*1.3)+0.02*sin(2*PI*t*3.7+1)'"
               if FLICKER.search(prompt) else "")
    graph = (
        # corta 4% das bordas: algumas imagens vêm com moldura ou faixa preta
        f"[0:v]crop=iw*0.92:ih*0.92,scale=2880:1620:force_original_aspect_ratio=increase,crop=2880:1620,"
        f"{ken_burns(i, n)}{flicker},format=gbrp[base];"
        "[1:v]format=gbrp[fx];"
        f"[base][fx]blend=all_mode=screen:all_opacity={FX_OPACITY[fx]},"
        # gradação escura: menos saturação, contraste, vinheta e granulação
        "eq=contrast=1.05:saturation=0.9:gamma=1.08,"
        "vignette=PI/6,noise=alls=4:allf=t,format=yuv420p[v]"
    )
    run(["ffmpeg", "-y", "-loop", "1", "-i", str(img),
         "-stream_loop", "-1", "-ss", f"{(i * 3.7) % 9:.2f}", "-i", str(ROOT / "assets" / "fx" / f"{fx}.mp4"),
         "-filter_complex", graph, "-map", "[v]", "-frames:v", str(n),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)])
    return fx


def caption_filters(captions, tmp):
    """drawtext com fade para os textos de tela (TXT:). A 1ª cena vem centralizada e maior."""
    cinzel = FONT_DIR / "Cinzel-Bold.ttf"
    out = []
    for k, (start, end, text) in enumerate(captions):
        tf = Path(tmp) / f"txt{k}.txt"
        tf.write_text(text)
        a = (f"if(lt(t,{start:.2f}),0,if(lt(t,{start + 0.5:.2f}),(t-{start:.2f})/0.5,"
             f"if(lt(t,{end - 0.5:.2f}),1,if(lt(t,{end:.2f}),({end:.2f}-t)/0.5,0))))")
        if k == 0:
            pos = "fontsize=64:x=(w-text_w)/2:y=h*0.80"
        else:
            pos = "fontsize=48:x=90:y=h-190"
        out.append(f"drawtext=fontfile={cinzel}:textfile={tf}:{pos}:fontcolor=0xE9C46A:"
                   f"shadowcolor=black@0.8:shadowx=3:shadowy=3:borderw=2:bordercolor=black@0.6:"
                   f"alpha='{a}':enable='between(t,{start:.2f},{end:.2f})'")
        if k > 0:  # filete dourado acima do texto
            out.append(f"drawbox=x=92:y=ih-206:w=140:h=3:color=0xE9C46A@0.9:t=fill:"
                       f"enable='between(t,{start + 0.3:.2f},{end - 0.3:.2f})'")
    return out


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
    chars = [len(s[0]) for s in scenes]
    per_scene = [sorted(folder.glob(f"cena{i + 1:02d}*.jpg")) for i in range(len(scenes))]
    n_shots = sum(len(p) for p in per_scene)
    # Cada transição "come" FADE segundos, então somamos isso de volta.
    span = total + FADE * (n_shots - 1)
    shots = []  # (imagem, prompt, duração, índice da cena)
    for si, (paths, c, sc) in enumerate(zip(per_scene, chars, scenes)):
        for k, p in enumerate(paths):
            prompt = sc[2][k] if k < len(sc[2]) else (sc[2][0] if sc[2] else "")
            shots.append((p, prompt, span * c / sum(chars) / len(paths), si))

    out = ROOT / "videos" / f"{slug}.mp4"
    out.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        clips = []
        for i, (img, prompt, d, si) in enumerate(shots):
            n = int(round(d * FPS))
            clip = Path(tmp) / f"c{i:02d}.mp4"
            fx = make_clip(img, prompt, i, n, clip)
            clips.append((clip, n / FPS, si))
            print(f"imagem {i + 1}/{len(shots)} ok ({n / FPS:.1f}s, {fx})", flush=True)

        # Encadeia com crossfade; na troca de cena, mergulho rápido no preto.
        inputs, chain, offset, last = [], [], 0.0, "0:v"
        scene_start = {0: 0.0}
        for clip, _, _ in clips:
            inputs += ["-i", str(clip)]
        for i in range(1, len(clips)):
            offset += clips[i - 1][1] - FADE
            new_scene = clips[i][2] != clips[i - 1][2]
            if new_scene:
                scene_start[clips[i][2]] = offset
            tr = "fadeblack" if new_scene else "fade"
            label = f"v{i}"
            chain.append(f"[{last}][{i}:v]xfade=transition={tr}:duration={FADE}:offset={offset:.3f}[{label}]")
            last = label

        captions = []
        for si, sc in enumerate(scenes):
            if sc[1] and si in scene_start:
                st = 1.2 if si == 0 else scene_start[si] + FADE + 0.3
                captions.append((st, st + (5.0 if si == 0 else 4.5), sc[1]))
        post = ",".join(["fade=t=in:st=0:d=1.5", f"fade=t=out:st={total - 2:.3f}:d=2",
                         *caption_filters(captions, tmp)])
        chain.append(f"[{last}]{post}[vout]")

        # Efeitos sonoros: impacto na abertura, whoosh em cada troca de cena,
        # tensão subindo antes do clímax (cena 8).
        sfx = [("boom", 0.25, 0.35)]
        for si, st in sorted(scene_start.items()):
            if si > 0:
                sfx.append(("whoosh", st + FADE / 2 - 0.6, 0.12))
        if 7 in scene_start and scene_start[7] > 6:
            sfx.append(("riser", scene_start[7] + FADE / 2 - 4.0, 0.13))

        a_inputs, a_chain = audio_mix(audio, len(clips), total, sfx)
        run(["ffmpeg", "-y", *inputs, *a_inputs, "-filter_complex", ";".join(chain + [a_chain]),
             "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}",
             "-c:v", "libx264", "-preset", "faster", "-crf", "24", "-r", str(FPS),
             # teto de bitrate: as partículas e a granulação inflam o arquivo; assim
             # um vídeo de ~7 min fica abaixo de 100 MB (limite para enviar)
             "-maxrate", "1500k", "-bufsize", "3000k",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out)])
    print(f"pronto: {out}")


def audio_mix(audio, n_in, total, sfx=()):
    """Narração + trilha + efeitos, em estéreo e normalizada para -14 LUFS (padrão YouTube).

    n_in é o índice do primeiro input de áudio no comando do ffmpeg.
    sfx é uma lista de (nome, instante em segundos, volume).
    """
    inputs = ["-i", str(audio)]
    # A narração da ElevenLabs vem baixa (~-34 LUFS): normaliza antes de mixar,
    # senão a música fica mais alta que a voz.
    nar = (f"[{n_in}:a]loudnorm=I=-16:TP=-2,adelay={int(NAR_DELAY * 1000)}|{int(NAR_DELAY * 1000)},"
           "pan=stereo|c0=c0|c1=c0,asplit=2[nar][key]")
    master = "loudnorm=I=-14:TP=-1.5:LRA=11,aformat=sample_rates=48000:channel_layouts=stereo[aout]"
    bg = ROOT / "assets" / "musica.mp3"
    if not bg.exists():
        bg = ROOT / "assets" / "ambiente.mp3"
    inputs += ["-stream_loop", "-1", "-i", str(bg)]
    parts = [
        nar,
        f"[{n_in + 1}:a]volume={MUSIC_VOL},afade=t=out:st={total - 4:.3f}:d=4[bg]",
        # abaixa a música enquanto o narrador fala e devolve nas pausas
        "[bg][key]sidechaincompress=threshold=0.03:ratio=4:attack=80:release=1000[duck]",
    ]
    mix = ["[nar]", "[duck]"]
    sfx = [s for s in sfx if s[1] >= 0]
    names = sorted({s[0] for s in sfx})
    k = n_in + 2
    for name in names:
        evs = [s for s in sfx if s[0] == name]
        inputs += ["-i", str(ROOT / "assets" / "sfx" / f"{name}.wav")]
        labels = [f"{name}{j}" for j in range(len(evs))]
        parts.append(f"[{k}:a]asplit={len(evs)}" + "".join(f"[{l}s]" for l in labels))
        for l, (_, t, vol) in zip(labels, evs):
            ms = int(t * 1000)
            parts.append(f"[{l}s]volume={vol},adelay={ms}|{ms}[{l}]")
            mix.append(f"[{l}]")
        k += 1
    parts.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:normalize=0,{master}")
    return inputs, ";".join(parts)


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
