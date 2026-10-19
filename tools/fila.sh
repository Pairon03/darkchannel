#!/bin/sh
# Renderiza vídeos em sequência (um por vez, para não disputar CPU).
# Uso: tools/fila.sh 04-alexandria 05-peste-negra ...
cd "$(dirname "$0")/.."
while pgrep -f "tools/render.py" >/dev/null; do sleep 10; done
for s in "$@"; do
  echo "== $s"; python3 tools/render.py "$s" && python3 tools/thumb.py "$s"
done
