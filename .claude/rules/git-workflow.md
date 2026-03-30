# Git 工作流规则（强制执行）

## 提交格式（Conventional Commits）

所有提交必须遵循以下格式：

```
<type>(<scope>): <description>

[可选 body]
[可选 footer]
```

**type 枚举：**

| type | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 重构（不改变行为） |
| `style` | 格式化/代码风格（不改变逻辑） |
| `docs` | 文档变更 |
| `test` | 测试相关 |
| `chore` | 构建、依赖、CI/CD 等杂项 |
| `perf` | 性能优化 |
| `ci` | CI/CD 配置变更 |

**scope 示例：** `backend`、`frontend`、`api`、`ws`、`db`、`llm`、`handler`、`task`

**description：** 使用中文或英文均可，但同一 PR 保持一致；祈使语气；不超过 72 字符。

示例：
```
feat(api): 添加 LLM 模型配置的分页查询接口
fix(ws): 修复 HeartbeatMonitor 在断线重连时的内存泄漏
refactor(services): 将 PersonnelService 的重试逻辑抽取为公共工具函数
```

## 提交粒度

- **一个提交做一件事**：功能开发、Bug 修复、重构、格式化必须分开提交
- **禁止**在同一提交中混合：新功能 + 重构 + 样式修改
- 数据库迁移文件必须**单独提交**，且提交信息注明迁移内容
- 前后端联动改动（同一功能的 API + 前端）可放同一提交，但要在 scope 中体现

## 分支管理

- **功能分支**：从 `master` 切出，命名 `feat/<short-desc>` 或 `fix/<short-desc>`
- **禁止**直接 push 到 `master`（通过 settings.json 权限控制辅助约束）
- 分支生命周期短暂，合并后立即删除

## PR 流程

提交 PR 前必须通过以下检查（本地自验）：

```bash
# 后端
ruff check src --fix && ruff format src
mypy src

# 前端
cd frontend && pnpm lint && pnpm type-check
```

- PR 描述必须说明：**变更原因**、**实现方式**、**验证步骤**
- 数据库 schema 变更的 PR 必须附带迁移回滚方案

## 禁止操作

- **禁止** `git push --force` 到 `master`（保护共享历史）
- **禁止** `git commit --no-verify` 跳过 pre-commit hooks
- **禁止** `git reset --hard` 抹除已推送的提交（使用 `revert` 代替）
- **禁止**提交包含以下内容的文件：`.env`、`*.pem`、`*secret*`、包含硬编码密钥的配置文件

## 变更范围控制

- 避免「顺手」改动：修复 Bug 时发现的代码风格问题，应在独立 commit 或 PR 中处理
- 大型重构分多个小 PR 逐步合并，每个 PR 保持独立可回滚
