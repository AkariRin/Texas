#!/usr/bin/env bash
# PostToolUse Edit|Write — auto-format Python files with ruff
set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(python -c "import json,sys; print(json.loads(sys.argv[1]).get('tool_input',{}).get('file_path',''))" "$INPUT")

# only process .py files
if [[ ! "$FILE_PATH" =~ \.py$ ]]; then
    exit 0
fi
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-.}"
ruff format "$FILE_PATH" --quiet || true
