#!/usr/bin/env python3
"""Planejamento de "ângulos de câmera" dentro de cada imagem e dos cortes no ritmo da fala.

A ideia vem da dica de retenção "cada frase, um ângulo diferente": em vez de uma
única panorâmica lenta de ~14 s por imagem, cada imagem vira várias tomadas
(plano geral, depois closes nas regiões com mais detalhe — rostos, fogo, ação),
com corte seco nas pausas da narração.

Uso de teste: python3 tools/angulos.py imagens/11/cena01.jpg   (mostra os closes escolhidos)
"""
import sys
from pathlib import Path

import cv2
import numpy as np

BORDER = 0.04  # o render corta 4% de cada borda antes de tudo


def interest_map(path, w=192, h=108):
    """Mapa de "interesse": bordas/detalhe × brilho, com reforço em tons de pele iluminados
    (rostos e mãos, que são o que o olho procura numa pintura)."""
    img = cv2.imread(str(path))
    H, W = img.shape[:2]
    bx, by = int(W * BORDER), int(H * BORDER)
    img = img[by:H - by, bx:W - bx]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    gx = cv2.Sobel(small, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(small, cv2.CV_32F, 0, 1)
    edges = cv2.GaussianBlur(np.hypot(gx, gy), (0, 0), 3)
    light = cv2.GaussianBlur(small, (0, 0), 4)
    m = edges * (0.25 + light)
    hsv = cv2.cvtColor(cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    skin = ((hue >= 3) & (hue <= 20) & (sat >= 50) & (sat <= 200) & (val >= 95)).astype(np.float32)
    skin = cv2.GaussianBlur(skin, (0, 0), 2.5)
    m = m * (1 + 6 * skin)
    # rostos ficam quase sempre no terço de cima / meio do quadro
    yy = np.linspace(0, 1, h)[:, None]
    m = m * (1.25 - 1.2 * (yy - 0.38) ** 2)
    return m / (m.max() + 1e-6)


def best_centers(m, zoom, k=3, min_dist=0.22, cy_max=0.5):
    """Até k centros (normalizados 0–1) de janelas 1/zoom do quadro com mais interesse.

    O centro vertical fica limitado a cy_max: nas pinturas, rostos e ação estão
    quase sempre na metade de cima, e mesas, mapas e chão (cheios de detalhe,
    mas sem drama) ficam embaixo.
    """
    h, w = m.shape
    ww, wh = int(w / zoom), int(h / zoom)
    integ = cv2.integral(m)
    sums = (integ[wh:, ww:] - integ[:-wh, ww:] - integ[wh:, :-ww] + integ[:-wh, :-ww])
    ymax = max(1, int(cy_max * h - wh / 2) + 1)
    sums = sums.copy()
    sums[ymax:, :] = -1
    picks = []
    flat = np.argsort(sums, axis=None)[::-1]
    for idx in flat:
        y, x = np.unravel_index(idx, sums.shape)
        c = ((x + ww / 2) / w, (y + wh / 2) / h)
        if all(np.hypot(c[0] - p[0], c[1] - p[1]) >= min_dist for p in picks):
            picks.append(c)
        if len(picks) == k:
            break
    return picks


# Sequência de enquadramentos por imagem: o 1º é sempre o plano geral (contexto),
# depois alterna close e plano médio em regiões diferentes do quadro.
def framings(path, n, seed=0):
    """Devolve n enquadramentos (z0, z1, cx0, cy0, cx1, cy1) para as tomadas de uma imagem."""
    m = interest_map(path)
    close = best_centers(m, 1.7, k=3)
    medium = best_centers(m, 1.35, k=3)
    rng = np.random.default_rng(seed)
    out = []
    for j in range(n):
        if j == 0:
            # plano geral com leve aproximação (ou afastamento) e deriva lateral
            d = rng.choice([-1, 1]) * 0.03
            zin = rng.random() < 0.6
            out.append((1.04 if zin else 1.16, 1.16 if zin else 1.04, 0.5 - d, 0.5, 0.5 + d, 0.5))
            continue
        pool = close if j % 2 == 1 else medium
        z = 1.7 if j % 2 == 1 else 1.35
        c = pool[(j // 2) % len(pool)] if pool else (0.5, 0.5)
        # deriva pequena e lenta dentro do close, sempre em direção ao centro do quadro
        dx = (0.5 - c[0]) * 0.12
        dy = (0.5 - c[1]) * 0.12
        out.append((z, z * 1.06, c[0], c[1], c[0] + dx, c[1] + dy))
    return out


def plan_cuts(t0, t1, cut_candidates, target=4.0, lo=2.8, hi=6.5, last_min=2.0):
    """Divide a janela [t0, t1) em tomadas, cortando de preferência nas pausas da fala."""
    cuts = [t0]
    cand = sorted(c for c in cut_candidates if t0 < c < t1)
    t = t0
    while t1 - t > hi:
        ok = [c for c in cand if t + lo <= c <= t + hi and t1 - c >= last_min]
        nxt = min(ok, key=lambda c: abs(c - (t + target))) if ok else t + target
        if t1 - nxt < last_min:
            # sobra pouco: divide o resto ao meio em vez de deixar uma tomada longa
            if t1 - t > 2 * lo:
                mid = [c for c in cand if t + lo <= c <= t1 - lo]
                cuts.append(min(mid, key=lambda c: abs(c - (t + t1) / 2)) if mid else (t + t1) / 2)
            break
        cuts.append(nxt)
        t = nxt
    cuts.append(t1)
    return cuts


if __name__ == "__main__":
    p = Path(sys.argv[1])
    m = interest_map(p)
    print("close:", [(round(x, 2), round(y, 2)) for x, y in best_centers(m, 1.7)])
    print("médio:", [(round(x, 2), round(y, 2)) for x, y in best_centers(m, 1.35)])
    for f in framings(p, 4):
        print(tuple(round(v, 2) for v in f))
