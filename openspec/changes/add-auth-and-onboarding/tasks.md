# Tasks

## 1. Backend: 数据模型与迁移

- [x] 1.1 在 `backend/app/db/models.py` 新增 `User`、`UserSession`、`OnboardingSubmission` 模型（字段与枚举见 design §4），验证 `python -c "import app.db.models"` 通过
- [x] 1.2 新增 Alembic 迁移 `backend/migrations/versions/0003_auth_onboarding.py`（含唯一约束与索引），验证 `alembic upgrade head` 成功、`alembic downgrade -1` 可回滚
- [x] 1.3 在 `backend/app/core/config.py` 增加配置（`AUTH_ENFORCED`、`SESSION_TTL_*`、`WECHAT_*`、`PROOF_MAX_MB`、`UPLOAD_DIR`、`ADMIN_PHONE`、`ADMIN_PASSWORD`）并更新 `.env.example`，验证 `get_settings()` 可读到默认值

## 2. Backend: 认证

- [x] 2.1 新增密码哈希工具（`passlib[bcrypt]` 或 `bcrypt`，若新增依赖则更新 `requirements.txt`），验证单测校验哈希与校验函数正确
- [x] 2.2 新增会话服务（生成高熵令牌、只存哈希、过期/撤销校验），验证单测覆盖创建、校验、过期、登出
- [x] 2.3 新增 `backend/app/api/v1/auth.py`：`register`、`login`（手机号+密码，Set-Cookie）、`me`、`logout`，验证 pytest 覆盖注册/登录/当前用户/登出
- [x] 2.4 新增微信 OAuth 客户端（真实 + `MockWechatClient`）与 `auth/wechat/authorize`、`auth/wechat/callback`、`auth/wechat/mock`（仅非生产），验证 mock 全流程可建会话、生产禁用 mock
- [x] 2.5 在 `router.py` 注册 auth 路由，验证 `GET /health` 与 auth 路由均可达

## 3. Backend: 准入登记与审核

- [x] 3.1 新增 `backend/app/api/v1/onboarding.py`：`submit`（含必填校验与「其他」文本）、`status`/`me` 视角读取，验证 pytest 覆盖必填缺失、首次提交进入待审核、重复提交被拒
- [x] 3.2 新增 `POST /api/v1/onboarding/proof`（multipart 上传，白名单+大小校验，服务端生成文件名落 `UPLOAD_DIR`），验证合格/不合格文件用例
- [x] 3.3 新增管理员接口：待审/历史列表、`approve`、`reject`（附原因）、受控读取证明文件，验证 `require_admin` 与状态流转正确（写 `users.onboarding_status` 同步）
- [x] 3.4 新增 `Notifier` 接口与 `InAppNotifier`（预留 `SmsNotifier` 空实现），验证状态变更后可被前端读取到

## 4. Backend: 鉴权依赖与灰度

- [x] 4.1 在 `backend/app/api/deps.py` 新增 `get_current_user`、`require_approved`、`require_admin`，验证错误码 `401`/`403` 与错误信封一致
- [x] 4.2 给 `accounts`/`articles` 路由挂 `require_approved`，由 `AUTH_ENFORCED` 控制是否强制，验证开关两态行为正确
- [x] 4.3 启动时按 `ADMIN_PHONE`/`ADMIN_PASSWORD` 幂等引导管理员账号（`is_admin`、`approved`），验证重复启动不重复创建

## 5. Frontend: 会话与数据流

- [x] 5.1 `next.config` 增加 `rewrites` 将 `/api/:path*` 代理到 `API_PROXY_TARGET`，验证浏览器经 `:3000` 调 `/api/v1/*` 命中后端且 Cookie 落地在前端源
- [x] 5.2 扩展 `lib/api.ts`：支持携带/转发会话、新增 auth 与 onboarding 调用、统一处理 `401/403`，验证 `npm run build` 通过
- [x] 5.3 新增 `middleware.ts`：无会话访问受保护路由 → `/login`，放行 `/login`、`/register`、`/onboarding*`、静态资源；验证守卫生效
- [x] 5.4 在 `lib/types.ts` 增加用户/会话/登记相关类型，验证类型检查通过

## 6. Frontend: 页面

- [x] 6.1 新增 `/login`（微信扫码 + 账号密码 Tab 切换，mock 入口仅开发可见）与 `/register`，验证登录/注册成功后可拿到会话并跳转
- [x] 6.2 新增 `/onboarding` 表单：获知途径、用户类型（含「其他」联动输入）、公司、证明上传、姓名、电话（必填），需求可选，验证必填校验与上传
- [x] 6.3 新增 `/onboarding/pending`、`/onboarding/rejected`（显示驳回原因 + 重新提交），验证状态路由正确
- [x] 6.4 按 `onboarding_status` 实现页面级门禁：`none→/onboarding`、`pending→pending`、`rejected→rejected`、`approved→主应用`，验证四种状态跳转
- [x] 6.5 新增 `/admin/reviews` 列表与通过/驳回操作，验证仅管理员可访问、证明文件可查看
- [x] 6.6 `layout.tsx` 头部增加登录态/登出入口，验证登出后回到登录页

## 7. Frontend: 样式与响应式

- [x] 7.1 在 `globals.css` 为登录、表单、上传、审核页补充样式（复用现有深色主题变量与 `.card`/`.notice`），验证与既有页面视觉一致
- [x] 7.2 移动端响应式（表单/单选项/审核列表窄屏堆叠），验证无溢出

## 8. 集成验证与文档

- [x] 8.1 后端 `cd backend && pytest -q` 全绿；前端 `cd frontend && npm run test && npm run build` 全绿
- [x] 8.2 端到端（mock 登录，`AUTH_ENFORCED=true`）：登录→首次强制登记→待审核门禁→管理员通过→进入主应用；驳回→重提路径可走通
- [x] 8.3 在 `docs/development.md` 与 `docs/deployment.md` 补充：新增环境变量、`UPLOAD_DIR` 持久化、`AUTH_ENFORCED` 切换与回滚、管理员引导、微信回调配置
- [x] 8.4 验证未登录/未通过审核时数据接口分别返回 `401`/`403`，且 `/health` 仍公开

## Workflow follow-up

- 评审通过后执行 `/opsx-apply` 落地实现；完成后 `/opsx-archive` 归档并合并 `authentication`、`onboarding` 新规格与 `query-api` 变更。
