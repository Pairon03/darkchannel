#!/usr/bin/env python3
"""Remove faixas pretas (letterbox) que o gerador às vezes coloca nas bordas.

Uso: python3 tools/aparar.py imagens/11/*.jpg
Corta linhas/colunas quase pretas nas bordas e recorta de volta para 16:9.
"""
import sys

import numpy as np
from PIL import Image


def trim(path):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(int).max(axis=2)
    # borda "preta" de verdade: quase todos os pixels da linha abaixo de 10
    rows = np.where(np.percentile(a, 98, axis=1) > 10)[0]
    cols = np.where(np.percentile(a, 98, axis=0) > 10)[0]
    t, b, l, r = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
    h, w = a.shape
    if t < h * 0.03 and h - b < h * 0.03 and l < w * 0.03 and w - r < w * 0.03:
        return
    im = im.crop((l, t, r, b))
    w2, h2 = im.size
    if w2 / h2 > 16 / 9:
        nw = int(h2 * 16 / 9); im = im.crop(((w2 - nw) // 2, 0, (w2 - nw) // 2 + nw, h2))
    else:
        nh = int(w2 * 9 / 16); im = im.crop((0, (h2 - nh) // 2, w2, (h2 - nh) // 2 + nh))
    im.resize((w, h), Image.LANCZOS).save(path, quality=95)
    print(f"aparada: {path} (t={t} b={h - b} l={l} r={w - r})")


for p in sys.argv[1:]:
    trim(p)
