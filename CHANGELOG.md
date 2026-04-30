## v1.4.0 (2026-04-30)

### Feat

- **frontend**: 为 Autocomplete 新增 autofocus 支持并修复竞态与 null 处理问题
- **frontend**: 新增 GroupAutocomplete/UserAutocomplete 并应用到全站
- **like**: 实现点赞功能（全栈）
- **drift-bottle**: 实现漂流瓶功能（全栈）
- **checkin**: 新增用户主动群签到功能（全栈）

### Fix

- **frontend,services**: 修复 Vuetify 4 异步补全模式并加固后端错误处理

### Refactor

- **core**: 将装饰器 controller 重命名为 component
- **core**: 重构权限检查与生命周期管理
- **structure**: 框架/业务深度解耦重构（Phase 0-6）
- 将对话框组件迁移至全局 components 目录并优化后端查询
- **drift-bottle**: 消除重复服务获取逻辑并重命名原始消息段类型
- **core**: 提取 ceil_div 工具函数并优化 CheckinService 查询

## v1.3.0 (2026-04-17)

### Feat

- **handler**: 新增 /help 功能帮助指令，支持分页列表和功能详情查询
- **core**: 将 HTML 注入防护下沉至 BrowserService 渲染层
- **core**: 新增 Markdown 转 PNG 渲染器（Playwright + markdown-it-py）
- **frontend**: 为会话选择器和私聊权限列表添加骨架屏加载状态

### Fix

- **frontend**: 修复面包屑样式、弹窗交互及群信息卡片关闭按钮冗余

### Refactor

- **services**: 消除帮助查询重复代码并优化 FeatureRegistry 性能
- **db**: 将聊天库迁移目录从 chat_migrations 迁移到 migrations/chat

## v1.2.1 (2026-04-14)

### Feat

- **core**: 引入 PERSISTENT_REDIS_URL，关键数据迁移持久化 Redis
- **rpc**: 增强 RPC 模块，添加并发控制、Prometheus 指标与错误处理

### Fix

- **db**: 修复权限迁移 FK 约束顺序，完善 CLI 前置检查
- **frontend**: 将 pnpm-workspace.yaml 中的构建配置键名修正为 ignoredBuiltDependencies
- **security**: 收紧 CI 权限并脱敏 API 错误响应

### Refactor

- **core**: 将 Redis 迁移到单数据库，规范化缓存键命名空间
- **frontend**: 提取 usePagination 组合式函数，内联单用工具函数
- **frontend**: 适配权限系统重构与人员模块接口变更
- **api**: 精简人员查询接口与 jrlp 服务，移除冗余关联加载
- **permission**: 重构权限系统，改用内存不可变注册表替代 feature_registry 表
- **jrlp**: 移除 wife_name 字段，改用关联查询动态获取昵称
- **frontend**: 重构布局组件目录并更新 jrlp 视图与 API 类型
- **db**: 重构迁移系统为 baseline 模式，精简历史迁移文件
- **frontend**: 重构人员信息卡片组件，替换 MegaMenu 为新菜单组件
- **core**: 将应用启动逻辑抽取为生命周期管理模块，统一异常与缓存键注册表

## v1.2.0 (2026-04-06)

### Feat

- **framework**: 为 RateLimitInterceptor 添加控制器排除名单
- **jrlp**: 实现今日老婆功能
- **rpc**: 新增 Redis RPC 基础设施，替代打卡 HTTP 内部回调
- **auth**: 替换 passlib 为 bcrypt，添加 Session 滑动续期
- **session**: 重构会话框架，支持多用户并发与二次确认流程
- **checkin**: 将打卡调度迁移至 Celery Beat + HTTP 回调架构
- **auth**: 实现完整登录鉴权系统

### Fix

- **jrlp**: 昵称回退改用 user.nickname，不再显示 QQ 号
- **jrlp**: 将 4 个 @on_fullmatch 合并为单个 @on_regex，避免 feature_registry upsert 冲突
- **jrlp**: 修复 Pydantic Schema 中 date 字段名与类型注解冲突
- **frontend**: 修复 XSS 风险并完善错误处理
- 修复多处异常捕获语法与输入校验漏洞

### Refactor

- **rpc,api**: 完成 RPCBridge 重命名并移除 checkin HTTP 接口
- **rpc**: 解耦 BotAPI 依赖，将 BotAPIProxy 重命名为 RPCProxy
- 移除 WebAuthn/TOTP/Session 鉴权系统
- **db**: 新增迁移文件以删除鉴权相关数据库表
- **docker**: 将角色控制从 ROLE 环境变量改为 ENTRYPOINT 子命令
- **types**: 完善 services/tasks 层类型注解，修复归档 SQL 转义
- **session**: 增强并发安全、移除 FSM 序列化、提取 build_mention_message
- **session**: 移除废弃 API、增强并发安全与错误处理
- 拆分大型服务与视图组件，遵循单一职责原则

## v1.1.0 (2026-03-31)

### Feat

- **services**: 新增每日自动打卡服务并加固安全校验
- **bot**: 新增 Bot 信息页面及 Profile API 接口
- **frontend**: 重设计导航为大菜单覆盖层（汉堡触发，L1 页面列表 + L2 子路由卡片）
- **framework**: 实现交互式会话框架并重构反馈模块
- 实现用户反馈系统
- **models**: 添加 Feedback 反馈模型和枚举定义

### Refactor

- **frontend**: 重构导航菜单与 Bot 页面，全局添加骨架屏加载态
- 统一全项目枚举为 StrEnum 规范并消除魔法字符串
- 提取反馈枚举、重构会话管理并优化前端错误处理
- **backend**: 优化聊天归档查询性能
- **frontend**: 简化 API 错误处理逻辑

## v1.0.0 (2026-03-29)

### Refactor

- **backend**: clean up code style across service and core modules
- **frontend**: replace PageHeader with PageLayout component
