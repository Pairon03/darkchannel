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
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from angulos import framings, plan_cuts

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS = 1920, 1080, 30
FADE = 0.8  # segundos de transição entre imagens
FONT_DIR = ROOT / "assets" / "fonts"
MUSIC_VOL = 0.224  # 0,2 aprovado no lote 1, +1 dB
NAR_DELAY = 0.5
HOOK_LEN = 3.0     # gancho visual: frase da thumbnail na tela nos 3 primeiros segundos
POP_LEN = 1.8      # quanto tempo um número/data fica na tela
CLEAN_LEN = 65     # segundos da cópia sem textos usada pelos Shorts
# Modo dinâmico (padrão): cada imagem vira várias tomadas (geral, closes) com corte
# seco nas pausas da narração. Use --estatico para o estilo antigo, uma panorâmica por imagem.
DYNAMIC = "--estatico" not in sys.argv

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


def framed(i, n, f):
    """zoompan de uma tomada com enquadramento planejado (tools/angulos.py).

    f = (z0, z1, cx0, cy0, cx1, cy1): zoom e centro (0–1) no início e no fim da tomada.
    Os closes entram com um "soco" de zoom curto (+5% que some em 0,2 s), que marca o corte.
    """
    z0, z1, cx0, cy0, cx1, cy1 = f
    p = f"(on/{max(n - 1, 1)})"
    punch = f"+0.05*max(0\\,1-on/6)" if z0 > 1.2 else ""
    z = f"{z0}+({z1}-{z0})*{p}{punch}"
    cx = f"({cx0}+({cx1}-{cx0})*{p})"
    cy = f"({cy0}+({cy1}-{cy0})*{p})"
    x = f"max(0\\,min(iw-iw/zoom\\,{cx}*iw-iw/zoom/2+7*sin(on/37+{i})+4*sin(on/13)))"
    y = f"max(0\\,min(ih-ih/zoom\\,{cy}*ih-ih/zoom/2+6*sin(on/29+{i * 2})+3*sin(on/17)))"
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={W}x{H}:fps={FPS}"


