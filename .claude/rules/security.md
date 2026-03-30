# 安全规则（强制执行）

本规则适用于所有代码变更，违反任何一条均为阻断性问题。

## Secrets 管理

- **禁止**在代码中硬编码任何密钥、token、密码、API key（包括测试代码）
- 所有凭据必须通过环境变量或 `.env` 文件注入，统一通过 `src/core/config.py` 的 Pydantic Settings 读取
- `.env`、`*.key`、`*_secret*` 文件必须列入 `.gitignore`，**绝不允许**提交到版本库
- 日志输出禁止打印 secrets 字段（Structlog 配置 `secrets_filter`）

## 输入校验

- 所有外部输入的信任边界：**API 请求体**、**WebSocket 消息**、**URL 参数/路径参数**、**Query 参数**
- Python 后端：必须使用 **Pydantic v2 模型**或 FastAPI 路由类型注解进行校验，不得使用裸 `dict`
- 前端：用户输入在提交前必须经过客户端基础校验（类型、长度、格式），但后端校验是最终防线
- 禁止信任 `Content-Length`、`X-Forwarded-For` 等可伪造的请求头进行授权判断

## SQL 注入

- **禁止**使用字符串拼接或 `%`/`.format()`/f-string 构造 SQL 语句
- 必须使用 **SQLAlchemy ORM**（`select(Model).where(...)`）或参数化查询（`text("... :param")` + `bindparams`）
- 原生 SQL 审查时需标注 `# nosec` 并说明安全理由

## XSS 防护

- 前端（Vue 3）：**禁止**将用户提供的内容绑定到 `v-html`；如必须渲染富文本，使用经过白名单过滤的库
- 后端 API 返回的用户生成内容不应假设前端会转义，确保不含危险的内联脚本注入点
- HTTP 响应头必须设置 `Content-Security-Policy`（通过 FastAPI 中间件统一注入）

## CSRF 防护

- 本项目 API 使用 **Bearer token 认证**而非 cookie session，天然规避主要 CSRF 攻击面
- 确保 `src/core/main.py` 中 CORS 白名单不包含通配符 `*`（除非是纯公开接口）
- WebSocket 握手必须校验 `NAPCAT_ACCESS_TOKEN`，拒绝无令牌连接

## 依赖安全

- 新增第三方依赖前，检查 [PyPI 安全顾问](https://pypi.org/security/) 或运行 `uv run pip-audit`
- **禁止**使用 `eval()`、`exec()`、`pickle.loads()` 处理任何来自外部的不可信数据
- 禁止在生产镜像中安装开发依赖（`uv sync --no-dev` for production）
