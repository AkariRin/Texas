---
name: texas-new-handler
description: Use when creating a new bot event handler in the Texas QQ bot project. Covers @controller/@on_command/@on_keyword/@on_regex decorators, Permission system, MessageScope, Context API, and service injection patterns.
---

# Texas: 创建 Bot 事件处理器

## 概述

Texas 使用装饰器驱动的处理器框架。`ComponentScanner` 自动扫描 `src/handlers/` 目录，所有 `@controller` 类无需手动注册。

## 文件位置约定

```
src/handlers/<功能名>_handler.py
```

例：`src/handlers/echo_handler.py`

## 完整模板

```python
"""<功能描述> Bot 处理器 —— <触发条件说明>。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from src.core.framework.decorators import (
    MessageScope,
    Permission,
    controller,
    on_command,
    on_keyword,
    on_regex,          # 可选
    on_event_type,     # 可选，用于非消息事件
)
from src.core.protocol.segment import MessageBuilder

if TYPE_CHECKING:
    from src.core.framework.context import Context
    from src.services.xxx import XxxService  # 仅用于类型提示

logger = structlog.get_logger()


@controller(
    name="unique_handler_name",        # 唯一标识，蛇形命名
    display_name="功能展示名",           # 前端权限管理页面显示
    description="功能简要描述",
    tags=["fun"],                       # 分类标签
    default_enabled=False,             # False=管理员手动开启; True=默认开启
    # system=True,                     # 强制启用、不在前端显示（系统级功能）
)
class XxxHandler:
    """Xxx 处理器。"""

    @on_command(
        "cmd",                          # 触发命令（不含 /）
        permission=Permission.ANYONE,   # 权限：ANYONE / ADMIN / SUPER_ADMIN
        message_scope=MessageScope.group,  # group / private / both
        display_name="命令触发",
        description="通过 /cmd 触发",
    )
    async def handle_cmd(self, ctx: Context) -> bool:
        """处理命令请求。"""
        from src.services.xxx import XxxService  # 在函数内延迟导入，避免循环依赖

        if not ctx.has_service(XxxService):
            return False

        svc: XxxService = ctx.get_service(XxxService)
        # ... 业务逻辑 ...

        await ctx.reply("回复内容")
        return True   # True = 事件已处理；False = 交给下一个 Handler
```

## 路由装饰器速查

| 装饰器 | 用途 | 关键参数 |
|--------|------|----------|
| `@on_command("cmd")` | `/cmd` 命令触发 | `permission`, `message_scope` |
| `@on_keyword({"词1", "词2"})` | 消息含关键词 | `message_scope` |
| `@on_regex(r"pattern")` | 正则匹配消息 | `message_scope` |
| `@on_event_type("notice.group_increase")` | 特定事件类型（非消息）| — |

**同一方法叠加多个装饰器** = 注册为多条独立路由规则，各自可在前端独立控制。

## Permission 权限级别

```python
Permission.ANYONE        # 所有人（默认）
Permission.ADMIN         # 群管理员及以上
Permission.SUPER_ADMIN   # 超级管理员（config.py 中配置）
```

## Context API 常用方法

```python
ctx.user_id              # int: 发送者 QQ 号
ctx.group_id             # int | None: 群号（私聊为 None）
ctx.message_text         # str: 消息纯文本内容
ctx.raw_message          # 原始消息段列表

await ctx.reply("文本")  # 回复消息（自动加 @）
await ctx.send("文本")   # 发送消息（不加 @）

ctx.has_service(SvcClass)          # 检查服务是否注入
ctx.get_service(SvcClass) -> svc   # 获取服务实例
```

## MessageBuilder 消息构建

```python
msg = (
    MessageBuilder()
    .at(ctx.user_id)          # @用户
    .text(" 签到成功！")        # 文本
    .image("http://...")      # 图片（URL 或 base64）
    .build()
)
await ctx.reply(msg)
```

## 异常处理模式

```python
try:
    result = await svc.do_something(...)
except Exception:
    logger.exception(
        "操作失败描述",
        user_id=ctx.user_id,
        group_id=ctx.group_id,
        event_type="feature.handler_error",
    )
    await ctx.reply("操作失败，请稍后重试")
    return True
```

## 常见错误

| 错误 | 原因 | 修复 |
|------|------|------|
| 处理器未被触发 | 文件名不含 `_handler.py` 或未在 `src/handlers/` 下 | 检查文件路径和命名 |
| `circular import` | 在模块级导入了 Service 类 | 移至函数体内延迟导入 |
| 权限报错 | `default_enabled=False` 且未开启 | 前端权限管理页手动开启 |
| Service 为 None | `has_service()` 未检查直接 `get_service()` | 先 `has_service()` 再 `get_service()` |
| 叠加装饰器顺序 | `@on_command` 必须最靠近方法定义 | `@on_keyword` 在上，`@on_command` 在下 |
