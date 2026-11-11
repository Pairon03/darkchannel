#!/bin/sh
# Gera os Shorts listados num .tsv (slug, sufixo, cena, título, pergunta).
# Uso: tools/shorts_lote.sh tools/shorts_lote2.tsv [filtro-de-slug]
cd "$(dirname "$0")/.."
grep -v '^#' "$1" | grep -- "${2:-}" | while IFS='	' read -r slug suf cena titulo perg; do
  [ -z "$slug" ] && continue
  [ "$suf" = "-" ] && suf=""
  if [ "$cena" = 1 ]; then
    python3 tools/short.py "$slug" "$titulo" --pergunta "$perg" --sufixo "$suf" </dev/null
  else
    python3 tools/short.py "$slug" "$titulo" --cena "$cena" --pergunta "$perg" --sufixo "$suf" </dev/null
  fi | grep -E "pronto|Error" || echo "FALHOU $slug $suf"
done
echo fim
