#!/bin/sh
# Re-renderiza em fila (um por vez) cada vídeo cuja pasta já tem as 30 imagens.
cd "$(dirname "$0")/.."
for s in "$@"; do
  n=${s%%-*}
  until [ "$(ls imagens/$n/cena*.jpg | wc -l)" -ge 30 ]; do sleep 15; done
  echo "== $s $(date +%T)"; nice python3 tools/render.py "$s" | tail -1
done
echo fim