def make_clip(img, prompt, i, n, out, framing=None):
    fx = pick_fx(prompt)
    flicker = (",eq=eval=frame:brightness='0.035*sin(2*PI*t*1.3)+0.02*sin(2*PI*t*3.7+1)'"
               if FLICKER.search(prompt) else "")
    camera = framed(i, n, framing) if framing else ken_burns(i, n)
    graph = (
        # corta 4% das bordas: algumas imagens vêm com moldura ou faixa preta
        f"[0:v]crop=iw*0.92:ih*0.92,scale=2880:1620:force_original_aspect_ratio=increase,crop=2880:1620,"
        f"{camera}{flicker},format=gbrp[base];"
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


def fade_alpha(start, end, fin=0.25, fout=0.35):
    return (f"if(lt(t,{start:.2f}),0,if(lt(t,{start + fin:.2f}),(t-{start:.2f})/{fin},"
            f"if(lt(t,{end - fout:.2f}),1,if(lt(t,{end:.2f}),({end:.2f}-t)/{fout},0))))")


def hook_filters(l1, l2, tmp, end=HOOK_LEN):
    """Gancho visual dos 3 primeiros segundos: a frase da thumbnail, grande, no centro."""
    anton = FONT_DIR / "Anton-Regular.ttf"
    out = []
    for k, (txt, y, box) in enumerate([(l1, "h*0.36", False), (l2, "h*0.36+150", True)]):
        if not txt:
            continue
        tf = Path(tmp) / f"hook{k}.txt"
        tf.write_text(txt)
        st = 0.15 + 0.35 * k  # a 2ª linha entra logo depois, no ritmo do impacto
        style = ("box=1:boxcolor=0xC81616:boxborderw=22:fontcolor=white" if box
                 else "fontcolor=white:borderw=6:bordercolor=black")
        out.append(f"drawtext=fontfile={anton}:textfile={tf}:fontsize=128:{style}:"
                   f"shadowcolor=black@0.7:shadowx=5:shadowy=5:x=(w-text_w)/2:y={y}:"
                   f"alpha='{fade_alpha(st, end, 0.12)}':enable='between(t,{st:.2f},{end:.2f})'")
    return out


def pop_filters(pops, tmp):
    """Números e datas que "saltam" na tela no momento em que são narrados."""
    anton = FONT_DIR / "Anton-Regular.ttf"
    out = []
    for k, (st, txt) in enumerate(pops):
        tf = Path(tmp) / f"pop{k}.txt"
        tf.write_text(txt)
        end = st + POP_LEN
        # entra 30% maior e encolhe até o tamanho final em 0,15 s
        size = f"fontsize='92+40*max(0\\,1-(t-{st:.2f})/0.15)'"
        out.append(f"drawtext=fontfile={anton}:textfile={tf}:{size}:fontcolor=0xE9C46A:"
                   f"borderw=5:bordercolor=black:shadowcolor=black@0.8:shadowx=4:shadowy=4:"
                   f"x=(w-text_w)/2:y=h*0.70-text_h/2:alpha='{fade_alpha(st, end, 0.08, 0.3)}':"
                   f"enable='between(t,{st:.2f},{end:.2f})'")
    return out


def question_filters(start, end, question, tmp):
    """Pergunta final na tela, convidando a comentar (a narração já faz a pergunta)."""
    anton = FONT_DIR / "Anton-Regular.ttf"
    words, lines, cur = question.upper().split(), [], ""
    for w_ in words:
        if len(cur) + len(w_) > 38 and cur:
            lines.append(cur)
            cur = w_
        else:
            cur = (cur + " " + w_).strip()
    lines.append(cur)
    tf = Path(tmp) / "pergunta.txt"
    tf.write_text("\n".join(lines))
    tl = Path(tmp) / "comente.txt"
    tl.write_text("COMENTE AQUI EMBAIXO")
    a = fade_alpha(start, end, 0.3, 0.6)
    return [
        f"drawbox=x=0:y=ih*0.60:w=iw:h=ih*0.34:color=black@0.55:t=fill:"
        f"enable='between(t,{start:.2f},{end:.2f})'",
        f"drawtext=fontfile={anton}:textfile={tf}:fontsize=54:fontcolor=white:line_spacing=8:"
        f"x=(w-text_w)/2:y=h*0.63:alpha='{a}':enable='between(t,{start:.2f},{end:.2f})'",
        f"drawtext=fontfile={anton}:textfile={tl}:fontsize=44:fontcolor=white:"
        f"box=1:boxcolor=0xC81616:boxborderw=12:x=(w-text_w)/2:y=h*0.865:"
        f"alpha='{a}':enable='between(t,{start + 0.4:.2f},{end:.2f})'",
    ]


def speech_timeline(audio, scenes):
    """Frases com início e fim estimados (encaixados nas pausas) e os pontos de corte.

    Reaproveita o alinhamento das legendas dos Shorts. Os tempos já incluem o
    atraso da narração no vídeo (NAR_DELAY).
    """
    from short import align, pauses
    full = " ".join(s[0] for s in scenes)
    phrases = [p.strip() for p in re.split(r"(?<=[.,?!:])\s+", full) if p.strip()]
    pz = pauses(audio)
    timed = align(phrases, len(full.replace(" ", "")) + len(phrases), duration(audio), pz)
    timed = [(a + NAR_DELAY, b + NAR_DELAY, p) for a, b, p in timed]
    cuts = [(a + b) / 2 + NAR_DELAY for a, b in pz]
    return timed, cuts


NUM = re.compile(r"\b\d{1,2} de (?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|"
                 r"outubro|novembro|dezembro)(?: de \d{3,4})?|\b\d{3,4}\b(?: antes de Cristo)?", re.I)


def number_pops(timed, avoid, gap=6.0):
    """Um "pop" por data/ano narrado, na posição estimada dentro da frase, sem encavalar."""
    pops, last = [], -99.0
    for a, b, ph in timed:
        for m in NUM.finditer(ph):
            t = a + (b - a) * m.start() / max(len(ph), 1)
            if t - last < gap or any(s - 1 <= t <= e for s, e in avoid):
                continue
            txt = m.group(0).upper().replace("ANTES DE CRISTO", "a.C.")
            pops.append((t, txt))
            last = t
    return pops


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

    timed, cut_points = speech_timeline(audio, scenes) if DYNAMIC else ([], [])

    out = ROOT / "videos" / f"{slug}.mp4"
    out.parent.mkdir(exist_ok=True)
    cache = ROOT / "videos" / f".tmp-{slug}"
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        clips = []
        t_start = 0.0  # início da imagem na linha do tempo final
        for i, (img, prompt, d, si) in enumerate(shots):
            n = int(round(d * FPS))
            # As tomadas ficam em videos/.tmp-<slug> até o fim: se a etapa final
            # falhar, rodar de novo reaproveita o que já foi renderizado.
            clip = cache / f"c{i:02d}.mp4"
            if clip.exists() and clip.stat().st_mtime > img.stat().st_mtime:
                clips.append((clip, n / FPS, si))
                t_start += n / FPS - FADE
                print(f"imagem {i + 1}/{len(shots)} (já renderizada)", flush=True)
                continue
            if DYNAMIC:
                # Tomadas cortadas nas pausas da fala; a transição para a próxima
                # imagem ocupa os últimos FADE segundos, então não corta ali.
                bounds = plan_cuts(t_start, t_start + n / FPS - FADE, cut_points)
                bounds[-1] = t_start + n / FPS
                fr = framings(img, len(bounds) - 1, seed=i)
                parts, used = [], 0
                for j, (a, b) in enumerate(zip(bounds, bounds[1:])):
                    nj = n - used if j == len(bounds) - 2 else int(round((b - a) * FPS))
                    part = cache / f"c{i:02d}_{j}.mp4"
                    fx = make_clip(img, prompt, i * 7 + j, nj, part, fr[j])
                    parts.append(part)
                    used += nj
                lst = cache / f"c{i:02d}.txt"
                lst.write_text("".join(f"file '{p}'\n" for p in parts))
                run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(clip)])
                takes = f", {len(parts)} tomadas"
            else:
                fx = make_clip(img, prompt, i, n, clip)
                takes = ""
            clips.append((clip, n / FPS, si))
            t_start += n / FPS - FADE
            print(f"imagem {i + 1}/{len(shots)} ok ({n / FPS:.1f}s, {fx}{takes})", flush=True)

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
        first_cap = HOOK_LEN + 0.2 if DYNAMIC else 1.2
        for si, sc in enumerate(scenes):
            if sc[1] and si in scene_start:
                st = first_cap if si == 0 else scene_start[si] + FADE + 0.3
                captions.append((st, st + (5.0 if si == 0 else 4.5), sc[1]))
        extra = []
        if DYNAMIC:
            m = re.search(r"^THUMB:\s*(.*)$", md, re.M)
            l1, l2 = ([s.strip() for s in m.group(1).split("|")] + [""])[:2] if m else ("", "")
            extra += hook_filters(l1, l2, tmp)
            # pergunta final: a última frase com "?" (junta o pedaço antes da vírgula)
            qi = [k for k, (a, b, p) in enumerate(timed) if p.endswith("?") and a > total * 0.85]
            q_span = []
            if qi:
                k = qi[-1]
                while k > 0 and timed[k - 1][2].endswith(","):
                    k -= 1
                qa = timed[k][0]
                q_span = [(qa, total - 1.5)]
                qtext = " ".join(p for _, _, p in timed[k:qi[-1] + 1])
                extra += question_filters(qa, total - 1.5, qtext, tmp)
            avoid = [(0, HOOK_LEN + 0.5)] + [(s, e) for s, e, _ in captions] + q_span
            extra += pop_filters(number_pops(timed, avoid), tmp)
        fade_in = "fade=t=in:st=0:d=0.3" if DYNAMIC else "fade=t=in:st=0:d=1.5"
        post = ",".join([fade_in, f"fade=t=out:st={total - 2:.3f}:d=2",
                         *caption_filters(captions, tmp), *extra])
        xfades = list(chain)
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

        if DYNAMIC:
            # Cópia "limpa" (sem textos) do primeiro minuto, usada pelo Short, que tem
            # título e legendas próprios. Passo separado e pequeno: só as primeiras imagens.
            k, acc = 0, clips[0][1]
            while acc - FADE < CLEAN_LEN and k + 1 < len(clips):
                k += 1
                acc += clips[k][1] - FADE
            vlast = f"v{k}" if k else "0:v"
            ca_inputs, ca_chain = audio_mix(audio, k + 1, total, sfx)
            run(["ffmpeg", "-y", *inputs[:2 * (k + 1)], *ca_inputs, "-filter_complex",
                 ";".join(xfades[:k] + [f"[{vlast}]trim=0:{CLEAN_LEN},setpts=PTS-STARTPTS[vcl]", ca_chain]),
                 "-map", "[vcl]", "-map", "[aout]", "-t", str(CLEAN_LEN), "-c:v", "libx264",
                 "-preset", "faster", "-crf", "20", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
                 str(ROOT / "videos" / f".{slug}-limpo.mp4")])

        run(["ffmpeg", "-y", *inputs, *a_inputs, "-filter_complex", ";".join(chain + [a_chain]),
             "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}",
             "-c:v", "libx264", "-preset", "faster", "-crf", "24", "-r", str(FPS),
             # teto de bitrate: as partículas e a granulação inflam o arquivo; assim
             # um vídeo de ~7 min fica abaixo de 100 MB (limite para enviar)
             "-maxrate", "1500k", "-bufsize", "3000k",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out)])
    shutil.rmtree(cache, ignore_errors=True)
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
    args = [a for a in sys.argv[1:] if a != "--estatico"]
    if args[0] == "--remix":
        for s in args[1:]:
            remix(s)
    else:
        main(args[0])
