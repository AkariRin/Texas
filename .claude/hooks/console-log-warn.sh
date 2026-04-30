#!/usr/bin/env bash
# PostToolUse Edit|Write — 若被编辑的文件中存在 console.log 则发出警告
set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(python -c "import json,sys; print(json.loads(sys.argv[1]).get('tool_input',{}).get('file_path',''))" "$INPUT")

# 仅检查前端 TS/JS/Vue 文件
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
