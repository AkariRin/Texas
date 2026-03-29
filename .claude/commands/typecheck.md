# /texas:typecheck — 全栈类型检查

运行后端 mypy + 前端 vue-tsc 类型检查，按文件分组报告错误。

## 执行步骤

**1. Python mypy（严格模式）**
```bash
mypy src
```

**2. Vue + TypeScript（vue-tsc）**
```bash
cd frontend && pnpm type-check
```

## 输出格式

- 按文件分组列出类型错误
- 提供每处错误的修复建议
- 若全部通过，简单回复 ✓ 类型检查通过
