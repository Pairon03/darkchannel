#!/bin/sh
# Remonta o painel de postagens (artifact no claude.ai) com os vídeos atuais.
# Uso: sh tools/painel/montar.sh <saida.html>
# Lê UPLOAD.md, SHORTS.md e LOTE2.md (títulos, descrições e datas), thumbnails/ e shorts/.
# As marcações de "postado" não ficam aqui: ficam no banco do próprio painel.
D="$(dirname "$0")"
python3 "$D/extrair.py" "${TMPDIR:-/tmp}/painel-itens.json" || exit 1
python3 - "$D" "${TMPDIR:-/tmp}/painel-itens.json" "$1" <<'PY'
import json, sys
d, itens, out = sys.argv[1:]
body = open(f"{d}/corpo.html").read().replace("__ITEMS__", json.dumps(json.load(open(itens)), ensure_ascii=False).replace("</", "<\\/"))
open(out, "w").write(open(f"{d}/cabecalho.html").read() + body)
PY
