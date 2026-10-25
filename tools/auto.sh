#!/bin/sh
# Renderiza automaticamente todo vídeo que já tem áudio + 10 imagens + thumb_base
# e ainda não tem MP4. Roda até não sobrar nada pendente por 2 h.
cd "$(dirname "$0")/.."
idle=0
while [ $idle -lt 720 ]; do
  while pgrep -f "tools/render.py" >/dev/null; do sleep 10; done
  did=0
  for a in audio/*.mp3; do
    s=$(basename "$a" .mp3); n=${s%%-*}
    [ -f "videos/$s.mp4" ] && continue
    [ -f "imagens/$n/cena10.jpg" ] && [ -f "imagens/$n/thumb_base.jpg" ] || continue
    echo "== $s $(date +%T)"; python3 tools/render.py "$s" && python3 tools/thumb.py "$s"; did=1; break
  done
  if [ $did = 0 ]; then idle=$((idle+1)); sleep 10; else idle=0; fi
done
echo fim
