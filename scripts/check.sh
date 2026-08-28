#!/bin/bash
# Verifica a integridade do store de memória do auto-memory.
# Um arquivo é "alcançável" se tem linha no MEMORY.md OU se algum dossiê o referencia por [[link]].
# Uso: ~/.claude/memory-check.sh
set -uo pipefail
. "$(dirname "$0")/lib.sh"
STORE="${1:-$(memory_store_or_die)}" || exit 1
IDX="$STORE/MEMORY.md"
[ -f "$IDX" ] || { echo "sem MEMORY.md em $STORE"; exit 1; }

cd "$STORE" || exit 1
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT

find . -name '*.md' -type f | sed 's|^\./||' | grep -v '^MEMORY.md$' | sort > "$tmp/disco"
grep -o '](\([^)]*\.md\))' MEMORY.md | sed 's/^](//;s/)$//' | sort -u > "$tmp/indice"
# slugs referenciados por [[link]] em qualquer arquivo, convertidos para caminho
grep -ho '\[\[[^]]*\]\]' -r . 2>/dev/null | sed 's/\[\[//;s/\]\]//' \
  | grep -E '^[a-z0-9][a-z0-9/-]*$' | grep -- '-' \
  | sed 's|$|.md|' | sort -u > "$tmp/linkados"

erros=0

echo "── store: $(wc -l < "$tmp/disco" | tr -d ' ') memórias | índice: $(grep -c '^- ' MEMORY.md) linhas / $(wc -c < MEMORY.md | tr -d ' ') bytes (teto 200 / 25600)"

echo
echo "── linhas do índice apontando para arquivo inexistente:"
if comm -13 "$tmp/disco" "$tmp/indice" | grep -q .; then
  comm -13 "$tmp/disco" "$tmp/indice" | sed 's/^/   ✗ /'; erros=1
else echo "   nenhuma"; fi

echo
echo "── arquivos inalcançáveis (sem linha no índice E sem nenhum [[link]] apontando):"
inalc=$(comm -23 "$tmp/disco" "$tmp/indice" | while read -r f; do
          grep -qxF "$f" "$tmp/linkados" || echo "$f"
        done)
if [ -n "$inalc" ]; then echo "$inalc" | sed 's/^/   ✗ /'; erros=1
else echo "   nenhum"; fi

echo
echo "── [[links]] quebrados (referência sem arquivo):"
if comm -13 "$tmp/disco" "$tmp/linkados" | grep -q .; then
  comm -13 "$tmp/disco" "$tmp/linkados" | sed 's/^/   ✗ /'; erros=1
else echo "   nenhum"; fi

echo
echo "── memórias sem frontmatter type:"
semtipo=$(while read -r f; do
   head -14 "$f" | grep -q '^\s*type:' || echo "$f"
 done < "$tmp/disco")
if [ -n "$semtipo" ]; then echo "$semtipo" | sed 's/^/   ✗ /'; erros=1
else echo "   nenhuma"; fi

echo
[ "$erros" -eq 0 ] && echo "✓ store íntegro" || echo "✗ store com problemas acima"
exit "$erros"
