# /texas:update-docs — 分析 codebase 并更新提示词文档

扫描整个代码库，对比 `CLAUDE.md` 和 `.claude/rules/*.md` 中的描述与实际代码状态，找出过时/缺失/不一致的内容，更新后保持文档与代码同步。

## 执行步骤

### 1. 扫描项目结构

读取以下内容，建立对当前代码库的实际认知：

```
src/
├── api/         # 路由文件列表
├── services/    # 服务文件列表
├── models/      # ORM 模型文件列表
├── handlers/    # 处理器文件列表
├── tasks/       # Celery 任务文件列表
└── core/        # 基础设施模块列表
frontend/src/
├── apis/        # 前端 API 层文件列表
├── stores/      # Pinia Store 文件列表
├── views/       # 页面视图列表
└── router/      # 路由配置
```

同时读取：`pyproject.toml`（Python 依赖/工具配置）、`frontend/package.json`（前端依赖）。

### 2. 检查 CLAUDE.md 一致性

对比 `CLAUDE.md` 中的以下描述与实际代码状态：

| 检查项 | 验证方式 |
|--------|---------|
| 服务层表格中的文件名和类名 | 检查 `src/services/` 下是否存在对应文件 |
| 常用命令（bash 代码块）| 验证命令中引用的模块/脚本路径是否存在 |
| 架构目录树 | 对比实际目录结构 |
| Slash Commands 表格 | 对比 `.claude/commands/` 下实际存在的命令文件 |
| misc/ 文档列表 | 验证 `misc/` 下文件是否存在 |
| 前端路由说明 | 读取 `frontend/src/router/index.ts` 验证 |

### 3. 检查 .claude/rules/*.md 一致性

逐一检查每个规则文件中引用的具体文件路径、模块名、类名是否仍然存在：

- `coding-style.md`：检查引用的目录结构、Base 类导入路径
- `git-workflow.md`：检查 PR 检查命令是否有效
- `performance.md`：检查引用的服务类名
- `security.md`：检查引用的配置文件路径
- `llm.md`：检查引用的服务文件路径

### 4. 生成差异报告

输出格式：

```
## CLAUDE.md 差异报告

### 过时项
- [文件:行] 描述 → 建议修正内容

### 缺失项（代码已有但文档未收录）
- 新增服务/模块/命令：建议添加描述

### 仍然准确
- ✓ 架构概览
- ✓ ...

## .claude/rules/ 差异报告
...
```

### 5. 执行更新

将差异报告展示给用户确认，**等待明确授权后**再执行文件修改。

修改范围仅限：
- `CLAUDE.md`
- `.claude/rules/*.md`

## 注意事项

- 不修改业务代码，只更新文档
- 若发现重大架构变更（如整个模块被删除），需在报告中单独高亮
- 保持原有文档风格和格式，只更新内容
