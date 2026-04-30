#!/usr/bin/env bash
# PostToolUse Edit|Write — 用 ruff 自动格式化 Python 文件
set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(python -c "import json,sys; print(json.loads(sys.argv[1]).get('tool_input',{}).get('file_path',''))" "$INPUT")

# 仅处理 .py 文件
if [[ ! "$FILE_PATH" =~ \.py$ ]]; then
    exit 0
fi
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-.}"
ruff format "$FILE_PATH" --quiet || true
