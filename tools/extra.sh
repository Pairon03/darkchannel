#!/bin/sh
# Copia imagens extras geradas (tool-results) com nome explícito.
# Uso: tools/extra.sh <NN> 01b=<blob> 01c=<blob> ...  -> imagens/NN/cena01b.jpg ...
T=/root/.claude/projects/-home-user-darkchannel/e4a94c7a-1d76-5e59-9a7a-e40e92f1b91c/tool-results
D=/home/user/darkchannel/imagens/$1; shift
for a in "$@"; do cp "$T/mcp-Magic_Patterns-blob-${a#*=}.jpg" "$D/cena${a%%=*}.jpg"; done
ls "$D" | wc -l
