# Design

## Context

后端为 FastAPI + SQLAlchemy + Alembic（`backend/app`），错误统一走 `AppError` → `{ "error": { "code", "message" } }` 信封（`main.py`），配置为 `frozen` `Settings` + `get_settings()`（`core/config.py`，从 `BACKEND_DIR/.env` 与仓库根 `.env` 加载），路由在 `api/v1/router.py` 聚合，依赖注入在 `api/deps.py`（现有 `get_db`）。ORM 模型见 `db/models.py`（无任何用户/身份模型），迁移版本 `0001`、`0002`。前端为 Next.js 15 App Router，绝大多数页面是 **Server Component** 直接 `fetch` 后端（`lib/api.ts` 的 `getJson` + `ApiError`，`NEXT_PUBLIC_API_BASE` 默认 `http://localhost:8000`），深色主题走 `globals.css`。当前前后端是 **不同源**（`:3000` 与 `:8000`），这是会话方案必须解决的关键约束。动机与范围见 `proposal.md`，行为契约见 `specs/authentication`、`specs/onboarding`、`specs/query-api`。

## Goals / Non-Goals

**Goals:**
- 手机号+密码与微信扫码（真实 OAuth2 + 非生产 mock 回退）两种登录，服务端可撤销会话。
- 首次信息录入表单 + 证明材料上传 + 待审核/通过/驳回状态流转 + 管理员审核。
- 未登录 → 登录页；已登录未通过审核 → 门禁页；审核通过 → 主应用。门禁前后端双层生效。
- 与既有错误信封、配置模式、SSR 数据流风格保持一致，不引入前端 UI 框架。

**Non-Goals:**
- 不做复杂 RBAC、组织/多租户、找回密码（预留）、验证码登录/注册、邮箱登录。
- 不接入真实短信服务商（仅预留通道，MVP 应用内通知）。
- 不做对象存储（MVP 用本地目录），不改动数据采集/指标模型。

## Decisions

### 1. 会话：服务端可撤销的会话令牌 + HttpOnly Cookie

登录后生成随机高熵令牌，**只把哈希**存 `user_sessions.token_hash`，明文令牌写入 `HttpOnly; SameSite=Lax; Path=/; Secure(生产)` Cookie；服务端按令牌哈希校验、支持过期与主动撤销（登出/改密）。相比无状态 JWT，DB 会话天然可撤销、易审计（记录 UA/IP/时间）、无需轮换密钥。后端同时接受 Cookie 与 `Authorization: Bearer <token>`，便于 SSR 服务端转发与命令行调试。

### 2. 跨源 Cookie：前端同源代理（Next.js rewrite）+ SSR 转发

开发/部署默认前端 `:3000`、后端 `:8000` 不同源，浏览器 Cookie 不会自动带到后端。方案：在 `next.config` 配置 **rewrites** 将 `/api/:path*` 代理到后端（`API_PROXY_TARGET`），使浏览器对 `:3000` 同源调用 `/api/v1/*`，后端 `Set-Cookie` 落到前端源，登录/登出/表单提交均可正常携带 Cookie；Server Component 通过 `cookies()` 读取令牌，转发到后端（`Cookie:` 或 `Authorization:`）。这样既保留现有 SSR `fetch` 风格，又消除跨源 Cookie 与 CORS 隐患（`CORS_ORIGINS` 仍保留用于直连场景）。

**替代方案**：localStorage + Bearer——否决，SSR 服务端无法安全读取、XSS 暴露面大。

### 3. 微信扫码登录：网站应用 OAuth2 + mock 回退

- 真实流程：`GET /api/v1/auth/wechat/authorize` 生成带 `state`（CSRF，短时有效并绑定会话/回跳）的微信 `qrconnect` 授权 URL；前端用该 URL 渲染二维码（`<iframe>` 或跳转）。用户扫码确认后微信回调 `GET /api/v1/auth/wechat/callback?code&state`；后端校验 `state`、用 `code` 换 `access_token`/`openid`/`unionid`，按 `unionid`（无则 `openid`）关联或创建用户，建立会话后重定向回前端。
- mock 回退：当 `WECHAT_APP_ID/SECRET` 缺失且 `APP_ENV != production` 时，启用 `MockWechatClient` 与 `POST /api/v1/auth/wechat/mock`，用固定/输入身份直接建立会话；**生产环境一律禁用 mock**（配置断言）。
- 配置项：`WECHAT_APP_ID`、`WECHAT_APP_SECRET`、`WECHAT_REDIRECT_URI`、`WECHAT_STATE_TTL_SECONDS`。

### 4. 数据模型（新增迁移 `0003_auth_onboarding`）

- `users`：`id`、`phone`(唯一, nullable, 微信用户可空)、`password_hash`(null for 纯微信用户)、`wechat_unionid`/`wechat_openid`(唯一, nullable)、`display_name`、`is_admin`(bool)、`onboarding_status`(枚举 `none|pending|approved|rejected`，默认 `none`，用于门禁的快速判断)、`created_at/updated_at`。
- `user_sessions`：`id`、`user_id`、`token_hash`(唯一)、`expires_at`、`revoked_at`(nullable)、`created_at`、`user_agent`、`ip`(nullable)。
- `onboarding_submissions`：`id`、`user_id`、`status`(pending/approved/rejected)、`source_channel`(枚举+`source_other`)、`user_type`(枚举+`user_type_other`)、`company_name`、`contact_name`、`contact_phone`、`needs`(nullable)、`proof_path`、`proof_mime`、`proof_size`、`reject_reason`(nullable)、`reviewer_id`(nullable)、`submitted_at`、`reviewed_at`(nullable)。保留历史，最新一条决定当前状态；写入时同步更新 `users.onboarding_status`。
- 枚举用 `String` + 常量类（沿用 `JobStatus` 风格），避免 DB 级枚举迁移成本。

