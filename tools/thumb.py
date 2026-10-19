#!/usr/bin/env python3
"""Gera a thumbnail 1280x720 a partir da imagem base e do campo THUMB do roteiro.

Uso: python3 tools/thumb.py 01-coliseu
Espera imagens/<NN>/thumb_base.jpg e a linha "THUMB: LINHA 1 | LINHA 2" no roteiro.
"""
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 1280, 720
FONT = ROOT / "assets" / "fonts" / "Anton-Regular.ttf"
BRAND = ROOT / "assets" / "fonts" / "Cinzel-Bold.ttf"
RED = (200, 22, 22)
GOLD = (233, 196, 106)


def fit_font(draw, text, path, max_w, start):
    size = start
    while size > 40:
        f = ImageFont.truetype(str(path), size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return ImageFont.truetype(str(path), size)


def main(slug):
    num = slug.split("-")[0]
    md = (ROOT / "roteiros" / f"{slug}.md").read_text()
    l1, l2 = [s.strip() for s in re.search(r"^THUMB: (.*)$", md, re.M).group(1).split("|")]

    base = Image.open(ROOT / "imagens" / num / "thumb_base.jpg").convert("RGB")
    base = base.resize((W, int(base.height * W / base.width)), Image.LANCZOS)
    top = (base.height - H) // 2
    img = base.crop((0, top, W, top + H))
    img = ImageEnhance.Contrast(img).enhance(1.15)
    img = ImageEnhance.Color(img).enhance(1.1)

    # Escurece o lado esquerdo para o texto respirar.
    shade = Image.new("L", (W, H))
    sd = ImageDraw.Draw(shade)
    for x in range(W):
        sd.line([(x, 0), (x, H)], fill=int(215 * max(0, 1 - x / (W * 0.62))))
    img = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), img, shade)

    d = ImageDraw.Draw(img)
    max_w = int(W * 0.56)
    f1 = fit_font(d, l1, FONT, max_w, 150)
    f2 = fit_font(d, l2, FONT, max_w, 150)
    x = 56
    h1 = f1.getbbox(l1)[3]
    h2 = f2.getbbox(l2)[3]
    y1 = (H - (h1 + h2 + 20)) // 2 - 10
    y2 = y1 + h1 + 20

    # Sombra suave atrás do texto.
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.text((x, y1), l1, font=f1, fill=(0, 0, 0, 255))
    gd.text((x, y2), l2, font=f2, fill=(0, 0, 0, 255))
    glow = glow.filter(ImageFilter.GaussianBlur(14))
    img.paste(glow, (6, 8), glow)

    d.text((x, y1), l1, font=f1, fill=(255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0))
    # Segunda linha em faixa vermelha, estilo "selo".
    bx = d.textbbox((x, y2), l2, font=f2)
    d.rectangle([bx[0] - 16, bx[1] - 10, bx[2] + 16, bx[3] + 12], fill=RED)
    d.text((x, y2), l2, font=f2, fill=(255, 255, 255))

    # Marca do canal no rodapé.
    fb = ImageFont.truetype(str(BRAND), 30)
    d.text((x, H - 62), "ECOS DA HISTÓRIA", font=fb, fill=GOLD)

    out = ROOT / "thumbnails" / f"{slug}.jpg"
    out.parent.mkdir(exist_ok=True)
    img.save(out, quality=92)
    print(f"pronto: {out}")


if __name__ == "__main__":
    main(sys.argv[1])
