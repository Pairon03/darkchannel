#!/usr/bin/env python3
"""Gera as camadas de movimento em loop (10 s, 1920x1080) usadas pelo render:

  assets/fx/brasas.mp4   brasas/faíscas subindo (cenas com fogo)
  assets/fx/poeira.mp4   partículas de poeira flutuando (padrão)
  assets/fx/neblina.mp4  névoa rolando (cenas com névoa, fumaça, tempestade)

As camadas são fundo preto + partículas claras: o render aplica em modo "screen",
então o preto some e só o brilho aparece por cima da imagem.
Uso: python3 tools/fx.py
"""
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS, T = 1920, 1080, 30, 10
N = FPS * T
rng = np.random.default_rng(7)


def encode(name, frames):
    out = ROOT / "assets" / "fx" / f"{name}.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                          "-crf", "18", "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f.tobytes())
    p.stdin.close()
    p.wait()
    print("pronto:", out)


def particles(n, vy_choices, vx_amp, size, color, alpha, blur, flicker):
    """Partículas que voltam exatamente à posição inicial em T segundos (loop perfeito)."""
    x0 = rng.uniform(0, W, n)
    y0 = rng.uniform(0, H, n)
    ky = rng.choice(vy_choices, n)                 # voltas verticais em T segundos
    sway = rng.uniform(0, vx_amp, n)
    ph = rng.uniform(0, 2 * np.pi, n)
    kx = rng.integers(1, 3, n)
    r = rng.uniform(*size, n)
    fk = rng.integers(2, 7, n)
    a0 = rng.uniform(*alpha, n)

    def frames():
        for i in range(N):
            t = i / N
            y = (y0 - ky * H * t) % (H + 40) - 20
            x = (x0 + sway * np.sin(2 * np.pi * kx * t + ph)) % W
            a = a0 * (1 - flicker + flicker * (0.5 + 0.5 * np.sin(2 * np.pi * fk * t + ph)))
            img = Image.new("RGB", (W, H))
            d = ImageDraw.Draw(img)
            for xi, yi, ri, ai in zip(x, y, r, a):
                c = tuple(int(v * ai) for v in color)
                d.ellipse([xi - ri, yi - ri, xi + ri, yi + ri], fill=c)
            glow = img.filter(ImageFilter.GaussianBlur(blur))
            yield np.clip(np.asarray(img, dtype=np.int16) + np.asarray(glow, dtype=np.int16) * 2, 0, 255).astype(np.uint8)
    return frames()


def fog():
    # Ruído suave periódico (filtrado por FFT) com 2 telas de largura: rolar uma
    # largura inteira em T segundos fecha o loop sem emenda.
    h, w = H // 4, W // 2
    noise = rng.normal(size=(h, w))
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    f = np.exp(-(fx ** 2 + fy ** 2) / (2 * 0.012 ** 2))
    field = np.real(np.fft.ifft2(np.fft.fft2(noise) * f))
    field = (field - field.min()) / (field.max() - field.min())
    field = np.clip((field - 0.35) / 0.65, 0, 1) ** 1.6
    big = np.asarray(Image.fromarray((field * 255).astype(np.uint8)).resize((W * 2, H), Image.BICUBIC))
    grad = np.linspace(0.55, 1.0, H)[:, None]  # mais densa embaixo
    for i in range(N):
        sh = int(round(W * i / N))
        sl = np.roll(big, -sh, axis=1)[:, :W] * grad
        g = (sl * 0.75).astype(np.uint8)
        yield np.stack([g, g, (g * 1.05).clip(0, 255).astype(np.uint8)], axis=2)


if __name__ == "__main__":
    encode("brasas", particles(160, [1, 2], 60, (1.2, 3.2), (255, 140, 40), (0.5, 1.0), 6, 0.6))
    encode("poeira", particles(110, [-1, 1], 90, (0.8, 2.2), (235, 225, 200), (0.25, 0.6), 3, 0.3))
    encode("neblina", fog())
