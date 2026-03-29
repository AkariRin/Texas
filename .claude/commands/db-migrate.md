# /texas:db-migrate — 数据库迁移工作流

管理双数据库（主库 + 聊天库）的 Alembic 迁移。

## 数据库说明

| 库 | 目标标识 | 迁移文件位置 | ORM Base |
|----|----------|-------------|----------|
| 主库（核心业务）| `main` | `src/core/db/migrations/versions/` | `Base` |
| 聊天库（聊天记录）| `chat` | `src/core/db/chat_migrations/versions/` | `ChatBase` |

## 常用操作

### 查看当前状态
```bash
python -m src.core.db.cli current --target main
python -m src.core.db.cli current --target chat
```

### 自动生成迁移（模型变更后）
```bash
python -m src.core.db.cli autogenerate --target main -m "描述变更内容"
python -m src.core.db.cli autogenerate --target chat -m "描述变更内容"
```

### 执行迁移
```bash
python -m src.core.db.cli migrate                  # 升级全部库到 head
python -m src.core.db.cli migrate --target main    # 仅升级主库
python -m src.core.db.cli migrate --target chat    # 仅升级聊天库
```

### 查看迁移历史
```bash
python -m src.core.db.cli history --target main
python -m src.core.db.cli history --target chat
```

### 回退迁移
```bash
python -m src.core.db.cli downgrade --target main -1   # 回退一步
```

## 标准工作流（模型变更）

1. 修改 `src/models/<module>.py` 中的 ORM 模型
2. 确认模型在 `src/models/__init__.py` 中已导出（Alembic 自动检测依赖此步）
3. 生成迁移文件：
   ```bash
   python -m src.core.db.cli autogenerate --target <main|chat> -m "<变更描述>"
   ```
4. **检查生成的迁移文件**（重要：自动生成可能遗漏或误判，需人工核查）
5. 执行迁移：
   ```bash
   python -m src.core.db.cli migrate --target <main|chat>
   ```
6. 验证结果：
   ```bash
   python -m src.core.db.cli current --target <main|chat>
   ```

## 注意事项

- 迁移注册表：`src/core/db/migration_registry.py`（管理各库的 Alembic 配置）
- 聊天库使用月分区表，`autogenerate` 不能自动检测分区，需手动处理
