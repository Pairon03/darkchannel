#!/usr/bin/env python3
"""Extrai só o texto narrado de um roteiro (sem IMG e cabeçalhos).

Uso: python3 tools/narracao.py roteiros/02-pompeia.md
"""
import re
import sys

md = open(sys.argv[1]).read()
blocks = re.split(r"^## CENA \d+\s*$", md, flags=re.M)[1:]
paras = []
for b in blocks:
    lines = [l for l in b.strip().splitlines() if l.strip() and not l.startswith(("IMG:", "TXT:"))]
    paras.append(" ".join(lines))
print("\n\n".join(paras))
