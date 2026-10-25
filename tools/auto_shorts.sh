#!/bin/sh
# Gera o Short de cada vídeo assim que o MP4 dele fica pronto (título = campo THUMB do roteiro).
# Uso: tools/auto_shorts.sh 11-constantinopla 12-caligula ...
cd "$(dirname "$0")/.."
for s in "$@"; do
  until [ -f "videos/$s.mp4" ] && [ ! -d "videos/.lock-$s" ]; do sleep 20; done
  [ -f "shorts/$s-short.mp4" ] && continue
  t=$(sed -n 's/^THUMB: //p' "roteiros/$s.md")
  python3 tools/short.py "$s" "$t" || echo "FALHOU short $s"
done
echo fim-shorts
