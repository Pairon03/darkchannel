#!/usr/bin/env python3
"""Gera o banner do canal (2560x1440) a partir de assets/banner_base.jpg.

Uso: python3 tools/banner.py "NOME DO CANAL" "slogan"
O texto fica na área segura central (1546x423), que aparece em todos os aparelhos.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 2560, 1440
GOLD = (233, 196, 106)


def main(name, slogan):
    base = Image.open(ROOT / "assets" / "banner_base.jpg").convert("RGB")
    bg = Image.new("RGB", (W, H), (0, 0, 0))
    b2 = base.resize((W, int(base.height * W / base.width)), Image.LANCZOS)
    bg.paste(b2, (0, (H - b2.height) // 2))
    d = ImageDraw.Draw(bg)
    f = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "Cinzel-Bold.ttf"), 120)
    x, y = (W - d.textlength(name, font=f)) // 2, H // 2 - 130
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).text((x, y), name, font=f, fill=(0, 0, 0, 255))
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    bg.paste(glow, (0, 6), glow)
    d.text((x, y), name, font=f, fill=GOLD)
    f2 = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "Cinzel-Bold.ttf"), 46)
    d.text(((W - d.textlength(slogan, font=f2)) // 2, y + 170), slogan, font=f2, fill=(220, 210, 190))
    out = ROOT / "canal" / "banner.jpg"
    bg.save(out, quality=92)
    print(f"pronto: {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
