# Security Policy

## Supported Versions

仅对最新的主分支（`master`）提供安全修复支持。

| 版本 | 支持状态 |
|------|----------|
| `master` (latest) | ✅ 支持 |
| 旧版本 tag | ❌ 不再维护 |

## Reporting a Vulnerability

**请勿通过 GitHub Issues 公开披露安全漏洞。**

请通过以下方式私下报告：

1. 使用 GitHub 的 [Private Security Advisories](https://github.com/AkariRin/Texas/security/advisories/new) 提交
2. 或发送邮件至项目维护者（在 GitHub 个人资料中查找联系方式）

报告中请尽可能包含：

- 漏洞描述及影响范围
- 复现步骤（PoC 代码或截图）
- 受影响的组件/文件路径
- 建议的修复方案（可选）

## Response Timeline

| 阶段 | 目标时间 |
|------|----------|
| 确认收到报告 | 72 小时内 |
| 初步评估和严重性定级 | 7 天内 |
| 修复并发布补丁 | 视严重程度，7–30 天内 |
| 公开披露 | 补丁发布后协商确定 |

## Scope

**在范围内（我们关注的安全问题）：**

- 认证绕过 / 未授权访问 API 或 WebSocket
- SQL 注入 / ORM 参数注入
- XSS（跨站脚本）/ 模板注入
- 敏感信息泄漏（日志、API 响应、错误信息）
- SSRF（服务端请求伪造）
- 依赖库中的已知 CVE 且影响本项目
- Docker 镜像中的高危配置错误

**不在范围内：**

- 需要物理访问或 root 权限的攻击
- 社会工程学 / 网络钓鱼
- 自托管实例中用户自行引入的配置问题
- 拒绝服务（DoS）攻击（资源耗尽类）
- 第三方服务（NapCat、PostgreSQL、Redis）本身的漏洞

## Security Practices for Deployers

部署 Texas 时请遵循以下安全基线：

- **必须**通过 `.env` 文件或环境变量注入所有凭据，**禁止**硬编码
- `NAPCAT_ACCESS_TOKEN` 使用高熵随机字符串（至少 32 字节）
- 不要将管理 API 端口直接暴露到公网；使用反向代理（Nginx/Caddy）并启用 TLS
- 定期运行 `uv run pip-audit` 检查 Python 依赖的已知 CVE
- 生产镜像使用 `uv sync --no-dev` 排除开发依赖
- 启用 PostgreSQL 连接加密（`sslmode=require`）
- 限制 Redis 仅监听内网地址，并配置 `requirepass`
