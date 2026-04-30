#!/usr/bin/env bash
# PreToolUse Edit|Write — 阻止在项目内创建任意 .md/.txt 文件
# 白名单：README.md, CLAUDE.md, AGENTS.md, CONTRIBUTING.md, CHANGELOG.md, GEMINI.md
#         misc/*.md, .claude/rules/*.md, .claude/commands/*.md, .claude/plans/*.md, .claude/hooks/*.md
set -euo pipefail

INPUT=$(cat)

python -c "
import json, sys, os, re

data = json.loads(sys.argv[1])
fp   = data.get('tool_input', {}).get('file_path', '')

# 仅拦截 .md / .txt 文件
if not re.search(r'\.(md|txt)$', fp, re.I):
    sys.exit(0)

root = os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()).replace('\\\\', '/')
fp   = fp.replace('\\\\', '/')

# 项目外的文件不受限制（如 ~/.claude/plans/）
if not fp.startswith(root + '/'):
    sys.exit(0)

rel  = fp[len(root)+1:]

ALLOWED_NAMES = {'README.md','CLAUDE.md','AGENTS.md','CONTRIBUTING.md','CHANGELOG.md','GEMINI.md','SECURITY.md'}
ALLOWED_DIRS  = ('misc/', '.claude/rules/', '.claude/commands/', '.claude/plans/', '.claude/hooks/')

if os.path.basename(rel) in ALLOWED_NAMES:
    sys.exit(0)
if any(rel.startswith(d) for d in ALLOWED_DIRS):
    sys.exit(0)

print('[block-md-txt] blocked: ' + rel, file=sys.stderr)
print('[block-md-txt] allowed paths: README.md  CLAUDE.md  misc/*.md  .claude/rules/*.md  .claude/commands/*.md', file=sys.stderr)
sys.exit(2)
" "$INPUT"
