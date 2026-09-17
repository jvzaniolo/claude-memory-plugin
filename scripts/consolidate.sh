#!/bin/bash
set -eu
root="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$root/scripts/runtime.py" consolidate "$@"