### 5. 访问控制依赖与门禁双层

- `api/deps.py` 新增：`get_current_user`（无有效会话→`AppError(401, "UNAUTHENTICATED")`）、`require_approved`（`onboarding_status != approved`→`AppError(403, "ONBOARDING_REQUIRED"|"ONBOARDING_PENDING"|"ONBOARDING_REJECTED")`）、`require_admin`（非管理员→`AppError(403, "FORBIDDEN")`）。
- 给 `accounts`/`articles` 路由整体挂 `Depends(require_approved)`；`onboarding` 审核接口挂 `require_admin`；`auth`/`health` 公开。
- 通过配置 `AUTH_ENFORCED`（默认 `false`，灰度期）=false 时数据路由暂不强制（便于先上线端点、再开启），生产置 `true`。这样避免"一上线就锁死"的回滚风险。
- 前端：`middleware.ts` 对受保护路由做**轻量**判断（无会话 Cookie→`/login`）；更精确的准入状态由页面 Server Component 调 `getCurrentUser()` 决定：`401`→`/login`，`pending`→`/onboarding/pending`，`rejected`→`/onboarding/rejected`，`none`→`/onboarding`，`approved`→放行。前端仅做体验引导，**真正授权以接口 `require_approved` 为准**（防绕过）。

### 6. 证明材料上传：本地目录 + 鉴权访问

`POST /api/v1/onboarding/proof`（登录用户）用 multipart 上传；校验扩展名/MIME 白名单（`jpg/png/webp/pdf`）与大小上限（`PROOF_MAX_MB`，默认 5MB），以不可猜测文件名（uuid+crc）落盘至 `UPLOAD_DIR`；记录 `proof_path/mime/size`。**不静态暴露**上传目录，管理员经 `GET /api/v1/onboarding/submissions/{id}/proof`（`require_admin`）受控读取。防路径穿越：文件名由服务端生成，读取时校验路径在 `UPLOAD_DIR` 之内。

### 7. 管理员引导与通知

- 管理员引导：启动时若配置 `ADMIN_PHONE`+`ADMIN_PASSWORD`，幂等创建/标记一个 `is_admin=1` 且 `onboarding_status=approved` 的账号。
- 通知：定义 `Notifier` 接口，MVP 用 `InAppNotifier`（写"通知"表或直接由状态字段驱动，前端轮询 `/auth/me`）；预留 `SmsNotifier`（未配置服务商时为空实现，绝不谎报已发送短信）。

### 8. 前端集成与现有代码的适配

- `lib/api.ts`：`getJson` 支持携带 Cookie（SSR 从 `cookies()` 注入）与可选 `Authorization`；新增 `loginWithPassword`、`me`、`logout`、`submitOnboarding`、`uploadProof`、`getWechatAuthorizeUrl` 等；统一把 `401/403` 映射为 `ApiError`，由页面转成重定向。
- 新增页面：`app/login`（微信扫码 + 账号密码切换）、`app/register`、`app/onboarding`（表单 + 上传 + 「其他」联动）、`app/onboarding/pending`、`app/onboarding/rejected`；管理员审核页 `app/admin/reviews`（简单列表 + 通过/驳回）。
- `layout.tsx` 头部增加登录态与登出入口；语义与深色主题沿用 `globals.css` 变量与 `.card`/`.notice` 等工具类。
- `next.config`：加 `rewrites` 代理、按需 `images`/env 透传；不改动既有页面数据逻辑。

**替代方案**：把前端整体迁到 Tailwind/shadcn——与本项目现状冲突、改动过大，否决。

## Risks / Trade-offs

- **一上线即锁死公开访问** → 用 `AUTH_ENFORCED` 灰度开关，先发端点与 UI，验证后开启；README/运维文档标注切换步骤。
- **微信真实 OAuth 需要公网回调域名与备案，离线无法联调** → mock 回退保证本地闭环；生产强制真实凭据并禁用 mock。
- **跨源 Cookie 陷阱** → 以 rewrite 同源代理为主，SSR 显式转发令牌；`CORS_ORIGINS` 兼容直连。
- **上传安全（路径穿越/内容伪装/超大文件）** → 服务端生成文件名、白名单+大小校验、受控读取、目录不可静态访问。
- **PII 合规（手机号/公司/证明文件）** → 最小化收集、访问受控、日志脱敏；保留删除/保留策略留待合规评审。
- **会话/上传目录需持久化与清理** → 文档标注 `UPLOAD_DIR`、会话过期清理任务（后续）。

## Migration Plan

1. 新增模型与 Alembic 迁移 `0003_auth_onboarding`；本地 `init_db` 自动建表（仅 SQLite 非生产）。
2. 先实现 `auth`/`onboarding` 端点与依赖，`AUTH_ENFORCED=false` 上线（数据接口仍公开），完成联调。
3. 上线登录/登记/审核 UI 与门禁，mock 登录本地验证全流程。
4. 配置真实微信凭据与 `ADMIN_PHONE/PASSWORD`，置 `AUTH_ENFORCED=true`，完成真实扫码与审核闭环验证。
5. 回滚：置 `AUTH_ENFORCED=false` 即恢复公开读取；会话与登记数据为增量，无破坏性迁移。

## Open Questions

- 短信服务商选型（阿里云/腾讯云）与模板报备——接入后把 `SmsNotifier` 接上即可，不影响本次结构。
- 审核通过后是否需要"到期/续期"或配额策略——不在本次范围。
- 管理员审核页面放在同一 Web 应用还是独立后台——MVP 先放同一应用 `/admin`，后续可拆分。
