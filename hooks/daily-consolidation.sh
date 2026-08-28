#!/bin/bash
# SessionStart: dispara a consolidação diária, no máximo uma vez por dia.
#
# Por que aqui e não no launchd/cron: em macOS o store costuma ficar no iCloud
# Drive, que é pasta protegida por TCC. Processo lançado pelo launchd NÃO herda a
# permissão da sessão gráfica e recebe "Operation not permitted" até para `ls` —
# a tarefa roda, não enxerga nada, e parece saudável. O hook roda no contexto do
# Claude Code, que já tem acesso ao store (é onde o worker escreve).
#
# Nunca bloqueia: dispara em background e devolve o controle na hora.
[ -n "$CLAUDE_MEMORY_WORKER" ] && exit 0

marcador="$HOME/.claude/.memory-consolidate-last-run"
hoje=$(date '+%Y-%m-%d')
[ -f "$marcador" ] && [ "$(cat "$marcador" 2>/dev/null)" = "$hoje" ] && exit 0
echo "$hoje" > "$marcador"

script="${CLAUDE_PLUGIN_ROOT}/scripts/consolidate.sh"
[ -x "$script" ] || exit 0

( nohup "$script" >/dev/null 2>&1 & ) </dev/null >/dev/null 2>&1 &
exit 0
