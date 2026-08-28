#!/bin/bash
# Wrapper de caminho estável para o agendador.
#
# O plugin instalado vive em ~/.claude/plugins/cache/<marketplace>/memory/<versão>/,
# e esse caminho muda a cada atualização — um LaunchAgent ou cron apontando direto
# para lá quebra em silêncio no primeiro update. Este wrapper fica num lugar fixo
# e resolve a versão corrente na hora de rodar.
#
# Instale-o em ~/.claude/memory-consolidate-run.sh e agende ESTE arquivo.
set -uo pipefail

# 1. plugin instalado: pega a versão de modificação mais recente
alvo=$(find "$HOME/.claude/plugins/cache" -type f -path '*/memory/*/scripts/consolidate.sh' \
        -exec stat -f '%m %N' {} \; 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)

# 2. fallback: clone de desenvolvimento
if [ -z "$alvo" ]; then
  for c in "$HOME/Developer/claude-memory-plugin/scripts/consolidate.sh" \
           "$HOME/.claude/legacy-memory/memory-consolidate.sh"; do
    [ -x "$c" ] && { alvo="$c"; break; }
  done
fi

if [ -z "$alvo" ]; then
  echo "[$(date '+%F %T')] wrapper: consolidate.sh não encontrado" >> "$HOME/.claude/memory-consolidate.log"
  exit 0
fi

exec "$alvo" "$@"
