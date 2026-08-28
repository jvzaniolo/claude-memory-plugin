#!/bin/bash
# Busca no store de memória em duas camadas, sem índice e sem embedding.
#   1. LITERAL  — grep pelo termo: pega identificador exato (número de ticket, PR, chave de config)
#   2. CATÁLOGO — nome + descrição de cada memória, para o modelo escolher por sentido
# Uso: memory-find.sh [termo]   (sem termo, imprime só o catálogo)
. "$(dirname "$0")/lib.sh"
STORE="${MEM_STORE:-$(memory_store_or_die)}" || exit 1
cd "$STORE" || exit 1

if [ $# -gt 0 ]; then
  echo "═══ LITERAL: arquivos contendo \"$*\" ═══"
  grep -ril -- "$*" . 2>/dev/null | sed 's|^\./|  |' | grep -v '^  MEMORY.md$' || echo "  (nenhum)"
  echo
fi

echo "═══ CATÁLOGO: $(find . -name '*.md' ! -name 'MEMORY.md' | wc -l | tr -d ' ') memórias ═══"
find . -name '*.md' ! -name 'MEMORY.md' -print0 | sort -z | while IFS= read -r -d '' f; do
  rel="${f#./}"
  d=$(awk '/^description:/{sub(/^description:[ ]*/,""); gsub(/^"|"$/,""); print; exit}' "$f")
  t=$(awk '/^[[:space:]]*type:/{print $2; exit}' "$f")
  printf '%s [%s] %s\n' "$rel" "${t:-?}" "$d"
done
