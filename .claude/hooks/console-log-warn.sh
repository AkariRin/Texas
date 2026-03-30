#!/usr/bin/env bash
# PostToolUse Edit|Write — warn if console.log is found in the edited file
set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(python -c "import json,sys; print(json.loads(sys.argv[1]).get('tool_input',{}).get('file_path',''))" "$INPUT")

# only check frontend TS/JS/Vue files
if [[ ! "$FILE_PATH" =~ \.(ts|tsx|js|jsx|vue)$ ]]; then
    exit 0
fi
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

HITS=$(grep -n 'console\.log' "$FILE_PATH" | head -5 || true)
if [[ -n "$HITS" ]]; then
    echo "[console.log] found in $FILE_PATH" >&2
    echo "$HITS" >&2
    echo "[console.log] remove before committing" >&2
fi

exit 0
