# 本地开发指南

## 前置依赖

- Python 3.11+（已在 3.14 验证）
- Node.js 20+（已在 26 验证）
- 可选：PostgreSQL 14+（本地可先用 SQLite 零配置启动）

## 目录结构

```
wechat-insight/
├── backend/      FastAPI + SQLAlchemy + Alembic
├── worker/       采集 Worker（复用 backend 的 providers/db）
├── frontend/     Next.js + TypeScript
├── docs/         需求 / 数据库 / 开发 / 部署文档
└── openspec/     规划与规格
```

## 1. 环境变量

```bash
cp .env.example .env
```

关键变量：`DATABASE_URL`、`DEFAULT_PROVIDER`（本地用 `mock`）、`CORS_ORIGINS`、供应商 Key。
**第三方 Key 只能放在后端环境变量，禁止使用 `NEXT_PUBLIC_` 前缀。**

## 2. 后端

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements-dev.txt   # 本地无 psycopg
# 生产改用: ./.venv/bin/pip install -r requirements.txt

# 初始化数据库（本地可默认 SQLite；生产用 PostgreSQL）
./.venv/bin/alembic upgrade head

# 启动 API
./.venv/bin/uvicorn app.main:app --reload --port 8000
```

验证：`curl http://localhost:8000/health` → `{"status":"ok"}`，浏览 `http://localhost:8000/docs`。

## 3. Worker

```bash
# 从仓库根目录运行（worker 会复用 backend 包）
.venv/bin/python -m worker.main --once      # 跑一轮入队+处理后退出
# 或常驻调度（默认 300s）
backend/.venv/bin/python -m worker.main --interval 60
```

本地默认 `DEFAULT_PROVIDER=mock`，无需真实 API Key 即可跑通「账号→文章→指标→快照」。
如使用 PostgreSQL，先在 `.env` 设置 `DATABASE_URL` 再执行 `alembic upgrade head`。

## 4. 前端

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

前端通过 `NEXT_PUBLIC_API_BASE`（默认 `http://localhost:8000`）访问后端。

## 4.1 登录与信息登记（认证 + 准入）

后端已内置手机号+密码、微信扫码（含 mock 回退）登录与信息登记审核。默认 `AUTH_ENFORCED=false` 时**不强制**（数据接口仍公开），便于先上线再灰度。

- 数据库：迁移 `0003_auth_onboarding`（`alembic upgrade head`）新增 `users / user_sessions / onboarding_proofs / onboarding_submissions`。
- 密码：PBKDF2-HMAC-SHA256（标准库，无额外依赖）。
- 会话：登录写 `HttpOnly` Cookie（`SESSION_COOKIE_NAME`，默认 `wi_session`），仅存令牌哈希、可撤销。
- 前端同源代理：`frontend/next.config.mjs` 用 `rewrites` 把 `/api/*` 代理到后端（`API_PROXY_TARGET`，默认 `http://localhost:8000`），Cookie 落在 `:3000` 同源；Server Component 读 Cookie 并转发到后端。
- 管理员引导：`.env` 设 `ADMIN_PHONE`/`ADMIN_PASSWORD`，启动时幂等创建管理员，用于审核（`/admin/reviews`）。
- 上传目录：`UPLOAD_DIR`（默认 `backend/uploads`），证明文件经鉴权接口受控读取，不静态暴露。
- 微信扫码：配置 `WECHAT_APP_ID/WECHAT_APP_SECRET/WECHAT_REDIRECT_URI` 启用真实 OAuth2；未配置且非生产时登录页显示「模拟微信登录」。

**打开强制登录（灰度）**：

1. 后端 `.env`：`AUTH_ENFORCED=true` 并重启 API（数据接口要求登录 + 审核通过）。
2. 前端构建变量：`NEXT_PUBLIC_AUTH_ENFORCED=true`（控制 `middleware` 与页面门禁，重建生效）。
3. 回滚：两者改回 `false` 即恢复公开访问（无破坏性迁移）。

端到端自测（mock）：注册/登录 → 首次引导 `/onboarding` 填表+上传 → `/onboarding/pending` → 管理员 `/admin/reviews` 通过 → 首页可用；驳回则 `/onboarding/rejected` 可重提。

## 5. 测试

```bash
cd backend
./.venv/bin/python -m pytest -q        # 后端 + worker 测试（SQLite）

cd frontend
npm run test                            # 前端格式化/组件逻辑单测
npm run build                           # 生产构建校验
```

## 6. 数据源接入（Qovia 已验证）

- 真实接口（`/v1/raw/wechat/*`）：`account_search`（账号）、`articles`（历史文章，`mp_id`+`cursor`）、`article_metrics`（阅读/点赞/在看/评论/分享）。
- 字段映射集中在 `backend/app/providers/qovia.py` 的 `_map_*`；业务层不依赖供应商字段。
- 连通性检查（不会打印密钥）：

```bash
cd backend
DEFAULT_PROVIDER=qovia python -m scripts.check_provider 科技
```

- 切到真实数据：把 `.env` 的 `DEFAULT_PROVIDER=qovia`。当前账户余额为 0、靠 trial（`meta.billed=false`），正式采集前需充值；每次成功调用约 `$0.005`（以账单为准）。
- 错误会映射为：`402` 余额不足、`429` 限流、`403` 权限、`404` 无数据、`5xx` 数据源不可用，均不外泄原始响应或密钥。

## 7. 常见问题

- **本地默认用 SQLite**：生产必须切换 PostgreSQL，`DATABASE_URL` 用 `postgresql+psycopg://...`。
- **Python 3.14 安装 psycopg 失败**：本地用 `requirements-dev.txt`（不含 psycopg），部署机器再装生产依赖。
- **端口冲突**：后端 `--port 8000`、前端默认 3000，可在命令中调整。
