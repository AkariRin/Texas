#!/usr/bin/env bash
# PostToolUse Edit|Write — 用 Prettier 自动格式化前端文件
set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(python -c "import json,sys; print(json.loads(sys.argv[1]).get('tool_input',{}).get('file_path',''))" "$INPUT")

# 仅处理前端 TS/JS/Vue 文件
if [[ ! "$FILE_PATH" =~ \.(ts|tsx|js|jsx|vue)$ ]]; then
    exit 0
fi
if [[ "$FILE_PATH" != */frontend/* ]]; then
    exit 0
fi
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-.}"
cd "$PROJECT_ROOT/frontend"
npx prettier --write "$FILE_PATH" || true
