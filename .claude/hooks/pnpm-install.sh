#!/usr/bin/env bash
# PostToolUse Edit|Write — frontend/package.json 变更时自动执行 pnpm install
set -euo pipefail

INPUT=$(cat)

FILE_PATH=$(python -c "import json,sys; print(json.loads(sys.argv[1]).get('tool_input',{}).get('file_path',''))" "$INPUT")

# 规范化路径分隔符并去除项目根路径前缀
NORMALIZED=$(python -c "
import sys, os
fp   = sys.argv[1].replace('\\\\', '/')
root = os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()).replace('\\\\', '/')
rel  = fp[len(root)+1:] if fp.startswith(root + '/') else fp.lstrip('/')
print(rel)
" "$FILE_PATH")

if [[ "$NORMALIZED" != "frontend/package.json" ]]; then
    exit 0
fi

PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-.}"
echo "[pnpm-install] package.json changed, running pnpm install..." >&2
cd "$PROJECT_ROOT/frontend"
pnpm install
