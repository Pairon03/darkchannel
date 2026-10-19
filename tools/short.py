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
    return [" ".join(l for l in b.strip().splitlines() if l.strip() and not l.startswith("IMG:"))
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
    """Estima o fim de cada frase pela proporção de caracteres e encaixa na pausa mais próxima."""
    rate = speech_dur / text_total_chars
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
            txt = " ".join(c)
            d = (b - a) * len(txt) / n
            # destaca em dourado palavras com números
            txt = re.sub(r"(\b\d[\d.]*\b)", r"{\\c&H6AC4E9&}\1{\\c&HFFFFFF&}", txt.upper())
            lines.append(f"Dialogue: 0,{ass_time(t + DELAY)},{ass_time(t + d + DELAY)},Cap,,0,0,0,,{txt}")
            t += d
    Path(path).write_text(head + "\n".join(lines) + "\n")


def esc(s):
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def main(slug, title):
    md = (ROOT / "roteiros" / f"{slug}.md").read_text()
    sc = scenes(md)
    audio = ROOT / "audio" / f"{slug}.mp3"
    full = " ".join(sc)
    pz = pauses(audio)
    all_phr = [p.strip() for p in re.split(r"(?<=[.,?!:])\s+", full) if p.strip()]
    timed = align(all_phr, len(full.replace(" ", "")) + len(all_phr), duration(audio), pz)

    # Fim do gancho: fim da cena 1 (ou da cena 2, se a 1 for curta demais).
    def scene_end(k):
        n = len([p for p in re.split(r"(?<=[.,?!:])\s+", " ".join(sc[:k])) if p.strip()])
        return timed[n - 1][1], n
    end, n = scene_end(1)
    if end < MIN_LEN and scene_end(2)[0] <= MAX_LEN:
        end, n = scene_end(2)
    if end > MAX_LEN:  # corta na última frase completa antes de 58 s
        n = max(i for i, (_, b, p) in enumerate(timed) if b <= MAX_LEN and p[-1] in ".?!") + 1
        end = timed[n - 1][1]
    timed = timed[:n]
    total = end + DELAY + 1.2

    out = ROOT / "shorts" / f"{slug}-short.mp4"
    out.parent.mkdir(exist_ok=True)
    l1, l2 = (title.split("|") + [""])[:2]
    anton, cinzel = FONT_DIR / "Anton-Regular.ttf", FONT_DIR / "Cinzel-Bold.ttf"
    with tempfile.TemporaryDirectory() as tmp:
        ass = Path(tmp) / "cap.ass"
        build_ass(timed, ass)
        vf = (
            "[0:v]split=2[a][b];"
            "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            "boxblur=28:2,eq=brightness=-0.22:saturation=0.8[bg];"
            "[b]scale=-2:1000,crop=1080:1000[fg];"
            "[bg][fg]overlay=0:400,"
            f"drawtext=fontfile={anton}:text='{esc(l1.strip())}':fontsize=96:fontcolor=white:"
            "borderw=6:bordercolor=black:x=(w-text_w)/2:y=150,"
            f"drawtext=fontfile={anton}:text='{esc(l2.strip())}':fontsize=96:fontcolor=white:"
            "box=1:boxcolor=0xC81616:boxborderw=18:x=(w-text_w)/2:y=275,"
            f"drawtext=fontfile={cinzel}:text='ECOS DA HISTÓRIA':fontsize=40:fontcolor=0xE9C46A:"
            "x=(w-text_w)/2:y=1740,"
            f"drawtext=fontfile={cinzel}:text='ASSISTA O VÍDEO COMPLETO NO CANAL':fontsize=32:fontcolor=white@0.85:"
            "x=(w-text_w)/2:y=1800,"
            f"subtitles={ass}:fontsdir={FONT_DIR},"
            f"fade=t=out:st={total - 0.8:.2f}:d=0.8[v];"
            f"[0:a]afade=t=out:st={total - 1.2:.2f}:d=1.2[aout]"
        )
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-t", f"{total:.2f}",
                        "-i", str(ROOT / "videos" / f"{slug}.mp4"), "-filter_complex", vf,
                        "-map", "[v]", "-map", "[aout]", "-c:v", "libx264", "-preset", "medium",
                        "-crf", "21", "-r", "30", "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart", str(out)], check=True)
    print(f"pronto: {out} ({total:.1f}s)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
