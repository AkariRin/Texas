#!/usr/bin/env bash
# Stop — block session end if any modified JS/TS/Vue file contains console.log
set -euo pipefail

INPUT=$(cat)

# avoid infinite loop when the hook itself triggers a stop
STOP_HOOK_ACTIVE=$(python -c "import json,sys; print(json.loads(sys.argv[1]).get('stop_hook_active', False))" "$INPUT")
if [[ "$STOP_HOOK_ACTIVE" == "True" ]]; then
    exit 0
fi

PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-.}"

# collect modified JS/TS/Vue files
DIRTY_FILES=$(git -C "$PROJECT_ROOT" diff --name-only HEAD 2>/dev/null \
    | grep -E '\.(ts|tsx|js|jsx|vue)$' || true)

BAD_FILES=()
while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    FULL="$PROJECT_ROOT/$f"
    if [[ -f "$FULL" ]] && grep -q 'console\.log' "$FULL"; then
        BAD_FILES+=("$f")
    fi
done <<< "$DIRTY_FILES"

if [[ ${#BAD_FILES[@]} -gt 0 ]]; then
    JOINED=$(IFS=' '; echo "${BAD_FILES[*]}")
    echo "{\"decision\":\"block\",\"reason\":\"console.log found in: $JOINED — remove before finishing\"}"
fi
