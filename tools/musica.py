#!/usr/bin/env python3
"""Compõe a trilha de fundo do canal: orquestral sombria em Ré menor, ~6 min.

Uso: python3 tools/musica.py [saida.wav]

Progressão i–VI–III–VII (Dm–B♭–F–C), 60 BPM, 8 s por acorde. A música
evolui por seções (pad → piano → baixo → percussão e melodia → pausa →
clímax → final) para não soar como um loop repetido.
"""
import sys

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 44100
CHORD = 8.0                       # segundos por acorde
CYCLE = 4 * CHORD                 # um ciclo da progressão
N_CYCLES = 11                     # ~5min52s, mais que o vídeo mais longo
rng = np.random.default_rng(7)


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


# Acordes (MIDI): fundamental no grave + tríade no médio.
CHORDS = [
    (38, [62, 65, 69]),   # Dm
    (34, [58, 62, 65]),   # Bb
    (41, [60, 65, 69]),   # F
    (36, [60, 64, 67]),   # C
]
# Arpejo do piano: índices nas notas da tríade (+12 = oitava acima).
ARP = [0, 1, 2, 1, 0, 2, 1, 2]
# Melodia (violoncelo), uma nota de 2 s por meio compasso, por acorde.
MELODY = [
    [74, 72, 69, 65],
    [70, 69, 65, 62],
    [72, 69, 67, 65],
    [67, 64, 67, 69],
]


def env(n, a, r):
    """Envelope com ataque e release lineares (em amostras)."""
    e = np.ones(n)
    a, r = min(a, n // 2), min(r, n // 2)
    e[:a] = np.linspace(0, 1, a)
    e[n - r:] = np.linspace(1, 0, r)
    return e


def strings(f, dur, harmonics=10, detune=(-0.004, 0, 0.004), vib=0.0):
    t = np.arange(int(dur * SR)) / SR
    out = np.zeros_like(t)
    for d in detune:
        ph = 2 * np.pi * f * (1 + d) * t
        if vib:
            ph += vib * np.sin(2 * np.pi * 5.2 * t) / 5.2
        for k in range(1, harmonics + 1):
            out += np.sin(k * ph + rng.uniform(0, 6.28)) / k
    return out / (len(detune) * 2.5)


def piano(f, dur=3.5):
    t = np.arange(int(dur * SR)) / SR
    out = np.zeros_like(t)
    for k, amp in enumerate([1, 0.5, 0.28, 0.15, 0.08, 0.05], start=1):
        fk = f * k * (1 + 0.0004 * k * k)          # leve inarmonicidade
        out += amp * np.sin(2 * np.pi * fk * t) * np.exp(-t * (1.2 + 0.9 * k))
    out *= env(len(t), int(0.004 * SR), int(0.3 * SR))
    return out * 0.5


def drum(dur=2.5):
    t = np.arange(int(dur * SR)) / SR
    f = 42 + 50 * np.exp(-t * 9)                    # queda de afinação
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.2)
    noise = rng.normal(0, 1, len(t)) * np.exp(-t * 25) * 0.15
    return (body + noise) * 0.9


def add(buf, sig, start):
    i = int(start * SR)
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i]


def lowpass(x, fc):
    return sosfilt(butter(4, fc, fs=SR, output="sos"), x)


def reverb(x, secs=3.2, seed=0):
    r = np.random.default_rng(seed)
    n = int(secs * SR)
    ir = r.normal(0, 1, n) * np.exp(-np.arange(n) / SR * 2.2)
    ir = lowpass(ir, 5000)
    ir /= np.sqrt(np.sum(ir ** 2))
    return fftconvolve(x, ir)[: len(x)]


def main(out):
    total = N_CYCLES * CYCLE + 6
    n = int(total * SR)
    pad, pia, bass, mel, drm = (np.zeros(n) for _ in range(5))

    # Que instrumentos tocam em cada ciclo.
    plan = [
        {"pad"},
        {"pad", "piano"},
        {"pad", "piano", "bass"},
        {"pad", "piano", "bass", "drum", "mel"},
        {"pad", "piano", "bass", "drum", "mel"},
        {"pad", "piano"},
        {"pad", "piano", "bass", "mel"},
        {"pad", "piano", "bass", "drum", "mel"},
        {"pad", "piano", "bass", "drum", "mel"},
        {"pad", "piano", "mel"},
        {"pad"},
    ]

    for c, parts in enumerate(plan):
        for k, (root, triad) in enumerate(CHORDS):
            t0 = c * CYCLE + k * CHORD
            if "pad" in parts:
                for m in triad:
                    s = strings(hz(m), CHORD + 2.5, vib=0.002)
                    add(pad, s * env(len(s), int(1.5 * SR), int(2.5 * SR)), t0)
            if "bass" in parts:
                s = strings(hz(root), CHORD + 1.5, harmonics=6, detune=(0,))
                add(bass, s * env(len(s), int(0.6 * SR), int(1.5 * SR)), t0)
            if "piano" in parts:
                for b, idx in enumerate(ARP):
                    m = triad[idx] + (12 if b in (2, 5) else 0)
                    add(pia, piano(hz(m)) * (0.8 + 0.2 * (b == 0)), t0 + b)
            if "mel" in parts:
                for b, m in enumerate(MELODY[k]):
                    s = strings(hz(m - 12), 2.4, harmonics=8, detune=(0, 0.002), vib=0.006)
                    add(mel, s * env(len(s), int(0.35 * SR), int(0.8 * SR)), t0 + 2 * b)
            if "drum" in parts:
                add(drm, drum(), t0)
                add(drm, drum() * 0.45, t0 + 6)

    pad = lowpass(pad, 1400) * 0.55
    bass = lowpass(bass, 300) * 0.8
    mel = lowpass(mel, 2200) * 0.5
    pia = lowpass(pia, 4000) * 0.45
    drm = lowpass(drm, 900) * 0.8

    dry = pad + bass + mel + pia + drm
    left = 0.75 * dry + 0.55 * reverb(dry + 0.3 * pia, seed=1)
    right = 0.75 * dry + 0.55 * reverb(dry + 0.3 * pia, seed=2)
    st = np.stack([left, right], axis=1)

    # Fade de entrada e saída, normaliza o pico.
    fade = env(n, int(4 * SR), int(6 * SR))
    st *= fade[:, None]
    st /= np.max(np.abs(st)) / 0.89

    import wave
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())
    print(f"pronto: {out} ({total:.0f}s)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "musica.wav")
