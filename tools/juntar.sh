#!/bin/sh
# Baixa as partes da narração (URLs da ElevenLabs) e junta em audio/<slug>.mp3,
# com 0,6 s de pausa entre elas. A ElevenLabs aceita no máximo 5.000 caracteres
# por geração, então cada roteiro é narrado em 2 partes.
# Uso: tools/juntar.sh <slug> URL1 URL2 [...]
set -e
cd "$(dirname "$0")/.."
slug=$1; shift
tmp=$(mktemp -d); i=0; inputs=""; filt=""
for u in "$@"; do
  curl -sSL -o "$tmp/p$i.mp3" "$u"
  inputs="$inputs -i $tmp/p$i.mp3"; i=$((i+1))
done
n=$i; j=0; chain=""
while [ $j -lt $n ]; do
  if [ $j -lt $((n-1)) ]; then chain="$chain[$j:a]apad=pad_dur=0.6[a$j];"; else chain="$chain[$j:a]anull[a$j];"; fi
  filt="$filt[a$j]"; j=$((j+1))
done
ffmpeg -y -hide_banner -loglevel error $inputs -filter_complex "${chain}${filt}concat=n=$n:v=0:a=1[o]" \
  -map "[o]" -c:a libmp3lame -b:a 192k "audio/$slug.mp3"
rm -rf "$tmp"
ffprobe -v error -show_entries format=duration -of csv=p=0 "audio/$slug.mp3"
