#!/bin/bash
# Busca no store de memória em duas camadas, sem índice e sem embedding.
#   1. LITERAL  — grep pelo termo: pega identificador exato (número de ticket, PR, chave de config)
#   2. CATÁLOGO — nome + descrição de cada memória, para o modelo escolher por sentido
#
# O catálogo omite por padrão o que já tem linha no MEMORY.md: essas memórias já estão em
# contexto, e reimprimi-las é metade do custo da busca sem nenhuma informação nova. Sobra o
# que não está em lugar nenhum — membros de dossiê e tasks/ —, que é o valor real da busca.
#
# Uso: find.sh [--tudo] [termo]   (--tudo inclui as já indexadas; sem termo, só o catálogo)
. "$(dirname "$0")/lib.sh"
STORE="${MEM_STORE:-$(memory_store_or_die)}" || exit 1
cd "$STORE" || exit 1

TUDO=0
[ "${1:-}" = "--tudo" ] && { TUDO=1; shift; }

if [ $# -gt 0 ]; then
  echo "═══ LITERAL: arquivos contendo \"$*\" ═══"
  grep -ril -- "$*" . 2>/dev/null | sed 's|^\./|  |' | grep -v '^  MEMORY.md$' || echo "  (nenhum)"
  echo
fi

indexadas=$(mktemp); trap 'rm -f "$indexadas"' EXIT
if [ "$TUDO" -eq 0 ] && [ -f MEMORY.md ]; then
  grep -o '](\([^)]*\.md\))' MEMORY.md | sed 's/^](//;s/)$//' | sort -u > "$indexadas"
fi

listadas=0
corpo=$(find . -name '*.md' ! -name 'MEMORY.md' -print0 | sort -z |
  while IFS= read -r -d '' f; do
    rel="${f#./}"
    grep -qxF "$rel" "$indexadas" 2>/dev/null && continue
    d=$(awk '/^description:/{sub(/^description:[ ]*/,""); gsub(/^"|"$/,""); print; exit}' "$f")
    t=$(awk '/^[[:space:]]*type:/{print $2; exit}' "$f")
    printf '%s [%s] %s\n' "$rel" "${t:-?}" "$d"
  done)
listadas=$(printf '%s' "$corpo" | grep -c . )
omitidas=$(wc -l < "$indexadas" | tr -d ' ')

if [ "$TUDO" -eq 1 ]; then
  echo "═══ CATÁLOGO COMPLETO: $listadas memórias ═══"
else
  echo "═══ CATÁLOGO: $listadas memórias fora do índice ═══"
  echo "(as outras $omitidas já têm linha no MEMORY.md, que você leu no início da sessão —"
  echo " escolha entre as duas listas juntas. Para reimprimi-las aqui: find.sh --tudo)"
fi
printf '%s\n' "$corpo"
