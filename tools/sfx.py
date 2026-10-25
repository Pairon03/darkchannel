#!/usr/bin/env python3
"""Sintetiza os efeitos sonoros do canal (sem direitos autorais):

  assets/sfx/whoosh.wav  passagem de ar, usado na troca de capítulo
  assets/sfx/boom.wav    impacto grave + cauda, usado na abertura (gancho)
  assets/sfx/riser.wav   tensão subindo, usado antes do clímax

Uso: python3 tools/sfx.py
"""
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SR = 48000
rng = np.random.default_rng(3)


def lowpass(x, cutoff):
    """Passa-baixas de 1 polo com corte variável no tempo (array ou escalar)."""
    a = np.exp(-2 * np.pi * np.broadcast_to(cutoff, x.shape) / SR)
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a[i]) * x[i] + a[i] * acc
        y[i] = acc
    return y


def save(name, x):
    x = x / np.max(np.abs(x)) * 0.89
    st = np.stack([x, x], axis=1)
    path = ROOT / "assets" / "sfx" / f"{name}.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((st * 32767).astype(np.int16).tobytes())
    print("pronto:", path)


def whoosh(d=1.4):
    t = np.linspace(0, 1, int(SR * d))
    env = np.sin(np.pi * t ** 0.7) ** 2
    cut = 300 + 3500 * np.sin(np.pi * t) ** 2
    n = lowpass(lowpass(rng.normal(size=t.size), cut), cut)
    return n * env


def boom(d=3.5):
    t = np.arange(int(SR * d)) / SR
    f = 55 * np.exp(-t * 0.8) + 30
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.6)
    hit = lowpass(rng.normal(size=t.size), 900) * np.exp(-t * 9) * 3
    tail = lowpass(rng.normal(size=t.size), 220) * np.exp(-t * 1.2) * 1.5
    return body * 1.2 + hit + tail


def riser(d=4.0):
    t = np.arange(int(SR * d)) / SR
    p = t / d
    f = 80 + 320 * p ** 2
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR)
    n = lowpass(rng.normal(size=t.size), 400 + 5000 * p ** 2)
    env = p ** 2 * (1 - np.clip((p - 0.97) / 0.03, 0, 1))
    return (tone * 0.5 + n) * env


if __name__ == "__main__":
    save("whoosh", whoosh())
    save("boom", boom())
    save("riser", riser())
