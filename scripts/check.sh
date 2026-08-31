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
# slugs referenciados por [[link]], convertidos para caminho. Duas listas, porque os
# dois usos divergem: alcançabilidade conta link em qualquer contexto, mas link quebrado
# não pode acusar o que está num exemplo (bloco de código, `inline` ou citação).
TMP="$tmp" python3 - <<'PYEOF'
import os, re, glob

TMP = os.environ["TMP"]
SLUG = re.compile(r'^[a-z0-9][a-z0-9/-]*$')
LINK = re.compile(r'\[\[([^\]]*)\]\]')


def slugs(texto):
    for bruto in LINK.findall(texto):
        if SLUG.match(bruto) and '-' in bruto:
            yield bruto + '.md'


def sem_exemplos(texto):
    linhas, em_bloco = [], False
    for linha in texto.splitlines():
        if linha.lstrip().startswith('```'):
            em_bloco = not em_bloco
            continue
        if em_bloco or linha.lstrip().startswith('>'):
            continue
        linhas.append(re.sub(r'`[^`]*`', '', linha))
    return '\n'.join(linhas)


todos, reais = set(), set()
for caminho in glob.glob('**/*.md', recursive=True):
    texto = open(caminho).read()
    todos.update(slugs(texto))
    reais.update(slugs(sem_exemplos(texto)))

for nome, conjunto in (('linkados', todos), ('linkados_reais', reais)):
    with open(os.path.join(TMP, nome), 'w') as saida:
        saida.write(''.join(s + '\n' for s in sorted(conjunto)))
PYEOF

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
if comm -13 "$tmp/disco" "$tmp/linkados_reais" | grep -q .; then
  comm -13 "$tmp/disco" "$tmp/linkados_reais" | sed 's/^/   ✗ /'; erros=1
else echo "   nenhum"; fi

echo
echo "── memórias sem frontmatter type:"
semtipo=$(while read -r f; do
   head -14 "$f" | grep -q '^\s*type:' || echo "$f"
 done < "$tmp/disco")
if [ -n "$semtipo" ]; then echo "$semtipo" | sed 's/^/   ✗ /'; erros=1
else echo "   nenhuma"; fi

echo
echo "── supersessão declarada mas incompleta:"
sup=$(STORE="$STORE" python3 - <<'PYEOF'
import os, re, glob, sys
STORE=os.environ["STORE"]
probs=[]
alvo_de={}
for p in glob.glob(os.path.join(STORE,"**","*.md"), recursive=True):
    rel=os.path.relpath(p,STORE)
    if rel=="MEMORY.md": continue
    txt=open(p).read()
    # só o frontmatter: `superseded_by` no corpo é exemplo, não declaração
    cab=txt.split("---",2)[1] if txt.startswith("---") else ""
    m=re.search(r'^\s*superseded_by:\s*\[([^\]]*)\]\s*$', cab, re.M)
    if not m: continue
    alvos=[s.strip() for s in m.group(1).split(",") if s.strip()]
    if not alvos:
        probs.append(f"{rel}: superseded_by vazio"); continue
    for a in alvos:
        alvo_de.setdefault(rel,[]).append(a)
        # o sucessor precisa existir
        if not any(os.path.exists(os.path.join(STORE,c)) for c in (a+".md", os.path.join("tasks",a+".md"))):
            probs.append(f"{rel}: superseded_by aponta para inexistente '{a}'")
    # o corpo precisa avisar o leitor, senão a marca só existe para máquina
    corpo=txt.split("---",2)[-1]
    if "Superada por" not in corpo and "SUPERADA" not in corpo.upper():
        probs.append(f"{rel}: marcada como superada, mas o corpo não avisa o leitor")
# ciclo simples
for a, alvos in alvo_de.items():
    base=lambda x: os.path.basename(x)[:-3]
    for alvo in alvos:
        for b, balvos in alvo_de.items():
            if base(b)==alvo and base(a) in balvos:
                probs.append(f"ciclo de supersessão entre '{base(a)}' e '{alvo}'")
print("\n".join(sorted(set(probs))))
PYEOF
)
if [ -n "$sup" ]; then echo "$sup" | sed 's/^/   ✗ /'; erros=1; else echo "   nenhuma"; fi

echo
[ "$erros" -eq 0 ] && echo "✓ store íntegro" || echo "✗ store com problemas acima"
exit "$erros"
