#!/bin/bash
# Hook global de checkpoint de memória, FORA da thread principal. Roda em dois eventos:
#
#   Stop       — a sessão acumulou trabalho suficiente desde o último checkpoint.
#   PreCompact — a compactação está prestes a trocar o detalhe da thread por um resumo.
#
# Dispara um worker headless desanexado que retoma esta mesma conversa
# (--resume --fork-session, contexto integral), grava as conclusões duráveis na
# memória e sai. Nunca bloqueia o encerramento: a thread do usuário não espera.
#
# O store vem de autoMemoryDirectory; o prompt vem do próprio plugin.

# O worker herda os hooks globais; sem este guard, o Stop dele dispara outro worker.
[ -n "$CLAUDE_MEMORY_WORKER" ] && exit 0

. "${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh"

input=$(cat)

evento=$(echo "$input" | jq -r '.hook_event_name // empty')
transcript=$(echo "$input" | jq -r '.transcript_path // empty')
session=$(echo "$input" | jq -r '.session_id // empty')
[ -z "$transcript" ] && exit 0
[ -z "$session" ] && exit 0
[ ! -f "$transcript" ] && exit 0

lines=$(wc -l < "$transcript" | tr -d ' ')
marker="${TMPDIR:-/tmp}/claude-memory-checkpoint-${session}"
last=0
[ -f "$marker" ] && last=$(cat "$marker")

# No Stop, só vale um worker se houve trabalho substancial desde o último (~120 eventos).
#
# No PreCompact o cálculo é outro: o detalhe desta thread está prestes a virar resumo, e o
# próximo Stop já não vai encontrá-lo. O piso existe só para não disparar em cima de um worker
# que acabou de rodar. Há uma corrida com a compactação — o worker resolve o transcript no
# disco, e se perder a corrida lê o mesmo resumo que leria depois —, então o PreCompact nunca
# fica pior que o comportamento sem ele, e na maioria das vezes salva o contexto inteiro.
case "$evento" in
  PreCompact) minimo=20 ;;
  *)          minimo=120 ;;
esac

if [ $((lines - last)) -lt "$minimo" ]; then
  exit 0
fi

prompt_file="${CLAUDE_PLUGIN_ROOT}/hooks/worker-prompt.md"
[ ! -f "$prompt_file" ] && exit 0

log="$HOME/.claude/memory-worker.log"
lock="${TMPDIR:-/tmp}/claude-memory-worker.lock"
store=$(memory_store) || exit 0

(
  # Lock por mkdir: atômico e nativo (macOS não tem flock). Serializa workers de
  # sessões concorrentes, que escrevem no mesmo MEMORY.md.
  if ! mkdir "$lock" 2>/dev/null; then
    # Lock com mais de 20 min é resquício de worker morto.
    if [ -n "$(find "$lock" -maxdepth 0 -mmin +20 2>/dev/null)" ]; then
      rm -rf "$lock"
      mkdir "$lock" 2>/dev/null || exit 0
    else
      exit 0
    fi
  fi
  trap 'rm -rf "$lock"' EXIT

  # Log é append-only; segura em ~500 linhas para não crescer sem fim.
  if [ -f "$log" ] && [ "$(wc -l < "$log" | tr -d ' ')" -gt 500 ]; then
    tail -n 200 "$log" > "$log.tmp" && mv "$log.tmp" "$log"
  fi

  echo "[$(date '+%F %T')] worker iniciado evento=${evento:-Stop} sessao=${session:0:8} linhas=$lines" >> "$log"

  saida=$(mktemp)
  CLAUDE_MEMORY_WORKER=1 nohup claude -p \
    --resume "$session" \
    --fork-session \
    --no-session-persistence \
    --model sonnet \
    --permission-mode acceptEdits \
    --add-dir "$store" \
    --allowedTools Read Write Edit Glob Grep \
    < "$prompt_file" > "$saida" 2>&1
  status=$?
  cat "$saida" >> "$log"

  # O worker termina imprimindo o que fez, uma linha por arquivo, ou `nada a gravar`.
  # Sem essa linha ele não chegou ao fim — limite de uso, erro de rede, saída vazia — e
  # sai com status 0 do mesmo jeito. O marker só avança quando houve trabalho de verdade:
  # checkpoint não confirmado é retentado no próximo Stop, em vez de virar buraco em silêncio.
  if [ "$status" -eq 0 ] && grep -qE '^[[:space:]]*(criado|atualizado|removido|nada a gravar)' "$saida"; then
    echo "$lines" > "$marker"
    echo "[$(date '+%F %T')] worker terminou sessao=${session:0:8}" >> "$log"
  else
    echo "[$(date '+%F %T')] worker NAO confirmou gravacao (status=$status) sessao=${session:0:8} — sera retentado" >> "$log"
  fi
  rm -f "$saida"
  echo "" >> "$log"
) </dev/null >/dev/null 2>&1 &

exit 0
