#!/bin/bash
# Consolidação episódico→semântico do store de memória.
# Roda diariamente. Se não há candidato, sai sem chamar o modelo (custo zero).
#
# O que faz: memória fria (>30d) + pouco usada + coberta por dossiê tem sua
# ESSÊNCIA promovida para 1-2 frases no dossiê. O arquivo detalhado PERMANECE
# no disco, intocado — muda o que está em primeiro plano, não o que existe.
set -uo pipefail

. "$(dirname "$0")/lib.sh"
STORE="${MEM_STORE:-$(memory_store_or_die)}" || exit 1
LOG="$HOME/.claude/memory-consolidate.log"
STATE="$HOME/.claude/memory-consolidated.json"
LOCK="$HOME/.claude/.memory-consolidate.lock"
LOTE="${MEM_BATCH:-5}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

# lock por mkdir (macOS não tem flock), com expiração de 30 min
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -d "$LOCK" ] && [ "$(find "$LOCK" -maxdepth 0 -mmin +30 2>/dev/null)" ]; then
    rmdir "$LOCK" 2>/dev/null; mkdir "$LOCK" 2>/dev/null || { log "lock preso, saindo"; exit 0; }
  else
    log "outra execução em andamento, saindo"; exit 0
  fi
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

CAND=$(MEM_COLD_DAYS="${MEM_COLD_DAYS:-30}" python3 "$(dirname "$0")/candidates.py" "$STORE" 2>>"$LOG")
TOTAL=$(echo "$CAND" | python3 -c 'import json,sys; print(json.load(sys.stdin)["total"])' 2>/dev/null || echo 0)

if [ "$TOTAL" -eq 0 ]; then
  log "nada a consolidar (0 candidatos)"; exit 0
fi

LOTE_JSON=$(echo "$CAND" | LOTE="$LOTE" python3 -c "
import json,sys,os
d=json.load(sys.stdin); n=int(os.environ['LOTE'])
d['candidatos']=d['candidatos'][:n]; d['total']=len(d['candidatos'])
print(json.dumps(d, ensure_ascii=False))
")
N=$(echo "$LOTE_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["total"])' 2>/dev/null || echo 0)
if [ "$N" -eq 0 ]; then log "ERRO ao montar o lote — abortando sem tocar em nada"; exit 1; fi
log "candidatos: $TOTAL | processando lote de $N"

PROMPT=$(cat "$(dirname "$0")/consolidate-prompt.md")
OUT=$(echo "$LOTE_JSON" | CLAUDE_MEMORY_WORKER=1 claude -p \
        --model sonnet --permission-mode acceptEdits \
        --add-dir "$STORE" --allowedTools Read Write Edit Glob Grep \
        --append-system-prompt "$PROMPT" \
        "Consolide as memórias do JSON abaixo, seguindo as instruções do sistema. JSON: $(echo "$LOTE_JSON")" \
        2>&1)
RC=$?
echo "$OUT" >> "$LOG"

# rc=0 não basta: o relatório precisa existir e não ser rastro de exceção
if [ "$RC" -eq 0 ] && echo "$OUT" | grep -qE '^(consolidada|já-resumida|pulada) ' \
   && ! echo "$OUT" | grep -q 'Traceback'; then
  echo "$LOTE_JSON" | python3 -c "
import json,sys,os
novo=json.load(sys.stdin)
p=os.path.expanduser('~/.claude/memory-consolidated.json')
try:
    est=json.load(open(p))
except Exception:
    est={}
import re
store=novo['store']
for c in novo['candidatos']:
    t=open(os.path.join(store,c['arquivo'])).read()
    m=re.search(r'^\s*modified:\s*(.+?)\s*\$', t, re.M)
    est[c['arquivo']]={'modified': m.group(1).strip() if m else None,
                       'consolidado_em': __import__('datetime').date.today().isoformat()}
json.dump(est, open(p,'w'), ensure_ascii=False, indent=2)
print(f'marcadas {len(novo[\"candidatos\"])} memórias como consolidadas')
" >> "$LOG" 2>&1
  log "concluído (rc=0)"
else
  log "FALHOU (rc=$RC, sem relatório válido) — nada marcado, tenta de novo amanhã"
fi
