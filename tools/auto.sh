#!/bin/sh
# Renderiza automaticamente todo vídeo que já tem áudio + imagens + thumb_base
# e ainda não tem MP4. Pode rodar em mais de uma instância ao mesmo tempo:
# cada vídeo é reservado com um diretório de trava (videos/.lock-<slug>).
# Para quando não sobra nada pendente por 2 h.
cd "$(dirname "$0")/.."
mkdir -p videos
idle=0
while [ $idle -lt 720 ]; do
  did=0
  for a in audio/*.mp3; do
    s=$(basename "$a" .mp3); n=${s%%-*}
    [ -f "videos/$s.mp4" ] && continue
    [ -f "imagens/$n/cena10.jpg" ] && [ -f "imagens/$n/thumb_base.jpg" ] || continue
    mkdir "videos/.lock-$s" 2>/dev/null || continue
    echo "== $s $(date +%T)"
    python3 tools/render.py "$s" && python3 tools/thumb.py "$s"
    rmdir "videos/.lock-$s"; did=1; break
  done
  if [ $did = 0 ]; then idle=$((idle+1)); sleep 10; else idle=0; fi
done
echo fim
