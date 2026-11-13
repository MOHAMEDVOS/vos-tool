#!/bin/bash
# PostToolUse hook: syntax-check edited .py files and type-check edited webapp TS files.
# Exit 2 sends the error back to Claude so it fixes the break right away.
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
FILE=$(jq -r '.tool_input.file_path // empty')
[ -f "$FILE" ] || exit 0

case "$FILE" in
  *.py)
    PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY=python3
    # compile() instead of py_compile: checks syntax without writing .pyc files
    OUT=$("$PY" -c 'import sys; compile(open(sys.argv[1], encoding="utf-8").read(), sys.argv[1], "exec")' "$FILE" 2>&1) || { echo "Syntax error in $FILE:
$OUT" >&2; exit 2; }
    ;;
  "$ROOT"/webapp/*.ts|"$ROOT"/webapp/*.tsx)
    OUT=$(cd "$ROOT/webapp" && node_modules/.bin/tsc -b 2>&1) || { echo "TypeScript errors after editing $FILE:
$OUT" | head -40 >&2; exit 2; }
    ;;
esac
exit 0
