#!/usr/bin/env python3
"""Divide a narração de um roteiro em partes de até 5.000 caracteres (limite da
ElevenLabs por geração), sempre na fronteira entre cenas e o mais equilibrado possível.

Uso: python3 tools/partes.py roteiros/12-caligula.md
"""
import re
import sys

LIMIT = 5000
md = open(sys.argv[1]).read()
blocks = re.split(r"^## CENA \d+\s*$", md, flags=re.M)[1:]
paras = [" ".join(l for l in b.strip().splitlines() if l.strip() and not l.startswith(("IMG:", "TXT:")))
         for b in blocks]
total = len("\n\n".join(paras))
n = -(-total // LIMIT)
parts, cur = [], []
for p in paras:
    if cur and len("\n\n".join(cur + [p])) > total / n + 300 and len(parts) < n - 1:
        parts.append(cur); cur = []
    cur.append(p)
parts.append(cur)
for i, ps in enumerate(parts):
    t = "\n\n".join(ps)
    print(f"===== PARTE {i + 1} ({len(t)} caracteres)")
    print(t)
