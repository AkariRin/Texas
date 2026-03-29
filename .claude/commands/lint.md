# /texas:lint — 全栈 Lint 检查

运行后端 + 前端的完整 lint 与格式化检查，汇总所有问题。

## 执行步骤

按以下顺序运行，遇到错误继续执行后续步骤，最后统一汇报：

**1. 后端 Ruff Lint（自动修复）**
```bash
ruff check src --fix
```

**2. 后端 Ruff 格式化**
```bash
ruff format src
```

**3. 前端 Lint（Oxlint + ESLint，自动修复）**
```bash
cd frontend && pnpm lint
```

**4. 前端格式化（Prettier）**
```bash
cd frontend && pnpm format
```

## 输出格式

所有步骤完成后，汇总报告：
- 每个步骤的通过/失败状态
- 剩余错误（无法自动修复的）及修复建议
- 若全部通过，简单回复 ✓ 无问题
