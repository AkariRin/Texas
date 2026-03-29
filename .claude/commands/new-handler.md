# /texas:new-handler — 创建 Bot 事件处理器

创建新的 Bot 事件处理器，`ComponentScanner` 会自动扫描 `src/handlers/` 下的所有处理器。

## 收集信息

若未提供，请询问以下内容：

| 字段 | 说明 | 示例 |
|------|------|------|
| 处理器名称 | 英文标识符（snake_case）| `greeting` |
| 功能描述 | 中文描述 | 问候回复 |
| 触发方式 | 见下方触发装饰器表 | `on_command` |
| 触发条件 | 命令名/关键词/正则/事件类型 | `/hello` |
| 权限要求 | 见权限枚举 | `ANYONE` |
| 消息作用域 | `all` / `group` / `private` | `all` |
| 依赖服务 | 需要注入的 Service 类（可选）| `PersonnelService` |

## 触发装饰器

| 装饰器 | 用途 | 关键参数 |
|--------|------|----------|
| `@on_command(cmd, aliases)` | `/cmd` 命令 | `cmd: str`, `aliases: set[str]` |
| `@on_keyword(keywords)` | 消息含关键词 | `keywords: set[str]` |
| `@on_regex(pattern)` | 正则匹配 | `pattern: str` |
| `@on_startswith(prefix)` | 消息前缀 | `prefix: str` |
| `@on_endswith(suffix)` | 消息后缀 | `suffix: str` |
| `@on_fullmatch(text)` | 完全匹配 | `text: str` |
| `@on_notice(notice_type)` | 通知事件 | `notice_type: str` |
| `@on_request(request_type)` | 请求事件 | `request_type: str` |
| `@on_poke()` | 戳一戳 | — |
| `@on_event(event_type)` | 任意 post_type | `event_type: str` |

## 权限枚举（`Permission`）

```python
Permission.ANYONE       # 所有人
Permission.GROUP_MEMBER # 群成员
Permission.GROUP_ADMIN  # 群管理员
Permission.GROUP_OWNER  # 群主
Permission.ADMIN        # 超级管理员
```

## 文件位置

`src/handlers/<handler_name>.py`

## 代码结构约定

```python
"""<模块功能描述>。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from src.core.framework.decorators import (
    Permission,
    controller,
    on_command,  # 按实际使用选择
)

if TYPE_CHECKING:
    from src.core.framework.context import Context

# 按需导入（非 TYPE_CHECKING，因为运行时需要类型标注）
from src.services.xxx import XxxService

logger = structlog.get_logger()


@controller(
    name="<handler_name>",
    display_name="<展示名称>",
    description="<中文功能描述>",
    tags=["<分类标签>"],
    version="1.0.0",
    default_enabled=False,  # 默认关闭，需管理员手动开启；system=True 时强制启用
)
class XxxHandler:
    """<处理器描述>。"""

    @on_command(
        cmd="<命令>",
        permission=Permission.ANYONE,
        message_scope="all",
        display_name="<方法展示名>",
        description="<方法描述>",
    )
    async def handle_xxx(self, ctx: Context) -> bool:
        """<方法描述>。"""
        if not ctx.has_service(XxxService):
            return False

        try:
            service = ctx.get_service(XxxService)
            # 业务逻辑
            await ctx.reply("回复内容")
        except Exception as exc:
            logger.error(
                "<操作>失败",
                error=str(exc),
                event_type="<handler_name>.error",
            )
        return False  # True=阻止后续处理器，False=继续传递
```

## 参考文件

- 处理器示例：`src/handlers/personnel_handler.py`
- 装饰器定义（含完整签名）：`src/core/framework/decorators.py`
- Context API：`src/core/framework/context.py`
- 扫描注册逻辑：`src/core/framework/scanner.py`
