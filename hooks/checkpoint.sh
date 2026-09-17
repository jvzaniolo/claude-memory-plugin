#!/bin/bash
set -eu
[ -n "${CLAUDE_MEMORY_WORKER:-}" ] && exit 0
root="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$root/scripts/runtime.py" dispatch-checkpoint "$@"
