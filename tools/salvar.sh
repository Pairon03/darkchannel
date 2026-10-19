#!/bin/sh
# Copia imagens geradas (tool-results) para imagens/<NN>/ na ordem dada.
# Uso: tools/salvar.sh <NN> <cena_inicial> blob1 blob2 ...
T=/root/.claude/projects/-home-user-darkchannel/e4a94c7a-1d76-5e59-9a7a-e40e92f1b91c/tool-results
D=/home/user/darkchannel/imagens/$1; mkdir -p "$D"; i=$2; shift 2
for b in "$@"; do
  if [ "$b" = thumb ]; then continue; fi
  case "$b" in T:*) cp "$T/mcp-Magic_Patterns-blob-${b#T:}.jpg" "$D/thumb_base.jpg";;
    *) cp "$T/mcp-Magic_Patterns-blob-$b.jpg" "$D/$(printf 'cena%02d.jpg' $i)"; i=$((i+1));; esac
done
ls "$D" | tr '\n' ' '; echo
