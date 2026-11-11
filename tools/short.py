#!/usr/bin/env python3
"""Gera um Short vertical (1080x1920) a partir do gancho do vídeo longo.

Uso: python3 tools/short.py 01-coliseu "TÍTULO DO SHORT"

Pega a cena 1 do roteiro (e a 2, se a 1 for curta), corta o trecho
correspondente de videos/<slug>.mp4, monta na vertical (fundo desfocado +
vídeo no centro), escreve título no topo e legendas sincronizadas.
Gera shorts/<slug>-short.mp4.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DELAY = 0.5          # a narração entra 0,5 s depois do início do vídeo
MIN_LEN, MAX_LEN = 28.0, 58.0
FONT_DIR = ROOT / "assets" / "fonts"


def scenes(md):
    blocks = re.split(r"^## CENA \d+\s*$", md, flags=re.M)[1:]
    return [" ".join(l for l in b.strip().splitlines() if l.strip() and not l.startswith(("IMG:", "TXT:")))
            for b in blocks]


def duration(p):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]))


def pauses(audio):
    log = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(audio), "-af",
                          "silencedetect=noise=-40dB:d=0.25", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    return list(zip(st, en))


def align(phrases, text_total_chars, speech_dur, pz):
    """Estima o fim de cada frase pela proporção de caracteres e encaixa na pausa mais próxima.

    A velocidade de fala é calculada só sobre o tempo falado (duração menos os silêncios):
    como cada frase "pula" a pausa seguinte, contar os silêncios na velocidade fazia a
    estimativa escorregar ~25% em narrações longas. text_total_chars fica por compatibilidade.
    """
    rate = (speech_dur - sum(b - a for a, b in pz)) / max(sum(len(p) for p in phrases), 1)
    t, out, used = 0.0, [], set()
    for ph in phrases:
        est = t + len(ph) * rate
        best = None
        for i, (a, b) in enumerate(pz):
            if i in used or a <= t + 0.3:
                continue
            if abs(a - est) <= 1.6 and (best is None or abs(a - est) < abs(pz[best][0] - est)):
                best = i
        if best is not None:
            used.add(best)
            end, nxt = pz[best]
        else:
            end = nxt = est
        out.append((t, end, ph))
        t = nxt
    return out


def align_dp(phrases, speech_dur, pz):
    """Alinhamento global: cada fim de frase é casado com uma pausa, em ordem.

    Trabalha em "tempo de fala" (sem os silêncios): a pausa j está no ponto s_j de fala
    acumulada, e a frase i deveria terminar em e_i = velocidade × caracteres acumulados.
    Programação dinâmica escolhe, em ordem crescente, a pausa de cada frase minimizando
    |s_j - e_i|. Pausas sobrando (respiros no meio de uma frase) são simplesmente puladas.
    Erros não se acumulam, ao contrário do encaixe guloso de align().
    """
    pz = [(a, b) for a, b in pz if a > 0.05 and b < speech_dur - 0.05]
    s_pos, acc = [], 0.0
    for a, b in pz:
        s_pos.append(a - acc)
        acc += b - a
    talk = speech_dur - acc
    lens = [len(p) for p in phrases]
    rate = talk / max(sum(lens), 1)
    e, c = [], 0
    for L in lens[:-1]:
        c += L
        e.append(c * rate)
    n, m = len(e), len(pz)
    if n == 0 or m < n:
        return align(phrases, 0, speech_dur, pz)
    dur = [b - a for a, b in pz]
    final = [p.rstrip()[-1] in ".?!" for p in phrases[:-1]]

    def fit(i, j):
        # distância no tempo + coerência com a pontuação: fim de período pede pausa
        # longa; vírgula, pausa curta
        c = abs(s_pos[j] - e[i])
        if final[i]:
            c += 4 * max(0.0, 0.55 - dur[j])
        else:
            c += 2 * max(0.0, dur[j] - 0.75)
        return c

    # pular uma pausa longa (provável fim de frase) custa caro
    skip = [3 * max(0.0, d - 0.45) for d in dur]
    P = [0.0]
    for v in skip:
        P.append(P[-1] + v)
    INF = float("inf")
    # dp[i][j]: custo mínimo casando as frases 0..i, com a frase i na pausa j
    dp = [[INF] * m for _ in range(n)]
    back = [[-1] * m for _ in range(n)]
    for j in range(m):
        dp[0][j] = fit(0, j) + P[j]
    for i in range(1, n):
        best, bj = INF, -1
        for j in range(i, m):
            k = j - 1  # candidata a pausa anterior; custo de pular as pausas entre k e j
            v = dp[i - 1][k] - P[k + 1]
            if v < best:
                best, bj = v, k
            dp[i][j] = best + P[j] + fit(i, j)
            back[i][j] = bj
    j = min(range(n - 1, m), key=lambda k: dp[n - 1][k] + P[m] - P[k + 1])
    picks = [0] * n
    for i in range(n - 1, -1, -1):
        picks[i] = j
        j = back[i][j]
    out, t = [], 0.0
    for i, ph in enumerate(phrases[:-1]):
        a, b = pz[picks[i]]
        out.append((t, a, ph))
        t = b
    out.append((t, speech_dur, phrases[-1]))
    return out


def ass_time(s):
    h, m = int(s // 3600), int(s % 3600 // 60)
    return f"{h}:{m:02d}:{s % 60:05.2f}"


def build_ass(timed, path):
    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Oswald,124,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,0,0,1,6,3,2,60,60,330,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for a, b, ph in timed:
        words = ph.split()
        chunks = [words[i:i + 3] for i in range(0, len(words), 3)]
        n = sum(len(" ".join(c)) for c in chunks) or 1
        t = a
        for c in chunks:
            d = (b - a) * len(" ".join(c)) / n
            # Karaokê: o bloco de 3 palavras fica na tela e a palavra falada
            # acende em dourado, um pouco maior. O bloco entra com um "pop".
            wl = sum(len(w) for w in c) or 1
            tw = t
            for k, w in enumerate(c):
                dw = d * len(w) / wl
                pop = r"{\fscx85\fscy85\t(0,110,\fscx100\fscy100)}" if k == 0 else ""
                txt = " ".join(
                    (r"{\c&H6AC4E9&\fscx112\fscy112}" + x.upper() + r"{\r}") if j == k
                    else re.sub(r"(\b\d[\d.]*\b)", r"{\\c&H6AC4E9&}\1{\\c&HFFFFFF&}", x.upper())
                    for j, x in enumerate(c))
                lines.append(f"Dialogue: 0,{ass_time(tw + DELAY)},{ass_time(tw + dw + DELAY)},Cap,,0,0,0,,{pop}{txt}")
                tw += dw
            t += d
    Path(path).write_text(head + "\n".join(lines) + "\n")


def esc(s):
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def clean_or_full(slug):
    """Prefere a cópia sem textos que o render gera (videos/.<slug>-limpo.mp4)."""
    clean = ROOT / "videos" / f".{slug}-limpo.mp4"
    return clean if clean.exists() else ROOT / "videos" / f"{slug}.mp4"


def phrases_of(text):
    return [p.strip() for p in re.split(r"(?<=[.,?!:])\s+", text) if p.strip()]


def wrap(text, width):
    lines, cur = [], ""
    for w in text.split():
        if cur and len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return lines + [cur]


def main(slug, title, src=None, cena=None, pergunta=None, sufixo=""):
    """Short do gancho (cena 1) ou, com cena=N, de um trecho do meio do vídeo.

    pergunta: texto mostrado nos últimos segundos, sobre a imagem congelada,
    para puxar comentários.
    """
    md = (ROOT / "roteiros" / f"{slug}.md").read_text()
    sc = scenes(md)
    audio = ROOT / "audio" / f"{slug}.mp3"
    timed = align_dp(phrases_of(" ".join(sc)), duration(audio), pauses(audio))
    counts = [len(phrases_of(t)) for t in sc]

    if cena:
        # trecho = a cena inteira, cortado na última frase completa até MAX_LEN
        k = int(cena) - 1
        i0 = sum(counts[:k])
        i1 = i0 + counts[k]
        seg = timed[i0:i1]
        # pula conectivos curtos no começo ("E tem mais.", "Agora,") que não servem de gancho
        while len(seg) > 3 and len(seg[0][2]) < 16:
            seg = seg[1:]
        t_first = seg[0][0]
        while len(seg) > 1 and (seg[-1][1] - t_first > MAX_LEN - 3 or seg[-1][2][-1] not in ".?!"):
            seg = seg[:-1]
        timed = [(a - t_first, b - t_first, p) for a, b, p in seg]
        win = (t_first + DELAY - 0.15, seg[-1][1] + DELAY + 0.2)
    else:
        # gancho: fim da cena 1 (ou da 2, se a 1 for curta demais)
        def scene_end(kk):
            n = sum(counts[:kk])
            return timed[n - 1][1], n
        end, n = scene_end(1)
        if end < MIN_LEN and scene_end(2)[0] <= MAX_LEN:
            end, n = scene_end(2)
        if end > MAX_LEN:
            n = max(i for i, (_, b, p) in enumerate(timed) if b <= MAX_LEN and p[-1] in ".?!") + 1
            end = timed[n - 1][1]
        timed = timed[:n]
        win = None

    hold = 2.8 if pergunta else 1.2  # segundos finais (imagem congelada se houver pergunta)
    speech_end = timed[-1][1] + DELAY + (0.2 if cena else 0)
    if cena:
        total = (win[1] - win[0]) + hold
        offset = 0.15  # o trecho começa 0,15 s antes da 1ª palavra
    else:
        total = speech_end + hold
        offset = DELAY

    out = ROOT / "shorts" / f"{slug}-short{sufixo}.mp4"
    out.parent.mkdir(exist_ok=True)
    l1, l2 = (title.split("|") + [""])[:2]
    anton, cinzel = FONT_DIR / "Anton-Regular.ttf", FONT_DIR / "Cinzel-Bold.ttf"
    with tempfile.TemporaryDirectory() as tmp:
        if cena:
            sys.path.insert(0, str(ROOT / "tools"))
            import render
            src = Path(tmp) / "trecho.mp4"
            render.main(slug, window=win, win_out=src)
        ass = Path(tmp) / "cap.ass"
        build_ass([(a + offset - DELAY, b + offset - DELAY, p) for a, b, p in timed], ass)
        q = []
        if pergunta:
            qf = Path(tmp) / "q.txt"
            qf.write_text("\n".join(wrap(pergunta.upper(), 22)))
            cf = Path(tmp) / "c.txt"
            cf.write_text("COMENTE AQUI")
            qs = total - hold + 0.1
            q = [f"drawbox=x=0:y=400:w=iw:h=1000:color=black@0.62:t=fill:enable='gte(t,{qs:.2f})'",
                 f"drawtext=fontfile={anton}:textfile={qf}:fontsize=84:fontcolor=white:line_spacing=14:"
                 f"x=(w-text_w)/2:y=900-text_h/2-40:enable='gte(t,{qs:.2f})'",
                 f"drawtext=fontfile={anton}:textfile={cf}:fontsize=56:fontcolor=white:box=1:"
                 f"boxcolor=0xC81616:boxborderw=16:x=(w-text_w)/2:y=1230:enable='gte(t,{qs + 0.3:.2f})'"]
        # fonte: congela o último quadro durante a pergunta; áudio some ao fim da fala
        clip_len = total - hold
        vsrc = (f"[0:v]trim=0:{clip_len:.2f},setpts=PTS-STARTPTS,"
                f"tpad=stop_mode=clone:stop_duration={hold:.2f},split=2[a][b];")
        asrc = (f"[0:a]atrim=0:{clip_len:.2f},asetpts=PTS-STARTPTS,"
                f"afade=t=out:st={clip_len - 0.25:.2f}:d=0.25,apad=whole_dur={total:.2f}[aout]")
        vf = (
            vsrc +
            "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            "boxblur=28:2,eq=brightness=-0.22:saturation=0.8[bg];"
            # zoom de impacto nos primeiros 0,6 s (1,18x -> 1x)
            # mostra só os 78% de cima do quadro (o rodapé do vídeo longo pode ter texto)
            "[b]scale=-2:1282,crop=1080:1000:(iw-1080)/2:0,"
            "scale=w='trunc(1080*(1+0.18*max(0\\,1-t/0.6))/2)*2':h=-2:eval=frame,crop=1080:1000[fg];"
            f"color=c=0xC81616:s=1080x10:r=30:d={total:.2f}[bar];"
            "[bg][fg]overlay=0:400[base];"
            # barra de progresso vermelha logo abaixo da imagem
            f"[base][bar]overlay=x='-W+W*t/{total:.2f}':y=1400:shortest=1,"
            f"drawtext=fontfile={anton}:text='{esc(l1.strip())}':fontsize=96:fontcolor=white:"
            "borderw=6:bordercolor=black:x=(w-text_w)/2:y=150,"
            f"drawtext=fontfile={anton}:text='{esc(l2.strip())}':fontsize=96:fontcolor=white:"
            "box=1:boxcolor=0xC81616:boxborderw=18:x=(w-text_w)/2:y=275,"
            f"drawtext=fontfile={cinzel}:text='ECOS DA HISTÓRIA':fontsize=40:fontcolor=0xE9C46A:"
            "x=(w-text_w)/2:y=1740,"
            f"drawtext=fontfile={cinzel}:text='ASSISTA O VÍDEO COMPLETO NO CANAL':fontsize=32:fontcolor=white@0.85:"
            "x=(w-text_w)/2:y=1800,"
            f"subtitles={ass}:fontsdir={FONT_DIR}"
            + "".join("," + f for f in q) +
            f",fade=t=out:st={total - 0.4:.2f}:d=0.4[v];" + asrc
        )
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-i", str(src or clean_or_full(slug)), "-filter_complex", vf,
                        "-map", "[v]", "-map", "[aout]", "-t", f"{total:.2f}", "-c:v", "libx264",
                        "-preset", "medium", "-crf", "21", "-r", "30", "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart", str(out)], check=True)
    print(f"pronto: {out} ({total:.1f}s)")


if __name__ == "__main__":
    # python3 tools/short.py <slug> "L1|L2" [--cena N] [--pergunta "..."] [--sufixo 2]
    args, opts = [], {}
    it = iter(sys.argv[1:])
    for a in it:
        if a.startswith("--"):
            opts[a[2:]] = next(it)
        else:
            args.append(a)
    main(args[0], args[1], cena=opts.get("cena"), pergunta=opts.get("pergunta"),
         sufixo=opts.get("sufixo", ""))
