#!/bin/sh
# Re-renderiza em fila os vídeos cujas pastas já têm as imagens extras (cenaNNb/c).
cd "$(dirname "$0")/.."
for s in "$@"; do
  n=${s%%-*}
  until [ -f "imagens/$n/cena10b.jpg" ] || [ -f "imagens/$n/cena10c.jpg" ]; do sleep 15; done
  sleep 20
  echo "== $s $(date +%T)"; python3 tools/render.py "$s" | tail -1
done
echo fim
