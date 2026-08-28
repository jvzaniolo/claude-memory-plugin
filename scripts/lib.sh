#!/bin/bash
# Resolve o diretório do store a partir da config do usuário.
# O store NUNCA fica dentro do plugin: o plugin é descartável, a memória não.
memory_store() {
  local s
  s=$(python3 - <<'PY' 2>/dev/null
import json, os
for p in (os.path.expanduser("~/.claude/settings.json"),
          os.path.expanduser("~/.claude/settings.local.json")):
    try:
        d = json.load(open(p))
    except Exception:
        continue
    v = d.get("autoMemoryDirectory")
    if v:
        print(os.path.expanduser(v)); break
PY
)
  [ -n "$s" ] && { echo "$s"; return 0; }
  return 1
}

memory_store_or_die() {
  local s; s=$(memory_store) || {
    echo "erro: 'autoMemoryDirectory' não está definido em ~/.claude/settings.json." >&2
    echo "      Rode /memory-setup para configurar." >&2
    return 1
  }
  [ -d "$s" ] || { echo "erro: store não existe: $s" >&2; return 1; }
  echo "$s"
}
